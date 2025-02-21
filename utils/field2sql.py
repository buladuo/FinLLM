
import logging
from ast import Dict
from services.db_client import DBClient

class Field2SQL():
    def __init__(self,db_client:DBClient):
        self.db_client = db_client
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_all_info_source(self,table_info:Dict,entity_info:Dict,is_hk=False,is_us=False):
        table_info_str = str(table_info).lower()
        
        if 'infosource' in table_info_str:
            sql = ''
            if 'companycode' in table_info_str and entity_info and entity_info['success'] and entity_info['data'] and entity_info['data'][0]:
                companycode = entity_info['data'][0].get('CompanyCode',111) if entity_info and entity_info['success'] == True else 111
                sql = f"""select DISTINCT infosource from {table_info['database_name']}.{table_info['table_name']} where companycode = {companycode}"""
            elif 'innercode' in table_info_str  and entity_info and entity_info['success'] and entity_info['data'] and entity_info['data'][0]:
                innercode = entity_info['data'][0].get('InnerCode',111) if entity_info and entity_info['success'] == True else 111
                sql = f"""select DISTINCT infosource from {table_info['database_name']}.{table_info['table_name']} where innercode = {innercode}"""
            else:
                sql = f"""select DISTINCT infosource from {table_info['database_name']}.{table_info['table_name']} """
            
            result = self.db_client.query(sql)
            
            prompt = "注意，InfoSource可取的值有："
            if result['success']:
                result_data = result['data']
                for innercode in result_data:
                    prompt += " " + str(innercode['infosource'])
        
            self.logger.info(f"InfoSource is: {prompt}")    
            return prompt
        
        
        return None