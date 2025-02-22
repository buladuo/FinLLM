import json
import logging
import core.agents as Agents
from services.db_client import DBClient


class EntityProcessor:
    def __init__(self,db_client:DBClient,llm_agent: Agents.EntityRecognitionAgent):
        self.db_client = db_client
        self.llm_agent = llm_agent
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_company_name(self, value):
        self.logger.info(f'Processing company name: {value}')
        res_lst = []
        tables = ['ConstantDB.SecuMain', 'ConstantDB.HK_SecuMain', 'ConstantDB.US_SecuMain']
        columns_to_match = ['CompanyCode', 'SecuCode', 'ChiName', 'ChiNameAbbr',
                            'EngName', 'EngNameAbbr', 'SecuAbbr', 'ChiSpelling']
        columns_to_select = ['InnerCode', 'CompanyCode', 'SecuCode', 'ChiName', 'ChiNameAbbr',
                             'EngName', 'EngNameAbbr', 'SecuAbbr', 'ChiSpelling']

        # 防止SQL注入
        value = value.replace("'", "''")

        for table in tables:
            if 'US' in table:
                columns_to_match.remove('ChiNameAbbr')
                columns_to_select.remove('ChiNameAbbr')
                columns_to_match.remove('EngNameAbbr')
                columns_to_select.remove('EngNameAbbr')

            match_conditions = [f"{col} = '{value}'" for col in columns_to_match]
            where_clause = ' OR '.join(match_conditions)
            sql = f"""
            SELECT {', '.join(columns_to_select)}
            FROM {table}
            WHERE {where_clause}
            """
            self.logger.debug(f'Executing SQL: {sql}')  # Log SQL query
            result = self.db_client.query(sql)
            if result and result['success'] and result['count']:
                self.logger.info(f'Result found for {table}: {result}')
                res_lst.append((result, table))
            else:
                self.logger.warning(f'No results found for {table} with value: {value}')

        return res_lst
    
    def process_concept(self,value):
        res_lst = []
        tables = {
                'AStockIndustryDB.LC_ExgIndustry': ['Industry', 'FirstIndustryName', 'SecondIndustryName', 'ThirdIndustryName', 'FourthIndustryName'], 
                'AStockIndustryDB.LC_ExgIndChange': ['Industry', 'FirstIndustryName', 'SecondIndustryName', 'ThirdIndustryName', 'FourthIndustryName'], 
                'AStockIndustryDB.LC_IndustryValuation': ['IndustryName'],
                'AStockIndustryDB.LC_IndFinIndicators': ['IndustryName'], 
                'AStockIndustryDB.LC_ConceptList': ['ClassName', 'SubclassName', 'ConceptName', 'ConceptCode']}

        value = value.replace("'", "''")

        for table, cols in tables.items():
            match_conditions = [f"{col} = '{value}'" for col in cols]
            where_clause = ' OR '.join(match_conditions)
            sql = f"""
            SELECT {', '.join(cols)}
            FROM {table}
            WHERE {where_clause}
            """
            self.logger.debug(f'Executing SQL: {sql}')  # Log SQL query
            result = self.db_client.query(sql)
            if result and result['success'] and result['count']:
                self.logger.info(f'Result found for {table}: {result}')
                res_lst.append((result, table))
            else:
                self.logger.warning(f'No results found for {table} with value: {value}')

        return res_lst

    def process_code(self, value):
        self.logger.info(f'Processing code: {value}')
        res_lst = []
        tables = ['ConstantDB.SecuMain', 'ConstantDB.HK_SecuMain', 'ConstantDB.US_SecuMain']
        columns_to_select = ['InnerCode', 'CompanyCode', 'SecuCode', 'ChiName', 'ChiNameAbbr',
                             'EngName', 'EngNameAbbr', 'SecuAbbr', 'ChiSpelling']

        value = value.replace("'", "''")

        for table in tables:
            if 'US' in table:
                columns_to_select.remove('ChiNameAbbr')
                columns_to_select.remove('EngNameAbbr')

            sql = f"""
            SELECT {', '.join(columns_to_select)}
            FROM {table}
            WHERE SecuCode = '{value}'
            """
            self.logger.debug(f'Executing SQL: {sql}')  # Log SQL query
            result = self.db_client.query(sql)
            if result and result['success'] and result['count']:
                self.logger.info(f'Result found for {table}: {result}')
                res_lst.append((result, table))
            else:
                self.logger.warning(f'No results found for {table} with SecuCode: {value}')

        return res_lst
    
    def process_human(self,value):
        """
        Process the human value and return the result list.
        """
        res_lst = []
        tables = {
                'AStockBasicInfoDB.LC_StockArchives': ['GeneralManager', 'LegalConsultant'], 
                'AStockShareholderDB.LC_SHTypeClassifi': ['SHName', 'SHCode'], 
                'AStockShareholderDB.LC_MainSHListNew': ['SHList', 'GDID'], 
                'AStockShareholderDB.LC_Mshareholder': ['MSHName', 'GDID'],
                'AStockShareholderDB.LC_ActualController': ['ControllerName'], 
                'AStockShareholderDB.LC_ShareTransfer': ['TransfererName', 'ReceiverName'], 
                'AStockShareholderDB.LC_ShareFP': ['FPSHName', 'ReceiverName'], 
                'AStockShareholderDB.LC_ShareFPSta': ['FPSHName'], 
                'AStockShareholderDB.LC_LegalDistribution': ['InvestorName', 'StandardInvestorName', 'StandardAquirerName'], 
                'AStockShareholderDB.LC_NationalStockHoldSt': ['SHName'], 
                'CreditDB.LC_ViolatiParty': ['PartyName'],
                'AStockEventsDB.LC_InvestorDetail': ['PersonalName'],
                'AStockShareholderDB.LC_TransferPlan': ['SHName'],
                'PublicFundDB.MF_FundArchives': ['Manager', 'InvestAdvisorCode', 'TrusteeCode'],
                'PublicFundDB.MF_InvestAdvisorOutline': ['InvestAdvisorName', 'InvestAdvisorAbbrName', 'LegalRepr', 'GeneralManager'],
                'InstitutionDB.LC_InstiArchive': ['InvestAdvisorName', 'TrusteeName', 'LegalPersonRepr', 'GeneralManager', 'OtherManager', 'Contactman', ],
                }

        value = value.replace("'", "''")  # Escape single quotes

        
        for table, cols in tables.items():
            match_conditions = [f"{col} like '%{value}%'" for col in cols]
            where_clause = ' OR '.join(match_conditions)
            sql = f"""
            SELECT {', '.join(cols)}
            FROM {table}
            WHERE {where_clause}
            """
            self.logger.debug(f'Executing SQL: {sql}')  # Log SQL query
            result = self.db_client.query(sql)
            if result and result['success'] and result['count']:
                self.logger.info(f'Result found for {table}: {result}')
                res_lst.append((result, table))
            else:
                self.logger.warning(f'No results found for {table} with: {value}')

        return res_lst

    def process_institution(self, value):
        self.logger.info(f'Processing institution with value: {value}')
        sql = f"SELECT ChiName, CompanyCode FROM InstitutionDB.LC_InstiArchive WHERE ChiName LIKE '%{value}%'"
        self.logger.debug(f'Executing SQL: {sql}')  # Log SQL query
        result = self.db_client.query(sql)
        if result and result['success'] and result['count']:
            self.logger.info(f'Result found for InstitutionDB.LC_InstiArchive: {result}')
            return [(result, 'InstitutionDB.LC_InstiArchive')]
        else:
            self.logger.warning(f'No results found in InstitutionDB.LC_InstiArchive for value: {value}')
            return []

    def process_items(self, question):
        item_list = self.llm_agent.query([{"role":"user","content":question}])
        self.logger.info('Processing item list')
        res_list = []
        for item in item_list:
            key, value = list(item.items())[0]
            self.logger.debug(f'Processing item: {key} with value: {value}')
            if key == "基金名称" or key == "上市公司名称":
                res_list.extend(self.process_company_name(value))
            elif key == "基金公司简称":
                res_list.extend(self.process_institution(value))
            elif key == "代码":
                res_list.extend(self.process_code(value))
            elif key == "概念板块名称" or key == "概念板块":
                res_list.extend(self.process_concept(value))
            elif key == "人名":
                res_list.extend(self.process_human(value))
            else:
                self.logger.error(f'无法识别的键：{key}')

        # 过滤空值
        res_list = [i for i in res_list if i]
        
        self.logger.info(f'Processing completed with results from tables: {res_list}')
        return res_list