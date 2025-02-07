from sre_constants import SUCCESS
from venv import logger
from core import question_manager
from services.llm_client import LLMServiceFactory
from services.db_client import DBClient
from utils.logging_utils import LoggingUtils
from core.prompt_manager import PromptManager
from core.entity_processor import EntityProcessor
from core.question_manager import QuestionManager
import core.agents as Agents
from core.table_locator import TableLocator
from core.database_table_manager import DatabaseTableManager
from core.yaml_table_manager import YamlTableManager

from paths import CONFIG_PATH,PROMPTS_PATH,QUESTION_PATH,YAML_DB_INFO_PATH

import yaml
import json



config_path = CONFIG_PATH
with open(config_path, "r") as file:
    config = yaml.safe_load(file)

logging_config = config.get("logging", {})
LoggingUtils.setup_logging(logging_config)

# excel_path = './data/DataDict.xlsx'
# db_table_manager = DatabaseTableManager(excel_path)
db_table_manager = YamlTableManager(YAML_DB_INFO_PATH)

db_client = DBClient()


prompt_manager = PromptManager(PROMPTS_PATH)
question_manager = QuestionManager(QUESTION_PATH)

model_config = config["models"]['gpt-4o-mini']
print(f"\n测试模型: {model_config['name']}")
global_config = config["global"]

agents_config_manager = Agents.AgentsConfigManager(model_config,global_config,prompt_manager)
entity_reference_replacement_agent = Agents.EntityReferenceReplacementAgent()
answer_rewrite_agent = Agents.AnswerRewriteAgent()
cot_agent = Agents.CotAgent()
table_locator = TableLocator()
sql_generator = Agents.SQLGeneratorAgent()
sql_regenerator = Agents.SQLReGeneratorAgent()



QUESTION_ID = 18


question_team = question_manager.get_question(QUESTION_ID-1)

entity_processor = EntityProcessor()
entity_result = entity_processor.process_items(question_team.get_all_question())
for entry in entity_result:
    response, db_name = entry
    if response['count'] == 0:
        continue

    print(json.dumps({"Database": db_name, "Response": response}, ensure_ascii=False, indent=4))
    entity_data = response['data']

    db_name_lower = db_name.lower()
    if 'hk' in db_name_lower:
        context = {
            "context": [],
            "current_question": ""
        }
        
        for question in question_team:
            original_question = question
            question_str = question.get_question()  # 修改为 question_str 以保持一致性
            
            if len(context['context']) > 0:
                context['current_question'] = question_str
                entity_reference_replacement_result = entity_reference_replacement_agent.query(context)
                if isinstance(entity_reference_replacement_result, list) and len(entity_reference_replacement_result) > 0:
                    question_str = entity_reference_replacement_result[0].get("rewrited_question", question_str)
                    
            cot_result = cot_agent.query(question_str)[0]

            answers = {}
            answers['question'] = cot_result['question']
            answers['subquestions'] = []
            
            for subquestion in cot_result['subquestions']:
                all_info = []
                for result in table_locator.get_hk_table(subquestion):  # 使用 get_hk_table
                    table_info = db_table_manager.get_table_info(result['table_name'].lower())
                    all_info.append(table_info)
                logger.info(f"查询到的表的信息:{all_info}")
                sql = sql_generator.query(subquestion, data=response['data'], info=all_info)
                result = db_client.query(sql)
                subquestion['sql_result'] = result['data'] if result['success'] else []
                subquestion['sql_result_count'] = result['count'] if result['success'] else 0
                subquestion['sql'] = sql if result['success'] else ""
                answers['subquestions'].append(subquestion)
            
            final_result = answer_rewrite_agent.query([answers])
            print(final_result)
            break
        
    elif 'us' in db_name_lower:
        context = {
            "context": [],
            "current_question": ""
        }
        
        for question in question_team:
            original_question = question
            question_str = question.get_question()  # 修改为 question_str 以保持一致性
            
            if len(context['context']) > 0:
                context['current_question'] = question_str
                entity_reference_replacement_result = entity_reference_replacement_agent.query(context)
                if isinstance(entity_reference_replacement_result, list) and len(entity_reference_replacement_result) > 0:
                    question_str = entity_reference_replacement_result[0].get("rewrited_question", question_str)
                    
            cot_result = cot_agent.query(question_str)[0]

            answers = {}
            answers['question'] = cot_result['question']
            answers['subquestions'] = []
            
            for subquestion in cot_result['subquestions']:
                all_info = []
                for result in table_locator.get_us_table(subquestion):  # 使用 get_us_table
                    table_info = db_table_manager.get_table_info(result['table_name'].lower())
                    all_info.append(table_info)
                logger.info(f"查询到的表的信息:{all_info}")
                sql = sql_generator.query(subquestion, data=response['data'], info=all_info)
                result = db_client.query(sql)
                subquestion['sql_result'] = result['data'] if result['success'] else []
                subquestion['sql_result_count'] = result['count'] if result['success'] else 0
                subquestion['sql'] = sql if result['success'] else ""
                answers['subquestions'].append(subquestion)
            
            final_result = answer_rewrite_agent.query([answers])
            print(final_result)
            break

        pass
    else:
        context = {
            "context":[],
            "current_question":""
        }
        
        for question in question_team:
            original_question = question
            question_str = question.get_question()
            
            if len(context['context']) > 0:
                context['current_question'] = question_str
                entity_reference_replacement_result = entity_reference_replacement_agent.query(context)
                if isinstance(entity_reference_replacement_result,list) and len(entity_reference_replacement_result)>0:
                    question_str = entity_reference_replacement_result[0].get("rewrited_question",question_str)
            cot_result = cot_agent.query(question_str)[0]

            answers = {}
            answers['question'] = cot_result['question']
            answers['subquestions'] = []
            for subquestion in cot_result['subquestions']:
                all_info = []
                for result in table_locator.get_table(subquestion):
                    table_info = db_table_manager.get_table_info(result['table_name'].lower())
                    all_info.append(table_info)
                logger.info(f"查询到的表的信息:{all_info}")
                sql = sql_generator.query(subquestion,data=response['data'],info=all_info)
                sql_result = db_client.query(sql)
                
                while sql_result['success'] == False:
                    sql=  sql_regenerator.query(subquestion,data=response['data'],info=all_info,SQL=sql,error_detail=sql_result['detail'])
                    sql_result = db_client.query(sql)
                
                subquestion['sql_result'] = sql_result['data'] if sql_result['success'] else []
                subquestion['sql_result_count'] = sql_result['count'] if sql_result['success'] else 0
                subquestion['sql'] = sql if sql_result['success'] else ""
                answers['subquestions'].append(subquestion)
                print(f"subquestion:\n\t{subquestion['subquestion']}")
                # print(f"sql_result:{subquestion['sql_result']}")
                print(f"sql:\n\t{subquestion['sql']}")
            final_result = answer_rewrite_agent.query([answers])
            print(json.dumps(final_result, indent=4,ensure_ascii=False))
            context['context'].append({
                "id": original_question.get_id(),
                "question": original_question.get_question(),
                "answer": final_result[0]['answer'] if len(final_result)>0 else ""
            })
            
        pass
    




