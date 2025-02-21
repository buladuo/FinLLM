
import logging

import yaml
from attr import fields_dict
# from utils.logging_utils import LoggingUtils
from services.db_client import DBClient
from paths import QUESTION_PATH,CONFIG_PATH,PROMPTS_PATH,QUESTION_PATH,YAML_DB_INFO_PATH,OUTPUT_PATH
from utils.code2name import Code2Name

def test():
    config_path = CONFIG_PATH
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)
    db_client = DBClient(config['database'])
    logging_config = config.get("logging", {})
    # LoggingUtils.setup_logging(logging_config)
    # 测试数据
    test_data = [
        {
            'success': True,
            'count': 1,
            'data': [{'InnerCode': 199617}]
        },
        {
            'success': True,
            'count': 1,
            'data': [{'CompanyCode': 165649}]
        },
        {
            'success': True,
            'count': 1,
            'data': [{'SecuCode': 600956}]
        },
        {
            'success': True,
            'count': 1,
            'data': [{'securitycode': '006614'}]
        }
    ]

    # 实例化处理器
    processor = Code2Name(db_client)

    # 遍历测试数据并进行处理
    for i, data in enumerate(test_data):
        print(f"Testing case {i + 1}:")
        processed_result = processor.process(data)
        print(processed_result)
        print('-' * 30)

if __name__ == "__main__":
    
    test()