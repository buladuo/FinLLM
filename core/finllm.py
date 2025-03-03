from ast import Dict, List
import logging
import os

from tqdm import tqdm
from services.db_client import DBClient
from core.sql_processor import SqlProcessor
from core.prompt_manager import PromptManager
from core.entity_processor import EntityProcessor
from core.question_manager import QuestionManager
from core.table_locator import TableLocator
from core.yaml_table_manager import YamlTableManager
from core.templates_manager import TemplatesManager
from services.embedding_client import EmbeddingServiceFactory
from utils.logging_utils import LoggingUtils
from utils.field2sql import Field2SQL
from utils.construct_few_shots import ConstructFewShots


from paths import QUESTION_PATH,CONFIG_PATH,PROMPTS_PATH,QUESTION_PATH,YAML_DB_INFO_PATH,OUTPUT_PATH,TEMPLATE_PATH
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
        self._init_embedding_client()

        self.entity_processor = EntityProcessor(self.db_client,self.entity_recognition_agent)
        self.table_locator = TableLocator(self.question_classification_agent,self.table_locator_agent)
        self.sql_processor = SqlProcessor(
            self.entity_processor,
            self.db_table_manager,
            self.sql_reason_agent,
            self.sql_generator_agent,
            self.sql_regenerator_agent,
            self.sql_comparison_agent,
            self.db_client,
            self.config["global"].get('retries')
        )
        
        self.template_manager = TemplatesManager(self.embedding_client,TEMPLATE_PATH)
        self.fewshots_constructor = ConstructFewShots(self.template_manager)
        
    def _init_embedding_client(self):
        default_embedding = self.config["global"].get('default_embedding')
        embedding_config = self.config["embeddings"][default_embedding]
        self.embedding_client = EmbeddingServiceFactory.create_service(embedding_config,self.config["global"])
    
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
        self.question_expand_agent = self._init_agent('question_expand_model', Agents.QuestionExpandAgent, default_model)
        self.sql_comparison_agent = self._init_agent('sql_comparison_model', Agents.SQLComparisonAgent, default_model)
        self.sql_generator_agent = self._init_agent('sql_generator_model', Agents.SQLGeneratorAgent, default_model)
        self.sql_regenerator_agent = self._init_agent('sql_regenerator_model', Agents.SQLReGeneratorAgent, default_model)
        self.sql_reason_agent = self._init_agent('sql_reason_model', Agents.SQLReasonAgent, default_model)
        self.entity_reference_replacement_agent = self._init_agent('entity_reference_replacement_model', Agents.EntityReferenceReplacementAgent, default_model)
        

    def _init_agent(self, model_key, agent_class, default_model):
        model_name = self.config["global"].get(model_key, default_model)
        model_config = self.config["models"][model_name]
        self.logger.info("Initializing agent: %s with model: %s", agent_class.__name__, model_name)
        return agent_class(model_config, self.config["global"], self.prompt_manager)
    
    def _question_type(self,question:str,entity_infos:list):
        
        is_a = False
        is_us = False
        is_hk = False
        
        if "美股" in question:
            is_us = True
            return (is_a,is_hk,is_us)
        if "港股" in question:
            is_hk = True
            return (is_a,is_hk,is_us)
        if not entity_infos:
            return (True,is_hk,is_us)
        
        
        for entry in entity_infos:
            
            response, table_name = entry
            if 'hk_secumain' in table_name.lower():
                is_hk = True
            elif 'us_secumain' in table_name.lower():
                is_us = True
            else:
                is_a = True
        return (is_a,is_hk,is_us)
        
        
    def process_question(self,question:str, entity_info:Dict,is_hk = False,is_us = False):
        self.logger.info("Processing question: '%s' with entity_info: %s", question, entity_info)

        cot_example = self.fewshots_constructor.construct_cot_few_shots(self._question_without_entity(question,entity_info))
        cot_result = self.cot_agent.query([{'role':'user','content':str(question)}],'without_example',cot_example)
        
        for cot_item in cot_result:
            subquestoins = cot_item.get('subquestions',[])
            answers = {"question":question,"subquestions":[]}
            for subquestoin in subquestoins:
                
                all_info = []

                # 这里要对子问题的上下文引用进行处理
                if answers["subquestions"]:
                    rewrited_subquestion = self.entity_reference_replacement_agent.query([{'role':'user','content':str([{"contex":answers["subquestions"],"current_question":subquestoin['subquestion']}])}])
                    if isinstance(rewrited_subquestion,list) and rewrited_subquestion and rewrited_subquestion[0].get('rewrited_question'):
                        self.logger.info(f"Rewrited Question:\n{rewrited_subquestion}")
                        subquestoin['subquestion'] = rewrited_subquestion[0].get('rewrited_question')
                
                self.logger.info(f"Proccessing the question: {subquestoin['subquestion']}")
                
                db_example = self.fewshots_constructor.construct_class_name_few_shots(self._question_without_entity(subquestoin['subquestion'],entity_info))
                table_example = self.fewshots_constructor.construct_table_name_few_shots(self._question_without_entity(subquestoin['subquestion'],entity_info))
                
                
                for result in self.table_locator.get_table(subquestoin['subquestion'],is_hk=is_hk,is_us=is_us,db_example=db_example,table_example=table_example):
                    
                    table_info = self.db_table_manager.get_table_info(result['table_name'].lower())
                    if table_info is None:
                        continue
                    
                    infos = self.file2sql.get_all_info_source(table_info,entity_info,is_hk,is_us)
                    self.logger.info(f"InfoSource Can be: {infos}")
                    if infos :
                        table_info['externtion_annotation'].append({
                            'id':"inforsource可能获取的值",
                            "content":infos,
                            "explain":"注解：当题目中提到相关信息如年报、季度报、申万等等，你需要在生成sql的时候重点考虑这个字段的信息，比如提问第一季度xxx信息，那么你需要使用InfoSource进行限定筛选，此外对于第一季度的日期你不需要选择一个精确的日期了，选择日期在第一个季度内。这有助于派出无用信息此外，你需要区分InfoSource和InfoSourceCode，的区别，InfoSourceCode通常是一个编码，其取值通常在InfoSource的字段说明中详细介绍，InfoSource通常就是一字符串。"
                        }) 
                    all_info.append(table_info)
                sql_example = self.fewshots_constructor.construct_sql_few_shots(self._question_without_entity(subquestoin['subquestion'],entity_info))
                sql_query_result = self.sql_processor.get_sql_result(subquestoin['subquestion'],entity_info,all_info,sql_example,answers["subquestions"])
                
                answers["subquestions"].append({
                    "id":subquestoin['id'],
                    "subquestion": subquestoin['subquestion'],
                    "sql_query_result" : sql_query_result
                })
                
            self.logger.info(f"Answers: {json.dumps(answers,ensure_ascii=False,indent=4)}")
                
            # TODO 将结果整理成为答案
            answers_with_entity_info = answers
            answers_with_entity_info['entity_info'] = entity_info
            return answers_with_entity_info
            
            
        self.logger.warning(f"There are some error in cot result: {cot_result}")
        return None
    
    
    def process_item(self, question_id: int) -> Dict:
        LoggingUtils.update_logging_file(self.logging_config, question_id)
        self.logger.info("Processing question with id: %s", question_id)
        
        question_team = self.question_manager.get_question(question_id)
        entity_result = self.entity_processor.process_items(question_team.get_all_question())
        question_format = self._format_questions(question_team)
        is_a, is_hk, is_us = self._question_type(question_team.get_all_question(), entity_result)
        
        if not entity_result:
            entity_result = []
            
        for entry in entity_result:
            response, table_name = entry
            if 'hk_secumain' in table_name.lower() and is_hk:
                self.logger.info(f"This question is related to HK stock.")
                return self._handle_question_type(question_team, response, question_format, is_hk=True)
            if 'us_secumain' in table_name.lower() and is_us:
                self.logger.info(f"This question is related to US stock.")
                return self._handle_question_type(question_team, response, question_format, is_us=True)
            else:
                self.logger.info(f"This question is related to A stock.")
                return self._handle_question_type(question_team, response, question_format, is_a=True)

        if not entity_result:
            self.logger.info(f"This question is related to a stock for which no entity was found.")
            return self._handle_question_type(question_team, {}, question_format, is_a=True)

    
    def _format_questions(self, question_team) -> list:
        """格式化问题数据为要求的结构"""
        return [
            {"id": subquestion.get_id(), "question": subquestion.get_question()}
            for subquestion in question_team
        ]

    def _question_without_entity(self, question_str:str, entity_info:dict) -> str:
        """将问题中的字符串中的实体替换为xxx等无意义的字符"""
        question_cleaned = question_str
        if entity_info and entity_info.get('success',False) and entity_info.get('count') > 0 and entity_info.get('data'):
            for entity in entity_info.get('data'):
                # entity是一个字典，将字典中的value在question_str中替换为xxx，这样就可以保证问题中的实体影响相似度计算
                for key, value in entity.items():
                    question_cleaned = question_cleaned.replace(str(value), 'xxx')
        return question_cleaned

    def _handle_question_type(self, question_team, entity_result, question_format, is_a=False, is_hk=False, is_us=False):
        """处理不同类型的问题，减少重复代码"""
        result = self.process_question(question_team.get_all_question(), entity_result, is_hk=is_hk, is_us=is_us)
        
        # 初始请求
        request_data = [{
            'role': 'user',
            'content': f"这是整理好的子问题答案:{result}\n以下是我的请求问题:\n{question_format}"
        }]
        
        retries = 0
        
        while retries < self.config["global"].get('retries', 3):
            try:
                # 调用answer_rewrite_agent进行答案重写
                rewritten_answer = self.answer_rewrite_agent.query(request_data, prompt_id=3)
                request_data.append({
                    'role': 'assistant',
                    'content': f'这是重写后的答案,并确保答案保持正确的格式:\n```json{json.dumps(rewritten_answer,ensure_ascii=False,indent=4)}```\n'
                })
                # 将重写后的答案设置回相应的question_team
                for answer in rewritten_answer:
                    question_team.set_answer_by_id(answer.get("id"), answer.get("answer"))
                
                # 如果成功，跳出循环
                return rewritten_answer
            except Exception as e:
                # 捕获异常，将错误信息作为新的输入
                retries += 1
                error_message = f"在处理问题时发生错误: {str(e)},现在你需要修改错误,并保持正确的格式,并继续重写答案"
                request_data.append({
                    'role': 'user',
                    'content': error_message
                })
                if retries >= self.config["global"].get('retries', 3):
                    # 如果达到最大重试次数，记录错误并退出
                    self.logger.error(f"在处理问题时达到最大重试次数，最终错误: {str(e)}")
                    return None
    
    
    def save_result(self):
        save_path = os.path.join(OUTPUT_PATH, 'answer.json')
        self.question_manager.save_to_json(save_path)
    
    def get_total_num_questions(self):
        return self.question_manager.get_total_num_questions()
        
    def cot_questions(self):
        
        all_cot_questions = []
        for question in self.question_manager:
            cot_result = self.cot_agent.query([{'role':'user','content':str(question.get_all_question())}])
            if not isinstance(cot_result,list) and len(cot_result) and not isinstance(cot_result[0],dict):
                continue
            cot_result = cot_result[0]
            for subquestion in cot_result['subquestions']:
                subquestion['table_name'] = []
                subquestion['reason'] = ""
                subquestion['sql'] = ""
            all_cot_questions.append(cot_result)
        save_path = os.path.join(OUTPUT_PATH, 'cot_all_questions.json')
        with open(save_path, 'w', encoding='utf8') as f:
            json.dump(all_cot_questions, f, ensure_ascii=False, indent=4)
            
    def process_templates(self,question_id:int):
        LoggingUtils.update_logging_file(self.logging_config, question_id)
        self.sql_processor.generate_template(question_id)
        
    def question_expand(self):
        count = 0
        for question in tqdm(self.template_manager, desc="Processing questions", unit="question"):
            LoggingUtils.update_logging_file(self.logging_config, count)
            
            if isinstance(question, tuple):
                question = question[1]  # 假设字典在元组的第二个位置
                
            if not isinstance(question, dict):
                self.logger.error(f"Unexpected format for question: {question}")
                continue  # 跳过无效项
            del question["question_embedding"]
            # self.logger.info(f"Origin Question:\n {json.dumps(question,ensure_ascii=False, indent=4)}")
            entity_result = self.entity_processor.process_items(question["question"])
            tables = set()
            count += 1
            
            for subquestion in question["subquestions"]:
                del subquestion["sub_question_embedding"]
                for table in subquestion["table_name"]:
                    cleaned_table = table.strip("() ").lower()  
                    tables.add(cleaned_table)
            
            all_tables_info = []
            for table in tables:
                # 以 '.' 分割表名，并提取最后一部分
                table_name_parts = table.split('.')
                last_part = table_name_parts[-1]
                
                table_info = self.db_table_manager.get_table_info(last_part)
                all_tables_info.append(table_info)
            
            
            prompt = f"""
                1. 已查询的实体信息：{entity_result}
                2. 表信息: {all_tables_info}
                3. 样例问题: {question}
            """
            
            self.logger.info(f"{prompt}")
            result = self.question_expand_agent.query([{"role":"user","content":prompt}])
            # self.logger.info(f"{json.dumps(result,ensure_ascii=False, indent=4)}")
            
            try:
            
                if result and isinstance(result,list) and len(result) > 0:
                    output_path = os.path.join(OUTPUT_PATH, "question_expand.json")
                    
                    # 检查文件是否存在，如果存在则加载现有数据
                    if os.path.exists(output_path):
                        with open(output_path, 'r', encoding='utf-8') as file:
                            try:
                                existing_data = json.load(file)
                            except json.JSONDecodeError:
                                existing_data = []
                    else:
                        existing_data = []
                    
                    # 将每个 question_expand 写入到现有数据中
                    for question_expand in result:
                        existing_data.append(question_expand)  # 追加每个扩展的问题
                    
                    # 写入更新后的数据到文件
                    with open(output_path, 'w', encoding='utf-8') as file:
                        json.dump(existing_data, file, ensure_ascii=False, indent=4)
            except Exception as e:
                self.logger.error(f"An error occurred: {e}")