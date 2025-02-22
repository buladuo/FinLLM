from ast import Dict, List
from email import message, utils
from sre_constants import SUCCESS
import logging
import os
from typing import final
from unittest import result
from urllib import response

from sqlalchemy import false, true
from core import question_manager
from services.llm_client import LLMServiceFactory
from services.db_client import DBClient
from utils.logging_utils import LoggingUtils
from utils.field2sql import Field2SQL
from core.sql_processor import SqlProcessor
from core.prompt_manager import PromptManager
from core.entity_processor import EntityProcessor
from core.question_manager import QuestionManager
from core.table_locator import TableLocator
from core.database_table_manager import DatabaseTableManager
from core.yaml_table_manager import YamlTableManager


from paths import QUESTION_PATH,CONFIG_PATH,PROMPTS_PATH,QUESTION_PATH,YAML_DB_INFO_PATH,OUTPUT_PATH,TEMPLATE_PATH
import core.agents as Agents
import yaml
import json

class FINLLM:
    def __init__(self):
        config_path = CONFIG_PATH
        with open(config_path, "r") as file:
            self.config = yaml.safe_load(file)
            
        self.db_table_manager = YamlTableManager(YAML_DB_INFO_PATH)
        self.db_client = DBClient(self.config['database'])
        
        self.logging_config = self.config.get("logging", {})
        LoggingUtils.setup_logging(self.logging_config)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.prompt_manager = PromptManager(PROMPTS_PATH)
        self.question_manager = QuestionManager(QUESTION_PATH)
        self.file2sql = Field2SQL(self.db_client)
        
        self._init_agents()

        self.entity_processor = EntityProcessor(self.db_client,self.entity_recognition_agent)
        self.table_locator = TableLocator(self.question_classification_agent,self.table_locator_agent)
        self.sql_processor = SqlProcessor()
        
        
            
    def _init_agents(self):
        default_model = self.config["global"].get('default_model')
        self.logger.info("Initializing agents with default model: %s", default_model)

        # 初始化各个代理并记录日志
        self.table_locator_agent = self._init_agent('table_locator_model', Agents.TableLocatorAgent, default_model)
        self.question_classification_agent = self._init_agent('question_classification_model', Agents.QuestionClassificationAgent, default_model)
        self.entity_recognition_agent = self._init_agent('entity_recognition_agent_model', Agents.EntityRecognitionAgent, default_model)
        self.entity_reference_replacement_agent = self._init_agent('entity_reference_replacement_model', Agents.EntityReferenceReplacementAgent, default_model)
        self.answer_rewrite_agent = self._init_agent('answer_rewrite_model', Agents.AnswerRewriteAgent, default_model)
        self.cot_agent = self._init_agent('cot_model', Agents.CotAgent, default_model)
        self.sql_generator_agent = self._init_agent('sql_generator_model', Agents.SQLGeneratorAgent, default_model)
        self.sql_regenerator_agent = self._init_agent('sql_regenerator_model', Agents.SQLReGeneratorAgent, default_model)
        self.sql_reason_agent = self._init_agent('sql_reason_model', Agents.SQLReasonAgent, default_model)
        self.entity_reference_replacement_agent = self._init_agent('entity_reference_replacement_model', Agents.EntityReferenceReplacementAgent, default_model)
        

    def _init_agent(self, model_key, agent_class, default_model):
        model_name = self.config["global"].get(model_key, default_model)
        model_config = self.config["models"][model_name]
        self.logger.info("Initializing agent: %s with model: %s", agent_class.__name__, model_name)
        return agent_class(model_config, self.config["global"], self.prompt_manager)
    
    def _question_type(self,question:str,entity_infos:list):
        
        is_a = False
        is_us = False
        is_hk = False
        
        if "美股" in question:
            is_us = True
            return (is_a,is_hk,is_us)
        if "港股" in question:
            is_hk = True
            return (is_a,is_hk,is_us)
        if not entity_infos:
            return (True,is_hk,is_us)
        
        
        for entry in entity_infos:
            
            response, table_name = entry
            if 'hk_secumain' in table_name.lower():
                is_hk = True
            elif 'us_secumain' in table_name.lower():
                is_us = True
            else:
                is_a = True
        return (is_a,is_hk,is_us)
        
        
    
    def get_sql_result(self,question:str,entity_info:dict,all_info:list)->list:
        prompt = f"""\n问题是：{question}\n已知信息：\n{entity_info}\n
                    涉及的表的信息：\n{all_info}\n
                    在回答之前，你应当首先解读我的提问:{question}，你应当从已知的信息中读取信息，然后按照要求生成sql。
                    请注意：externtion_annotation字段中包含了重要的信息，我要求你首先解读其中的每一条指示.
                    之后，你需要逐个字段分析表中的每一个字段的注解信息，这有助于你选择正确的数值。最后你再生成sql"""
        
        sql_list = list(self.sql_generator_agent.query_json_format([{
                    'role':'user',
                    'content':prompt
                }]))
        
        for sql in sql_list:
            
            if 'sql' not in sql:
                self.logger.warning(f"Warning: 'sql' field is missing in the sql list item: {sql}")
                continue
            sql_result = self.db_client.query(sql['sql'])
            sql_message = []
            retry_count = 0
            while sql_result and sql_result.get('success',False) == False and retry_count < self.config["global"].get('retries'):
                
                prompt_with_error = f"""\n问题是\n{question}\n
                                        已知信息：\n{entity_info}\n
                                        涉及的表的信息：\n{all_info}\n
                                        SQL:\n{sql['sql']}\n
                                        错误信息:\n{sql_result['detail']}"""
                sql_message.append({
                    'role':'user',
                    'content':prompt_with_error
                })
                sql['sql'] = self.sql_regenerator_agent.query(sql_message)
                sql_result = self.db_client.query(sql['sql'])
                retry_count +=1
                
            if not sql_result:
                sql_result = {'success':False}
            sql['sql_result_count'] = sql_result.get('count') if sql_result['success'] else 0,
            sql['sql_result'] = sql_result['data'] if sql_result['success'] else []
        
        self.logger.info(f"SQL Query Result: {sql_list}")
        return sql_list
        
    def process_question(self,question:str, entity_info:Dict,is_hk = False,is_us = False):
        self.logger.info("Processing question: '%s' with entity_info: %s", question, entity_info)

        cot_result = self.cot_agent.query([{'role':'user','content':str(question)}])
        for cot_item in cot_result:
            subquestoins = cot_item.get('subquestions',[])
            answers = {"question":question,"subquestions":[]}
            for subquestoin in subquestoins:
                self.logger.info(f"Proccessing the question: {subquestoin['subquestion']}")
                all_info = []
                
                # TODO:这里要对子问题的上下文引用进行处理
                if answers["subquestions"]:
                    rewrited_subquestion = self.entity_reference_replacement_agent.query([{'role':'user','content':str([{"contex":answers["subquestions"],"current_question":subquestoin['subquestion']}])}])
                    if isinstance(rewrited_subquestion,list) and rewrited_subquestion and rewrited_subquestion[0].get('rewrited_question'):
                        self.logger.info(f"Rewrited Question:\n{rewrited_subquestion}")
                        subquestoin['subquestion'] = rewrited_subquestion[0].get('rewrited_question')
                
                for result in self.table_locator.get_table(subquestoin['subquestion'],is_hk=is_hk,is_us=is_us):
                    
                    table_info = self.db_table_manager.get_table_info(result['table_name'].lower())
                    infos = self.file2sql.get_all_info_source(table_info,entity_info,is_hk,is_us)
                    self.logger.info(f"InfoSource Can be: {infos}")
                    if infos :
                        table_info['externtion_annotation'].append({
                            'id':"inforsource可能获取的值",
                            "content":infos,
                            "explain":"注解：当题目中提到相关信息如年报、季度报、申万等等，你需要在生成sql的时候重点考虑这个字段的信息，比如提问第一季度xxx信息，那么你需要使用InfoSource进行限定筛选，此外对于第一季度的日期你不需要选择一个精确的日期了，选择日期在第一个季度内。这有助于派出无用信息此外，你需要区分InfoSource和InfoSourceCode，的区别，InfoSourceCode通常是一个编码，其取值通常在InfoSource的字段说明中详细介绍，InfoSource通常就是一字符串。"
                        }) 
                    all_info.append(table_info)
                sql_query_result = self.get_sql_result(subquestoin['subquestion'],entity_info,all_info)
                
                answers["subquestions"].append({
                    "id":subquestoin['id'],
                    "subquestion": subquestoin['subquestion'],
                    "sql_query_result" : sql_query_result
                })
                
            # TODO 将结果整理成为答案
            answers_with_entity_info = answers
            answers_with_entity_info['entity_info'] = entity_info
            rewrited_answer = self.answer_rewrite_agent.query([{
                'role':'user',
                'content':f"{answers_with_entity_info}"
            }],prompt_id=2) 
            answers['answers'] = rewrited_answer[0]['answer'] if len(rewrited_answer) else ""
            return answers
            
            
        self.logger.warning(f"There are some error in cot result: {cot_result}")
        return None
    
    
    def process_item(self, question_id: int) -> Dict:
        question_team = self.question_manager.get_question(question_id)
        entity_result = self.entity_processor.process_items(question_team.get_all_question())
        question_format = self._format_questions(question_team)
        is_a, is_hk, is_us = self._question_type(question_team.get_all_question(), entity_result)
        
        if not entity_result:
            entity_result = []
            
        for entry in entity_result:
            response, table_name = entry
            if 'hk_secumain' in table_name.lower() and is_hk:
                self.logger.info(f"This question is related to HK stock.")
                return self._handle_question_type(question_team, response, question_format, is_hk=True)
            if 'us_secumain' in table_name.lower() and is_us:
                self.logger.info(f"This question is related to US stock.")
                return self._handle_question_type(question_team, response, question_format, is_us=True)
            else:
                self.logger.info(f"This question is related to A stock.")
                return self._handle_question_type(question_team, response, question_format, is_a=True)

        if not entity_result:
            self.logger.info(f"This question is related to a stock for which no entity was found.")
            return self._handle_question_type(question_team, {}, question_format, is_a=True)

    
    def _format_questions(self, question_team) -> list:
        """格式化问题数据为要求的结构"""
        return [
            {"id": subquestion.get_id(), "question": subquestion.get_question()}
            for subquestion in question_team
        ]

    def _handle_question_type(self, question_team, entity_result, question_format, is_a=False, is_hk=False, is_us=False):
        """处理不同类型的问题，减少重复代码"""
        result = self.process_question(question_team.get_all_question(), entity_result, is_hk=is_hk, is_us=is_us)
        # 调用answer_rewrite_agent进行答案重写
        rewritten_answer = self.answer_rewrite_agent.query(
            [{
                'role': 'user',
                'content': f"这是整理好的子问题答案:{result}\n以下是我的请求问题:\n{question_format}"
            }],
            prompt_id=3
        )

        # 将重写后的答案设置回相应的question_team
        for answer in rewritten_answer:
            question_team.set_answer_by_id(answer.get("id"), answer.get("answer"))

        return rewritten_answer
    
    def save_result(self):
        save_path = os.path.join(OUTPUT_PATH, 'answer.json')
        self.question_manager.save_to_json(save_path)
    
    def get_total_num_questions(self):
        return self.question_manager.get_total_num_questions()
        
    def cot_questions(self):
        
        all_cot_questions = []
        for question in self.question_manager:
            cot_result = self.cot_agent.query([{'role':'user','content':str(question.get_all_question())}])
            if not isinstance(cot_result,list) and len(cot_result) and not isinstance(cot_result[0],dict):
                continue
            cot_result = cot_result[0]
            for subquestion in cot_result['subquestions']:
                subquestion['table_name'] = []
                subquestion['reason'] = ""
                subquestion['sql'] = ""
            all_cot_questions.append(cot_result)
        save_path = os.path.join(OUTPUT_PATH, 'cot_all_questions.json')
        with open(save_path, 'w', encoding='utf8') as f:
            json.dump(all_cot_questions, f, ensure_ascii=False, indent=4)
            
    def process_templates(self,question_id:int):
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
                        
                        tables = self.sql_processor.extract_tables(sql_query)
                        subquestion['table_name'] = tables
                        all_info = []
                        for table  in tables:
                            table_info = self.db_table_manager.get_table_info(table.split('.')[-1].lower())
                            all_info.append(table_info)
                        
                        message.append({'role':'user','content':f"## 这里是sql所涉及的表的信息:\n{all_info}\n ## 以下是我的请求问题:\n{question}\n## 以下是我的sql查询:\n{sql_query}\n## 题目中已经知道的实体信息为：\n{entity_result}"})
                        response,result = self.sql_reason_agent.query(message)
                        
                        if isinstance(result,list):
                            result = result[-1]
                            subquestion['reason'] = str(result.get('reason',""))
                        
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
