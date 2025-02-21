from ast import Dict, List
from email import utils
from sre_constants import SUCCESS
import logging
import os
from typing import final
from core import question_manager
from services.llm_client import LLMServiceFactory
from services.db_client import DBClient
from utils.logging_utils import LoggingUtils
from utils.field2sql import Field2SQL
from core.prompt_manager import PromptManager
from core.entity_processor import EntityProcessor
from core.question_manager import QuestionManager
from core.table_locator import TableLocator
from core.database_table_manager import DatabaseTableManager
from core.yaml_table_manager import YamlTableManager


from paths import QUESTION_PATH,CONFIG_PATH,PROMPTS_PATH,QUESTION_PATH,YAML_DB_INFO_PATH,OUTPUT_PATH
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

    def _init_agent(self, model_key, agent_class, default_model):
        model_name = self.config["global"].get(model_key, default_model)
        model_config = self.config["models"][model_name]
        self.logger.info("Initializing agent: %s with model: %s", agent_class.__name__, model_name)
        return agent_class(model_config, self.config["global"], self.prompt_manager)
    
    
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
        
    def process_question(self,question:str, entity_info:Dict,is_us = False,is_hk = False):
        self.logger.info("Processing question: '%s' with entity_info: %s", question, entity_info)

        cot_result = self.cot_agent.query([{'role':'user','content':str(question)}])
        for cot_item in cot_result:
            subquestoins = cot_item.get('subquestions',[])
            answers = {"question":question,"subquestions":[]}
            for subquestoin in subquestoins:
                self.logger.info(f"Proccessing the question: {subquestoin['subquestion']}")
                all_info = []
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
    
    
    def process_item(self,question_id:int)->Dict:
        question_team = self.question_manager.get_question(question_id)
        entity_result = self.entity_processor.process_items(question_team.get_all_question())
        question_format = []
        for subquestion in question_team:
            question_format.append({
                "id": subquestion.get_id(),
                "question":subquestion.get_question()
            })
        if not entity_result:
            self.logger.info("这是一个A股题目，但没有查询到相关的信息")
            result = self.process_question(
                            question_team.get_all_question(),
                            {}
                        )
            result = self.answer_rewrite_agent.query(
                [{
                    'role':"user",
                    'content':f"\是整理好的子问题答案:{result}\n以下是我的请求问题:\n{question_format}"
                }],
                prompt_id=3
            )
            for answer in result:
                question_team.set_answer_by_id(answer.get("id"),answer.get("answer"))
        else:
            for entry in entity_result:
                response, table_name = entry
                
                if 'hk_secumain' in table_name.lower():
                    
                
                    response['question_type'] = 'hk'
                    self.logger.info(f"这是一个港股题目")
                    result = self.process_question(
                            question_team.get_all_question(),
                            response,
                            is_hk=True
                        )
                    result = self.answer_rewrite_agent.query(
                        [{
                            'role':'user',
                            'content':f"\n这是整理好的子问题答案:{result}\n以下是我的请求问题:\n{question_format}"
                        }],
                        prompt_id=3
                    )
                    for answer in result:
                        question_team.set_answer_by_id(answer.get("id"),answer.get("answer"))
                elif 'us_secumain' in table_name.lower():
                    
                    
                    
                    response['question_type'] = 'us'
                    self.logger.info(f"{response['question_type']}")
                    result = self.process_question(
                            question_team.get_all_question(),
                            response,
                            is_us=True
                        )
                    result = self.answer_rewrite_agent.query(
                        [{
                            'role':'user',
                            'content':f"这是整理好的子问题答案:{result}\n以下是我的请求问题:\n{question_format}"
                        }],
                        prompt_id=3
                    )
                    for answer in result:
                        question_team.set_answer_by_id(answer.get("id"),answer.get("answer"))
                else:
                    response['question_type'] = 'a'
                    self.logger.info(f"这是一个A股题目")
                    result = self.process_question(
                            question_team.get_all_question(),
                            response
                        )
                    result = self.answer_rewrite_agent.query(
                        [{
                            'role':'user',
                            'content':f"这是整理好的子问题答案:{result}\n以下是我的请求问题:\n{question_format}"
                        }],
                        prompt_id=3
                    )
                    for answer in result:
                        question_team.set_answer_by_id(answer.get("id"),answer.get("answer"))
                    
                    # break
    
    def save_result(self):
        save_path = os.path.join(OUTPUT_PATH, 'answer.json')
        self.question_manager.save_to_json(save_path)
        
        
    def cot_questions(self):
        
        all_cot_questions = []
        for question in self.question_manager:
            cot_result = self.cot_agent.query([{'role':'user','content':str(question.get_all_question())}])
            if not isinstance(cot_result,list) and len(cot_result) and not isinstance(cot_result[0],dict):
                continue
            cot_result = cot_result[0]
            for subquestion in cot_result['subquestions']:
                subquestion['table_name'] = ""
                subquestion['reason'] = ""
                subquestion['sql'] = ""
            all_cot_questions.append(cot_result)
        save_path = os.path.join(OUTPUT_PATH, 'cot_all_questions.json')
        with open(save_path, 'w', encoding='utf8') as f:
            json.dump(all_cot_questions, f, ensure_ascii=False, indent=4)
