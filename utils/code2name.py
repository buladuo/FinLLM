
import logging

import yaml
from attr import fields_dict
# from utils.logging_utils import LoggingUtils
from services.db_client import DBClient
from paths import QUESTION_PATH,CONFIG_PATH,PROMPTS_PATH,QUESTION_PATH,YAML_DB_INFO_PATH,OUTPUT_PATH


class Code2Name():
    def __init__(self,db_client:DBClient):
        self.db_client = db_client
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _update_names(self, answer, code_key, field_name):
        '''
        通用方法，根据给定的键和字段名替换 answer 中的 ChiName 和 ChiNameAbbr
        :param answer: 包含需要更新的 answer 数据
        :param code_key: 内部代码的键（如 'InnerCode', 'CompanyCode', 'SecuCode'）
        :param field_name: 用于 SQL 查询的字段名（应与数据库字段匹配）
        :return: 更新后的 answer
        '''
        db_tables = ['ConstantDB.SecuMain', 'ConstantDB.HK_SecuMain']

        for item in answer['data']:
            code_value = None
            for key in item.keys():
                if key.lower() == code_key.lower():
                    code_value = item[key]
                    break
            
            item['ChiName'] = ''
            item['ChiNameAbbr'] = ''
            
            if code_value is not None:
                for table in db_tables:
                    sql = f'select ChiName, ChiNameAbbr from {table} where {field_name}={code_value}'
                    result = self.db_client.query(sql)  # 假设之前定义了 exec_sql 方法
                    
                    if result and result['success'] and result['count'] > 0 and result['data']:
                        chi_names = []
                        chi_name_abbrs = []
                        for data in result['data']:
                            chi_names.append(data['ChiName'] if data['ChiName'] else '')
                            chi_name_abbrs.append(data['ChiNameAbbr'] if data['ChiNameAbbr'] else '' )
                        
                        if chi_names:  
                            item['ChiName'] = ', '.join(chi_names)  # 使用逗号连接多个名称
                        if chi_name_abbrs:
                            item['ChiNameAbbr'] = ', '.join(chi_name_abbrs)  # 使用逗号连接多个简称

        return answer

    def innercode2name(self, answer):
        ''' 根据 innercode 替换返回的 answer 中的 ChiName 和 ChiNameAbbr '''
        return self._update_names(answer, 'InnerCode', 'InnerCode')

    def companycode2name(self, answer):
        ''' 根据 companycode 替换返回的 answer 中的 ChiName 和 ChiNameAbbr '''
        return self._update_names(answer, 'CompanyCode', 'CompanyCode')

    def innercode2disclname(self, answer):
        for item in answer['data']:
            code_value = None
            for key in item.keys():
                if key.lower() == 'innercode':
                    code_value = item[key]
                    break
            
            if code_value is not None:
                sql = f'select DisclName from publicfunddb.mf_fundprodname where innercode={code_value}'
                result = self.db_client.query(sql)
                if result and result['success'] and result['count'] > 0 and result['data']:
                    conceptnames = []
                    for data in result['data']:
                        conceptnames.append(data['DisclName'])
                    item['DisclName'] = ', '.join(conceptnames)

        return answer

    def secucode2name(self, answer):
        ''' 根据 secucode 替换返回的 answer 中的 ChiName 和 ChiNameAbbr '''
        return self._update_names(answer, 'SecuCode', 'SecuCode')

    def securitycode2name(self, answer):
        
        for item in answer['data']:
            code_value = None
            for key in item.keys():
                if key.lower() == 'securitycode':
                    code_value = item[key]
                    break
            
            item['CodeWithName'] = []
            
            if code_value is not None:
                sql = f'select InnerCode from PublicFundDB.MF_FundArchives where SecurityCode={code_value}'
                result = self.db_client.query(sql)
                if result and result['success'] and result['count'] > 0 and result['data']:
                    for data in result['data']:
                        new_result = self.innercode2name(result)
                        for new_result_item in new_result['data']:
                            item['CodeWithName'].append(new_result_item) 

        return answer
    
    def conceptcode2name(self,answer):
        for item in answer['data']:
            code_value = None
            for key in item.keys():
                if key.lower() == 'conceptcode':
                    code_value = item[key]
                    break
            
            if code_value is not None:
                sql = f'select ConceptName from AStockIndustryDB.LC_COConcept where ConceptCode={code_value}'
                result = self.db_client.query(sql)
                if result and result['success'] and result['count'] > 0 and result['data']:
                    conceptnames = []
                    for data in result['data']:
                        conceptnames.append(data['ConceptName'])
                    item['ConceptName'] = ', '.join(conceptnames)

        return answer
    

    def process(self, answer,sql = None):
        

            
        
        if answer.get('success', False) == False:
            return answer
        # 将 answer 转换为小写字符串
        answer_str = str(answer).lower()
        
        # 定义一个字段到处理方法的映射
        field_to_method = {
            'innercode': self.innercode2name,
            'companycode': self.companycode2name,
            'secucode': self.secucode2name,
            'securitycode': self.securitycode2name,
            'conceptcode': self.conceptcode2name
        }

        # 检测哪些字段存在于 answer_str 中，并调用相应的方法
        for field in field_to_method.keys():
            if field in answer_str:
                if sql is not None and isinstance(sql,str):
                    if field == 'innercode' and 'mf_fundprodname' in sql.lower():
                        answer = self.innercode2disclname(answer)
                # 当字段存在时，调用相应的方法
                answer = field_to_method[field](answer)
        
        return answer

