import re
import os
import json
import logging
from urllib import response

from sqlalchemy import insert_sentinel, null
import core.agents as Agents

from paths import TEMPLATE_PATH
from services.db_client import DBClient
from services.db_client import DBClient
from core.entity_processor import EntityProcessor
from core.database_table_manager import DatabaseTableManager

from utils.code2name import Code2Name

class SqlProcessor:
    def __init__(self,entity_processor:EntityProcessor,db_table_manager:DatabaseTableManager,
                 sql_reason_agent:Agents.SQLReasonAgent,sql_generator_agent:Agents.SQLGeneratorAgent,
                 sql_regenerator_agent:Agents.SQLReGeneratorAgent,sql_comparison_agent:Agents.SQLComparisonAgent,
                 db_client:DBClient,retries=3):
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.entity_processor = entity_processor
        self.db_table_manager = db_table_manager
        self.sql_reason_agent = sql_reason_agent
        self.sql_generator_agent = sql_generator_agent
        self.sql_regenerator_agent = sql_regenerator_agent
        self.sql_comparison_agent = sql_comparison_agent
        self.db_client = db_client
        self.retries = retries
        
        self.code2name = Code2Name(db_client)
        
    def _normalize_query(self, query: str):
        """移除多余的空格并将 SQL 转为小写"""
        return re.sub(r'\s+', ' ', query).lower()

    def _extract_from_query(self, query: str):
        """从 SQL 查询中提取表名，支持子查询和别名"""
        tables = []
        
        # 正则匹配 FROM 和 JOIN 后面的表名或子查询（包括别名）
        pattern = r'(from|join)\s+(\([^\)]+\)|[^\s,;]+(?:\s+as\s+[^\s,;]+)?)'
        for match in re.findall(pattern, query):
            table = match[1]
            # 如果是子查询，提取括号内的查询并递归调用提取表名
            if table.startswith('('):
                subquery_tables = self._extract_from_query(table)
                tables.extend(subquery_tables)
            else:
                # 去除别名部分，仅保留实际表名
                table = table.split(' as ')[0]
                tables.append(table)
        
        return tables
    
    def extract_fields(self, query: str):
        """
        提取 SQL 查询中的字段列表，支持复杂字段表达式，如 COUNT(field), ROUND(field, 2) AS f 等
        """
        query = self._normalize_query(query)
        fields = []
        
        # 处理多条 SQL 查询语句
        for subquery in self._split_queries(query):
            # 匹配 SELECT 子句中的字段
            match = re.search(r'select\s+(.*?)\s+from', subquery, re.IGNORECASE)
            if match:
                fields_str = match.group(1)
                
                # 按照逗号分割字段，并去除空格
                for field in fields_str.split(','):
                    field = field.strip()

                    # 去除带有函数调用的部分（例如 COUNT(field), ROUND(field, 2)）
                    field_name = re.sub(r'\s*\(.*\)\s*', '', field).strip()

                    # 去除可能的别名（例如 field AS f, ROUND(field, 2) AS rounded_price）
                    field_name = re.sub(r'\s+as\s+[`\w"\']+', '', field_name, flags=re.IGNORECASE).strip()

                    # 只保留字段名（排除聚合函数和其他表达式）
                    if field_name and field_name not in fields:
                        fields.append(field_name)
        
        self.logger.info(f"SQL Query: {query}")
        self.logger.info(f"Extracted fields: {fields}")
        
        return fields
    def extract_where_fields(self, query: str):
        """
        提取 SQL 查询中的 WHERE 子句中的字段
        """
        query = self._normalize_query(query)
        where_fields = []
        
        # 找到 WHERE 子句的内容
        where_match = re.search(r'where\s+(.*?)(\s+group\s+by|\s+order\s+by|\s*;|$)', query, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1).strip()
            
            # 匹配 WHERE 子句中的字段（通常是字段名、表名或字段操作）
            # 这里只是简单的匹配字段名，支持一些基本操作符（例如 AND，OR）
            # 假设 WHERE 子句中的字段名是直接的字段引用或可能带有条件的字段操作
            field_pattern = r'\b\w+\b'
            where_fields = re.findall(field_pattern, where_clause)

            # 去除可能的重复字段
            where_fields = list(set(where_fields))

        self.logger.info(f"SQL Query: {query}")
        self.logger.info(f"Extracted WHERE fields: {where_fields}")
        
        return where_fields
    

    def extract_tables(self, query: str):
        """
        提取 SQL 查询中的表名，支持子查询和多个 SQL 查询
        """
        query = self._normalize_query(query)
        tables = []
        
        # 处理多条 SQL 查询语句
        for subquery in self._split_queries(query):
            # 提取表名
            tables.extend(self._extract_from_query(subquery))
        
        return tables
    
    def _split_queries(self, query: str):
        """
        通过 ';' 分割多个 SQL 查询语句，并处理嵌套查询
        """
        queries = []
        depth = 0
        current_query = []
        
        # 遍历字符并根据分号分割 SQL 查询
        for char in query:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ';' and depth == 0:
                queries.append(''.join(current_query).strip())
                current_query = []
                continue
            current_query.append(char)
        
        if current_query:
            queries.append(''.join(current_query).strip())  # 最后一个查询
        
        return queries

    def preprocess_sql(self, sql: str):
        return sql


    def check_sql_result(self, sql_result: dict) -> str:
        """
        检查 SQL 查询结果
        :param sql_result: SQL 查询的返回结果字典
        """
        # 检查查询是否成功
        
        if not sql_result or not sql_result.get('success', False):
            return False
        
        # 检查 count 是否为 0
        if sql_result.get('count', 0) == 0:
            return False
        
        # 检查返回的数据字段是否全部是 0、null 或 None
        # 假设查询结果存储在 sql_result['data'] 中
        if sql_result.get('data', []):
            for record in sql_result['data']:
                # 遍历每一行记录的字段值
                for value in record.values():
                    # 如果有一个字段值不是 0、null 或 None，返回 '成功'
                    if value not in [0, None, 'null', null]:  # 也考虑字符串'null'
                        return True
        
        # 如果所有字段都是 0、null 或 None，返回 '失败'
        return False


    def get_sql_result(self, question: str, entity_info: dict, all_info: list, sql_example: None, history_subquestions: list) -> dict:
        prompt = f"""\n问题是：{question}\n已知实体信息：\n```json\n{entity_info}\n```\n
                    \n已经完成的历史查询信息：\n```json\n{history_subquestions}\n```\n涉及的表的信息：\n{all_info}\n
                    在回答之前，你应当首先解读我的提问:{question}，你应当从已知的信息中读取信息，然后按照要求生成sql。
                    请注意：externtion_annotation字段中包含了重要的信息，我要求你首先解读其中的每一条指示.
                    之后，你需要逐个字段分析表中的每一个字段的注解信息，这有助于你选择正确的数值。最后你再生成sql"""
        sql_list_with_example = self.generate_sql(prompt, sql_example)
        
        # 执行初次 SQL 查询
        primary_results = []
        for sql in sql_list_with_example:
            result = self.execute_sql(sql, question, entity_info, all_info)
            primary_results.append(result)

        # 检查初次结果是否失败
        if any(not result for result in primary_results):  # 如果任一结果为 False
            self.logger.warning("发现查询失败，准备重新生成 SQL 查询并执行")
            
            # 重新生成 SQL 查询，不使用样例
            sql_list_no_example = self.generate_sql(prompt)
            secondary_results = []
            
            # 执行重新生成的 SQL 查询
            for sql in sql_list_no_example:
                result = self.execute_sql(sql, question, entity_info, all_info)
                secondary_results.append(result)

            # 将两个结果保存到字典中进行对比
            results = {
                'primary_results': sql_list_with_example,
                'secondary_results': sql_list_no_example
            }
            comparison_prompt = f"""1. **当前处理的问题**\n{question}\n2. **已经完成的历史查询**\n{history_subquestions}
            3. **已经知道的相关实体信息**\n{entity_info}\n4. **涉及到的表信息**\n{all_info}5. **当前两两个查询版本**\n
            ```json\n{results}\n```"""
            comparison_result = self.sql_comparison_agent.query([{"role":"user","content":comparison_prompt}])
            
            self.logger.info(f"初始查询结果: {json.dumps(sql_list_with_example, indent=4, ensure_ascii=False)}")
            self.logger.info(f"重试查询结果: {json.dumps(sql_list_no_example, indent=4, ensure_ascii=False)}")
            self.logger.info(f"选择的版本结果: {json.dumps(comparison_result, indent=4, ensure_ascii=False)}")
            
            final_choose = 'secondary_results'
            if comparison_result and isinstance(comparison_result,list) and len(comparison_result):
                comparison_result = comparison_result[0]
                final_choose = comparison_result.get("choose",'secondary_results')
            
            if 'secondary' in final_choose:
                return sql_list_no_example

        self.logger.info(f"SQL 查询结果: {json.dumps(sql_list_with_example, indent=4, ensure_ascii=False)}")
        return sql_list_with_example


    def generate_sql(self, prompt: str, sql_example=None) -> list:
        if sql_example:
            return list(self.sql_generator_agent.query_json_format([{
                'role': 'user',
                'content': prompt
            }], 'json_format_witout_example', examples=sql_example))
        else:
            return list(self.sql_generator_agent.query_json_format([{
                'role': 'user',
                'content': prompt
            }]))

    def execute_sql(self, sql: dict, question: str, entity_info: dict, all_info: list):
        if 'sql' not in sql:
            self.logger.warning(f"Warning: 'sql' field is missing in the sql list item: {sql}")
            return
        
        sql_result = self.db_client.query(sql['sql'])
        sql_message = []
        retry_count = 0
        while sql_result and sql_result.get('success', False) == False and retry_count < self.retries:
            prompt_with_error = f"""\n问题是\n{question}\n
                                    已知信息：\n{entity_info}\n
                                    涉及的表的信息：\n{all_info}\n
                                    SQL:\n{sql['sql']}\n
                                    错误信息:\n{sql_result['detail']}"""
            sql_message.append({
                'role': 'user',
                'content': prompt_with_error
            })
            response, sql['sql'] = self.sql_regenerator_agent.query(sql_message)
            
            sql_message.append({
                'role': 'assistant',
                'content': response
            })
            
            sql_result = self.db_client.query(sql['sql'])
            retry_count += 1
            
        if not sql_result:
            sql_result = {'success': False}
            
        sql['sql_result_count'] = sql_result.get('count') if sql_result['success'] else 0
        if not self.check_sql_result(sql_result):
            sql['sql_result']  = sql_result['data'] if sql_result['success'] else []
            return False
            
        sql_result = self.code2name.process(sql_result) if sql_result['success'] else sql_result
        sql['sql_result'] = sql_result['data'] if sql_result['success'] else []
        
        # 处理字段注释
        self.process_field_annotations(sql, all_info)
        return True

    def process_field_annotations(self, sql: dict, all_info: list):
        if sql.get('sql_result', []):
            sql['filed_annotations'] = []
            fields = self.extract_fields(sql['sql'])
            
            for field in fields:
                combined_annotations = []
                field_lower = field.lower()
                
                for table in all_info:
                    for column in table['fields']:
                        if str(column['column_name']).lower() == field_lower:
                            if column['annotation_zh'] and str(column['annotation_zh']).strip() != 'nan':
                                combined_annotations.append(str(column['annotation_zh']))
                
                if combined_annotations:
                    sql['filed_annotations'].append({
                        'field': field,
                        'annotations': " | ".join(combined_annotations)
                    })

    
    def generate_template(self, question_id:int):
        id = 0
        for file_path in TEMPLATE_PATH:
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    
                for item in data:
                    id += 1
                    if id != question_id:
                        continue
                    question_all = item['question']
                    entity_result = self.entity_processor.process_items(question_all)
                    
                    self.logger.info(f"问题: {question_all}")
                    message = []
                    for subquestion in item['subquestions']:
                        question = subquestion['subquestion']
                        sql_query = subquestion['sql']
                        
                        if not sql_query:
                            continue
                        
                        tables = self.extract_tables(sql_query)
                        subquestion['table_name'] = tables
                        all_info = []
                        for table  in tables:
                            table_info = self.db_table_manager.get_table_info(table.split('.')[-1].lower())
                            all_info.append(table_info)
                        
                        message.append({'role':'user','content':f"## 这里是sql所涉及的表的信息:\n{all_info}\n ## 以下是我的请求问题:\n{question}\n## 以下是我的sql查询:\n{sql_query}\n## 题目中已经知道的实体信息为：\n{entity_result}"})
                        response,result = self.sql_reason_agent.query(message)
                        
                        try:
                            if isinstance(result,list) and len(result) > 0:
                                result = result[-1]
                                subquestion['reason'] = str(result.get('reason',""))
                        except Exception as e:
                            self.logger.error(f"An error occurred: {e}")
                            return
                        message.append({'role':'assistant','content':f"{response}"})
                    
                        
                        # 打印表名列表
                        self.logger.info(f"  子问题 ID: {subquestion['id']}")
                        self.logger.info(f"  子问题: {subquestion['subquestion']}")
                        self.logger.info(f"  表名: {subquestion['table_name']}")  # 输出表名列表
                        self.logger.info(f"  原因: {subquestion['reason']}")
                        self.logger.info(f"  SQL 查询: {sql_query}")
                        self.logger.info("-" * 150)
                        
                        try:
                            with open(file_path, 'w', encoding='utf-8') as file:
                                json.dump(data, file, ensure_ascii=False, indent=4)
                                self.logger.info(f"已保存进 {file_path}")
                        except Exception as e:
                            self.logger.error(f"保存文件时发生错误: {e}")

                # 将处理好的数据写回原文件路径
                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                self.logger.info(f"处理完毕，已保存到 {file_path}")
            else:
                self.logger.error(f"文件 {file_path} 不存在！")


