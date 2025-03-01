
import logging
from core.templates_manager import TemplatesManager


class ConstructFewShots():
    def __init__(self,templates_manager:TemplatesManager):
        
        self.templates_manager = templates_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        
        
    def construct_cot_few_shots(self, question_str: str, topk=5):
        """
        构建COT格式的few-shots数据
        """
        # 获取topk的COT格式示例
        examples = self.templates_manager.get_topk_questions_cot(question_str, topk)
        
        # 将examples转换为所需的字符串格式
        result_str = ""
        for idx, example in enumerate(examples, start=1):
            result_str += f"**示例{idx}**:\n"
            result_str += "  user：\n"
            result_str += f"  ```\n  {example['question']}\n  ```\n"
            result_str += "  assistant：\n"
            result_str += "  ```json\n"
            result_str += "  [\n"
            result_str += "    {\n"
            result_str += f'      "question": "{example["question"]}",\n'
            result_str += '      "subquestions": [\n'
            for subq in example['subquestions']:
                result_str += '        {\n'
                result_str += f'          "id": {subq["id"]},\n'
                result_str += f'          "subquestion": "{subq["subquestion"]}"\n'
                result_str += '        },\n'
            result_str = result_str.rstrip(',\n') + '\n'
            result_str += '      ]\n'
            result_str += '    }\n'
            result_str += '  ]\n'
            result_str += '  ```\n\n'
        
        self.logger.debug(f"构造的Cot格式few-shots数据：\n{result_str}")
        return result_str
    
    def construct_sql_few_shots(self, question_str: str, topk=5):
        """
        构建SQL格式的few-shots数据
        """
        # 获取topk的SQL格式示例
        examples = self.templates_manager.get_topk_subquestions_sql(question_str, topk)
        
        # 将examples转换为所需的字符串格式
        result_str = ""
        for idx, example in enumerate(examples, start=1):
            result_str += f"**示例{idx}**\n"
            result_str += "user:\n"
            result_str += "```\n"
            result_str += f"{example[0]['question']}\n"
            result_str += "已知信息：\n"
            result_str += "```json\n"
            result_str += "<已经查询到的相关的实体信息>\n"
            result_str += "```\n"
            result_str += "```json\n"
            result_str += "<已经查已经完成的子问题的查询的详细信息，包括子问题、对应的SQL、SQL理由、查询结果、对应字段的描述>\n"
            result_str += "```\n"
            result_str += "表信息：\n"
            result_str += "<这里是数据库表的信息，xxx>\n"
            result_str += "其他生成要求，特别的一些指令等。你需要严格按照分析流程分析我的输入\n"
            result_str += "assistant:\n"
            result_str += "<这里你要严格遵循分析流程，按照分析步骤逐步思考，有助于正确生成sql>\n"
            result_str += "```json\n[\n"
            for sql_item in example:
                result_str += "\t{\n"
                result_str += f'\t\t"id": {sql_item["id"]},\n'
                result_str += f'\t\t"reason": "{sql_item["reason"]}",\n'
                result_str += f'\t\t"sql": "{sql_item["sql"]}"\n'
                result_str += "\t},\n"
            result_str = result_str.rstrip(',\n') + "\n]\n```\n\n"
        
        self.logger.debug(f"构造的SQL格式few-shots数据：\n{result_str}")
        return result_str
    
    def construct_class_name_few_shots(self, question_str: str, topk=5):
        examples = self.templates_manager.get_topk_subquestions_table_names(question_str, topk)
        
        result_str = ""
        
        for idx, example in enumerate(examples, start=1):
            question = example['question']
            tables_name = example['tables_name']
            
            result = self._find_db_classes(tables_name)
            
            # 将结果转换为字符串格式
            result_str += f"**示例{idx}**:\n"
            result_str += "user：\n"
            result_str += f"```\n{question}\n```\n"
            result_str += "assistant：\n"
            result_str += "```json\n[\n"
            for item in result:
                result_str += "\t{\n"
                result_str += f'\t\t"id": {item["id"]},\n'
                result_str += f'\t\t"class_name": "{item["class_name"]}"\n'
                result_str += "\t},\n"
            result_str = result_str.rstrip(',\n') + "\n]\n```\n\n"
        
        self.logger.debug(f"构造的分类名称few-shots数据：\n{result_str}")
        return result_str
    
    def construct_table_name_few_shots(self, question_str: str, topk=5):
        examples = self.templates_manager.get_topk_subquestions_table_names(question_str, topk)
        
        result_str = ""
        
        for idx, example in enumerate(examples, start=1):
            question = example['question']
            tables_name = example['tables_name']
            
            result = self._find_table_names(tables_name)
            
            # 将结果转换为字符串格式
            result_str += f"**示例{idx}**:\n"
            result_str += "user：\n"
            result_str += f"```\n{question}\n```\n"
            result_str += "assistant：\n"
            result_str += "```json\n[\n"
            for item in result:
                result_str += "\t{\n"
                result_str += f'\t\t"id": {item["table_id"]},\n'
                result_str += f'\t\t"table_name": "{item["table_name"]}"\n'
                result_str += "\t},\n"
            result_str = result_str.rstrip(',\n') + "\n]\n```\n\n"
        self.logger.debug(f"构造的表名few-shots数据：\n{result_str}")
        return result_str

    def _find_db_classes(self, db_table_names):
        # 定义数据库表名与类别名称的对应关系
        db_classes = [
            {"id": 1, "class_name": "A股上市公司数据", "db_name": "AStockBasicInfoDB"},
            {"id": 2, "class_name": "上市公司行业板块", "db_name": "AStockIndustryDB"},
            {"id": 3, "class_name": "上市公司产品供销/人力资源", "db_name": "AStockOperationsDB"},
            {"id": 4, "class_name": "上市公司股东与股本/公司治理", "db_name": "AStockShareholderDB"},
            {"id": 5, "class_name": "上市公司财务指标/财务报表/融资与分红", "db_name": "AStockFinanceDB"},
            {"id": 6, "class_name": "上市公司股票行情", "db_name": "AStockMarketQuotesDB"},
            {"id": 7, "class_name": "上市公司公告资讯/重大事项", "db_name": "AStockEventsDB"},
            {"id": 8, "class_name": "公募基金数据库", "db_name": "PublicFundDB"},
            {"id": 9, "class_name": "诚信数据库", "db_name": "CreditDB"},
            {"id": 10, "class_name": "指数数据库", "db_name": "IndexDB"},
            {"id": 11, "class_name": "机构数据库", "db_name": "InstitutionDB"},
            {"id": 12, "class_name": "常量库", "db_name": "ConstantDB"},
            {"id": 13, "class_name": "港股数据库", "db_name": "HKStockDB"},
            {"id": 14, "class_name": "美股数据库", "db_name": "USStockDB"}
        ]
        
        # 结果列表
        result = []
        
        # 遍历输入的数据库表名列表
        for db_table_name in db_table_names:
            # 去除前后空格
            db_table_name = db_table_name.strip()
            
            # 分割字符串，获取 db_name
            db_name = db_table_name.split('.')[0]
            
            # 将 db_name 转为小写
            input_name = db_name.lower()
            
            # 查找匹配项
            for item in db_classes:
                if item["db_name"].lower() == input_name:
                    result.append({"id": item["id"], "class_name": item["class_name"]})
                    break
        
        return result

    def _find_table_names(self, db_table_names:list)->list:
        # 定义数据库表名与类别名称的对应关系
        AStockBasicInfoDB = [{"id":1,"table_name":"LC_StockArchives"},{"id":2,"table_name":"LC_NameChange"},{"id":3,"table_name":"LC_Business"}]
        AStockEventsDB = [{"id":1,"table_name":"LC_Warrant"},{"id":2,"table_name":"LC_Credit"},{"id":3,"table_name":"LC_SuitArbitration"},{"id":4,"table_name":"LC_EntrustInv"},{"id":5,"table_name":"LC_Regroup"},{"id":6,"table_name":"LC_MajorContract"},{"id":7,"table_name":"LC_InvestorRa"},{"id":8,"table_name":"LC_InvestorDetail"}]
        AStockFinanceDB = [{"id":1,"table_name":"LC_AShareSeasonedNewIssue"},{"id":2,"table_name":"LC_ASharePlacement"},{"id":3,"table_name":"LC_Dividend"},{"id":4,"table_name":"LC_CapitalInvest"},{"id":5,"table_name":"LC_BalanceSheetAll"},{"id":6,"table_name":"LC_IncomeStatementAll"},{"id":7,"table_name":"LC_CashFlowStatementAll"},{"id":8,"table_name":"LC_IntAssetsDetail"},{"id":9,"table_name":"LC_MainOperIncome"},{"id":10,"table_name":"LC_OperatingStatus"},{"id":11,"table_name":"LC_AuditOpinion"}] 
        AStockIndustryDB = [{"id":1,"table_name":"LC_ExgIndustry"},{"id":2,"table_name":"LC_ExgIndChange"},{"id":3,"table_name":"LC_IndustryValuation"},{"id":4,"table_name":"LC_IndFinIndicators"},{"id":5,"table_name":"LC_COConcept"},{"id":6,"table_name":"LC_ConceptList"}] 
        AStockMarketQuotesDB = [{"id":1,"table_name":"CS_StockCapFlowIndex"},{"id":2,"table_name":"CS_TurnoverVolTecIndex"},{"id":3,"table_name":"CS_StockPatterns"},{"id":4,"table_name":"QT_DailyQuote"},{"id":5,"table_name":"QT_StockPerformance"},{"id":6,"table_name":"LC_SuspendResumption"}] 
        AStockOperationsDB = [{"id":1,"table_name":"LC_SuppCustDetail"},{"id":2,"table_name":"LC_Staff"},{"id":3,"table_name":"LC_RewardStat"}]
        AStockShareholderDB = [{"id":1,"table_name":"LC_SHTypeClassifi"},{"id":2,"table_name":"LC_MainSHListNew"},{"id":3,"table_name":"LC_SHNumber"},{"id":4,"table_name":"LC_Mshareholder"},{"id":5,"table_name":"LC_ActualController"},{"id":6,"table_name":"LC_ShareStru"},{"id":7,"table_name":"LC_StockHoldingSt"},{"id":8,"table_name":"LC_ShareTransfer"},{"id":9,"table_name":"LC_ShareFP"},{"id":10,"table_name":"LC_ShareFPSta"},{"id":11,"table_name":"LC_Buyback"},{"id":12,"table_name":"LC_BuybackAttach"},{"id":13,"table_name":"LC_LegalDistribution"},{"id":14,"table_name":"LC_NationalStockHoldSt"},{"id":15,"table_name":"CS_ForeignHoldingSt"},{"id":16,"table_name":"LC_ESOP"},{"id":17,"table_name":"LC_ESOPSummary"},{"id":18,"table_name":"LC_TransferPlan"},{"id":19,"table_name":"LC_SMAttendInfo"}] 
        ConstantDB = [{"id":1,"table_name":"SecuMain"},{"id":2,"table_name":"HK_SecuMain"},{"id":3,"table_name":"CT_SystemConst"},{"id":4,"table_name":"QT_TradingDayNew"},{"id":5,"table_name":"LC_AreaCode"},{"id":6,"table_name":"US_SecuMain"}] 
        CreditDB = [{"id":1,"table_name":"LC_ViolatiParty"}]
        HKStockDB = [{"id":1,"table_name":"HK_EmployeeChange"},{"id":2,"table_name":"HK_StockArchives"},{"id":3,"table_name":"CS_HKStockPerformance"}]
        IndexDB = [{"id":1,"table_name":"LC_IndexBasicInfo"},{"id":2,"table_name":"LC_IndexComponent"}]
        InstitutionDB = [{"id":1,"table_name":"LC_InstiArchive"},{"id":2,"table_name":"PS_EventStru"},{"id":3,"table_name":"PS_NewsSecurity"}]
        PublicFundDB = [{"id":1,"table_name":"MF_FundArchives"},{"id":2,"table_name":"MF_FundProdName"},{"id":3,"table_name":"MF_InvestAdvisorOutline"},{"id":4,"table_name":"MF_Dividend"}]
        USStockDB = [{"id":1,"table_name":"US_CompanyInfo"},{"id":2,"table_name":"US_DailyQuote"}]
        all_db_tables = [{'db_name':'AStockBasicInfoDB','tables':AStockBasicInfoDB},
                         {'db_name':'AStockEventsDB','tables':AStockEventsDB},
                         {'db_name':'AStockFinanceDB','tables':AStockFinanceDB},
                         {'db_name':'AStockIndustryDB','tables':AStockIndustryDB},
                         {'db_name':'AStockMarketQuotesDB','tables':AStockMarketQuotesDB},
                         {'db_name':'AStockOperationsDB','tables':AStockOperationsDB},
                         {'db_name':'AStockShareholderDB','tables':AStockShareholderDB},
                         {'db_name':'ConstantDB','tables':ConstantDB},
                         {'db_name':'CreditDB','tables':CreditDB},
                         {'db_name':'HKStockDB','tables':HKStockDB},
                         {'db_name':'IndexDB','tables':IndexDB},
                         {'db_name':'InstitutionDB','tables':InstitutionDB},
                         {'db_name':'PublicFundDB','tables':PublicFundDB},
                         {'db_name':'USStockDB','tables':USStockDB}]
        
        
        # 结果列表
        result = []
        
        # 遍历输入的数据库表名列表
        for db_table_name in db_table_names:
            # 去除前后空格
            db_table_name = db_table_name.strip()
            
            # 分割字符串，获取 table_name
            table_name = db_table_name.split('.')[-1]
            
            # 将 db_name 转为小写
            input_name = table_name.lower()
            
            # 查找匹配项
            for item in all_db_tables:
                for table in item['tables']:
                    if input_name == table['table_name'].lower():
                        result.append({
                            'db_name': item['db_name'],
                            'table_id': table['id'],
                            'table_name': table['table_name']
                        })
                        break  # 找到匹配项后跳出内层循环
        
        return result
