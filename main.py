from venv import logger
from services.llm_client import LLMServiceFactory
from services.db_client import DBClient
from utils.logging_utils import LoggingUtils
from core.prompt_manager import PromptManager
from core.entity_processor import EntityProcessor
import core.agents as Agents
from core.table_locator import TableLocator
from core.database_table_manager import DatabaseTableManager

from paths import CONFIG_PATH,PROMPTS_PATH

import yaml
import json



config_path = CONFIG_PATH
with open(config_path, "r") as file:
    config = yaml.safe_load(file)

logging_config = config.get("logging", {})
LoggingUtils.setup_logging(logging_config)

excel_path = './data/DataDict.xlsx'
db_table_manager = DatabaseTableManager(excel_path)

db_client = DBClient()


prompt_manager = PromptManager(PROMPTS_PATH)
model_config = config["models"]['gpt-4o-mini']
global_config = config["global"]
agents_config_manager = Agents.AgentsConfigManager(model_config,global_config,prompt_manager)

question = "600872的全称、A股简称、法人、法律顾问、会计师事务所及董秘是？"

entity_processor = EntityProcessor()

print(f"\n测试模型: {model_config['name']}")
result = entity_processor.process_items(question)
data = []
for entry in result:
    response, db_name = entry
    if response['count'] >0:
        data.append(response['data'])
    print(json.dumps({"Database": db_name, "Response": response}, ensure_ascii=False, indent=4))

cot_agent = Agents.CotAgent()
table_locator = TableLocator()
sql_generator = Agents.SQLGeneratorAgent()

for subquestion in cot_agent.query(question)[0]['subquestions']:

    result = table_locator.get_table(subquestion)[0]
    table_description = db_table_manager.get_table_description_by_name(result['table_name'])
    logger.info(f"Processing subquestion:{subquestion}")
    table_info = db_table_manager.get_table_info_by_name(result['table_name'])
    result = sql_generator.query(subquestion,data=data,table_desc=table_description,table_info=table_info)
    
    result = db_client.query(result)
    
    print(result)

# TODO
# 重大事项相关需要涉及到多个表格
