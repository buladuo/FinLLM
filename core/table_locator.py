from tkinter import NO
import core.agents as Agents
import logging

class TableLocator:
    
    def __init__(self,question_classification_agent:Agents.QuestionClassificationAgent,table_locator_agent:Agents.TableLocatorAgent):
        self.db_table = ['AStockBasicInfoDB','AStockIndustryDB','AStockOperationsDB',
                         'AStockShareholderDB','AStockFinanceDB','AStockMarketQuotesDB',
                         'AStockEventsDB','PublicFundDB','CreditDB','IndexDB',
                         'InstitutionDB','ConstantDB','HKStockDB','USStockDB']
        self.question_classification_agent = question_classification_agent
        self.table_locator_agent = table_locator_agent
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"\nDatabase class is : {self.db_table}\n"
                         f"Total num of class is {len(self.db_table)} ")
        
    def get_table(self, question: str, is_hk = False,is_us = False):
        
        if is_hk:
            question = "这是一个港股题目，你应该查找港股相关的表：" + question
            return self.get_hk_table(question)
        elif is_us:
            question = "这是一个股题目，你应该查找美股相关的表：" + question
            return self.get_us_table(question)
        
        # 初始化一个空列表用于存储最终结果
        final_results = []

        # 遍历 question_classification_agent 查询的多个结果
        for result in self.question_classification_agent.query([{"role":"user","content":question}]):
            # 检查 result 是否为字典类型且不为 None
            if isinstance(result, dict) and result is not None:
                # 根据分类结果选择对应的数据库
                database = self.db_table[int(result['id']) - 1].lower()
                database_info = database + '_info'
                
                # 记录日志，显示选择的数据库信息
                self.logger.info(f"Chosen database: {database_info}")
                
                # 通过 table_locator_agent 查询表信息
                tables = self.table_locator_agent.query([{"role":"user","content":question}], type=database_info)
                
                # 遍历查询结果，确保每个结果都是字典类型且不为 None
                for res in tables:
                    if isinstance(res, dict) and res is not None:
                        if 'table_name' in res:
                            res['table_name'] = res['table_name'].lower()
                        # 添加 db_table_name 字段，标识表所属的数据库
                        res['db_name'] = database  # 添加数据库名
                        final_results.append(res)  # 将完整结果添加到最终列表中
                        self.logger.info(f"Added table info with db_table_name: {res}")
                    else:
                        self.logger.warning(f"Expected dict but got {type(res)}: {res}")
            else:
                self.logger.warning(f"Expected dict but got {type(result)}: {result}")
        
        # 返回包含完整信息的字典列表
        return final_results

    def get_hk_table(self, question: str):
        # 初始化一个空列表用于存储最终结果
        final_results = []
        tables = [{
            "id":12,
            "class_name": "常量库"
        },
        {
            "id": 13,
            "class_name": "港股数据库"
        }]

        # 遍历 question_classification_agent 查询的多个结果
        for result in tables:
            # 检查 result 是否为字典类型且不为 None
            if isinstance(result, dict) and result is not None:
                # 根据分类结果选择对应的数据库
                database = self.db_table[int(result['id']) - 1].lower()
                database_info = database + '_info'
                
                # 记录日志，显示选择的数据库信息
                self.logger.info(f"Chosen database: {database_info}")
                
                # 通过 table_locator_agent 查询表信息
                tables = self.table_locator_agent.query([{"role":"user","content":question}], type=database_info)
                
                # 遍历查询结果，确保每个结果都是字典类型且不为 None
                for res in tables:
                    if isinstance(res, dict) and res is not None:
                        if 'table_name' in res:
                            res['table_name'] = res['table_name'].lower()
                        # 添加 db_table_name 字段，标识表所属的数据库
                        res['db_name'] = database  # 添加数据库名
                        final_results.append(res)  # 将完整结果添加到最终列表中
                        self.logger.info(f"Added table info with db_table_name: {res}")
                    else:
                        self.logger.warning(f"Expected dict but got {type(res)}: {res}")
            else:
                self.logger.warning(f"Expected dict but got {type(result)}: {result}")
        
        # 返回包含完整信息的字典列表
        return final_results

    def get_us_table(self, question: str):
        # 初始化一个空列表用于存储最终结果
        final_results = []
        tables = [{
            "id":12,
            "class_name": "常量库"
        },{
            "id": 14,
            "class_name": "美股数据库"
        }]

        # 遍历 question_classification_agent 查询的多个结果
        for result in tables:
            # 检查 result 是否为字典类型且不为 None
            if isinstance(result, dict) and result is not None:
                # 根据分类结果选择对应的数据库
                database = self.db_table[int(result['id']) - 1].lower()
                database_info = database + '_info'
                
                # 记录日志，显示选择的数据库信息
                self.logger.info(f"Chosen database: {database_info}")
                
                # 通过 table_locator_agent 查询表信息
                tables = self.table_locator_agent.query([{"role":"user","content":question}], type=database_info)
                
                # 遍历查询结果，确保每个结果都是字典类型且不为 None
                for res in tables:
                    if isinstance(res, dict) and res is not None:
                        if 'table_name' in res:
                            res['table_name'] = res['table_name'].lower()
                        # 添加 db_table_name 字段，标识表所属的数据库
                        res['db_name'] = database  # 添加数据库名
                        final_results.append(res)  # 将完整结果添加到最终列表中
                        self.logger.info(f"Added table info with db_table_name: {res}")
                    else:
                        self.logger.warning(f"Expected dict but got {type(res)}: {res}")
            else:
                self.logger.warning(f"Expected dict but got {type(result)}: {result}")
        
        # 返回包含完整信息的字典列表
        return final_results


    
    def get_table_with_db(self,question:str):
        
        new_result = []
        for result in self.question_classification_agent.query(question):
            # 首先要对result进行类型检查，如果是字符串或者不是字典类型则错误，跳过
            if (not isinstance(result,dict)) and result is not None:
                pass
            database = self.db_table[int(result['id']) - 1].lower()
            database_info = database+'_info'
            self.logger.info(f"Chosed database in:{database_info}")
            result = self.table_locator_agent.query([{"role":"user","content":question}],type=database_info)
            
            
            
            for res in result:
                # 检查res是否是字典且不为None
                if isinstance(res, dict) and res is not None:
                    table_name = res.get('table_name')  # 获取表名
                    if table_name:  # 确保表名不为空
                        # 拼接数据库和表名
                        full_table_name = f"{database}.{table_name.lower()}"
                        new_result.append(full_table_name)  # 添加到new_result
                        
                        # 输出拼接后的全表名到日志
                        self.logger.info(f"Added table name: {full_table_name} to results.")
                    else:
                        self.logger.warning("The 'table_name' key is missing or empty in the result.")
                else:
                    self.logger.warning(f"Expected dict but got {type(res)}: {res}")
            
        return new_result
        