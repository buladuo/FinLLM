from tkinter import NO
import core.agents as Agents
import logging

class TableLocator:
    
    def __init__(self):
        self.db_table = ['AStockBasicInfoDB','AStockIndustryDB','AStockOperationsDB',
                         'AStockShareholderDB','AStockFinanceDB','AStockMarketQuotesDB',
                         'AStockEventsDB','HKStockDB','USStockDB','PublicFundDB','CreditDB',
                         'IndexDB','InstitutionDB','ConstantDB']
        self.question_classification_agent = Agents.QuestionClassificationAgent()
        self.table_locator_agent = Agents.TableLocatorAgent()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"\nDatabase class is : {self.db_table}\n"
                         f"Total num of class is {len(self.db_table)} ")
        
    def get_table(self, question:str): 
        result = self.question_classification_agent.query(question)
        
        database = self.db_table[int(result['id']) - 1].lower()
        database_info = database+'_info'
        self.logger.info(f"Chosed database in:{database_info}")
        result = self.table_locator_agent.query(question,type=database_info)
        return result
    
    def get_table_with_db(self,question:str):
        
        new_result = []
        for result in self.question_classification_agent.query(question):
            # 首先要对result进行类型检查，如果是字符串或者不是字典类型则错误，跳过
            if (not isinstance(result,dict)) and result is not None:
                pass
            database = self.db_table[int(result['id']) - 1].lower()
            database_info = database+'_info'
            self.logger.info(f"Chosed database in:{database_info}")
            result = self.table_locator_agent.query(question,type=database_info)
            
            
            
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
        