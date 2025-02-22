from abc import ABC, abstractmethod
from ast import List
from tkinter import NO
from unittest import result

from tenacity import retry
from services.llm_client import LLMServiceFactory
from utils.json_extractor import JsonExtractor
from utils.sql_extractor import SqlExtractor
import logging

class BaseAgent(ABC):
    def __init__(self, model_config, global_config, prompt_manager):
        self.model_name = model_config['name']
        self.model_config = model_config
        self.global_config = global_config
        self.prompt_manager = prompt_manager
        
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.service = LLMServiceFactory.create_service(self.model_config, self.global_config)
        self.json_extractor = JsonExtractor()
        self.sql_extractor = SqlExtractor()
        
        self.retries = 3

    @abstractmethod
    def query(self, question):
        pass

    def _handle_json_response(self, response)->list:
        extract_response = self.json_extractor.extract_json(response, model_name=self.model_name)
        if not extract_response or not isinstance(extract_response, list):
            self.logger.warning("Received empty or invalid JSON response, attempting to repair.")
            system_prompt = self.prompt_manager.get_prompt('json_repair')['content']
            messages = [{"role": "system", "content": str(system_prompt)},
                        {"role": "user", "content": str(response)}]
            extract_response = self.service.query(messages)
            repaired_response = self.json_extractor.extract_json(extract_response, model_name=self.model_name)
            if not repaired_response or not isinstance(repaired_response, list):
                self.logger.warning("Repair attempt also returned empty or invalid response.")
                return []
            return repaired_response
        
        return extract_response

    def _query_and_extract_json(self, prompt_type, message, prompt_id=None):
        system_prompt = self.prompt_manager.get_prompt(prompt_type, prompt_id)['content']
        messages = [{"role": "system", "content": str(system_prompt)}]
        messages.extend(message)
        self.logger.debug(f"Send request: {messages}.")
        
        response = self.service.query(messages)
        self.logger.info(f"Received response: \n{response}.")
        return self._handle_json_response(response)
    
    def _query_with_extract_json(self, prompt_type, message, prompt_id=None):
        system_prompt = self.prompt_manager.get_prompt(prompt_type, prompt_id)['content']
        messages = [{"role": "system", "content": str(system_prompt)}]
        messages.extend(message)
        self.logger.debug(f"Send request: {messages}.")
        
        response = self.service.query(messages)
        self.logger.info(f"Received response: \n{response}.")
        return (response,self._handle_json_response(response))

    def _handle_sql_response(self, response):
        extract_response = self.sql_extractor.extract_sql(response, model_name=self.model_name)

        if not extract_response:
            self.logger.warning("Received empty SQL response, attempting to repair.")
            system_prompt = self.prompt_manager.get_prompt('sql_repair')['content']
            messages = [{"role": "system", "content": str(system_prompt)},
                        {"role": "user", "content": str(response)}]
            extract_response = self.service.query(messages)
            repaired_response = self.sql_extractor.extract_sql(extract_response, model_name=self.model_name)
            if not repaired_response:
                self.logger.warning("Repair attempt also returned empty response.")
                return []
            return repaired_response
        
        return extract_response

    def _query_and_extract_sql(self, prompt_type, message, prompt_id=None):
        system_prompt = self.prompt_manager.get_prompt(prompt_type, prompt_id)['content']
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(message)
        self.logger.debug(f"Send request: {messages}.")
        
        response = self.service.query(messages)
        self.logger.info(f"Received response: {response}.")
        return self._handle_sql_response(response)
    

class EntityRecognitionAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        return self._query_and_extract_json('entity_recognition', message, prompt_id)


class QuestionClassificationAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        return self._query_and_extract_json('db_cls', message, prompt_id)
    
    
class JsonFormatRepairAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        return self._query_and_extract_json('json_repair', message, prompt_id)


class SQLFormatRepairAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        return self._query_and_extract_sql('sql_repair', message, prompt_id)

    
class AnswerRewriteAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        # self.logger.info(f"Your message:{message}")
        
        return self._query_and_extract_json('answer_rewrite', message, prompt_id)
    
    
class EntityReferenceReplacementAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        return self._query_and_extract_json('entity_reference_replacement', message, prompt_id)

class TableLocatorAgent(BaseAgent):
    def query(self, message, type, prompt_id=None):
        
        result = self._query_and_extract_json(type, message, prompt_id)
        retry_times = 0
        while not result and retry_times < self.retries:
            result = self._query_and_extract_json(type, message, prompt_id)
            retry_times += 1
        
        return result


class SQLGeneratorAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        return self._query_and_extract_sql('sql_generator', message, prompt_id)
    def query_json_format(self, message, prompt_id='json_format'):
        
        result = self._query_and_extract_json('sql_generator', message, prompt_id)
        
        if prompt_id == 'json_format':
            if not isinstance(result,list):
                self.logger.warning("Query result is not json format!")
                return []
        return result
    

class SQLReGeneratorAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        return self._query_and_extract_sql('sql_regenerator', message, prompt_id)
    
class SQLReasonAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        return self._query_with_extract_json('sql_reason', message, prompt_id)

class CotAgent(BaseAgent):
    def query(self, message, prompt_id=None):
        
        cot_result = self._query_and_extract_json('cot', message, prompt_id)
        if not isinstance(cot_result,list):
            return []
        
        id = 1
        finall_cot  = {
            "question": "",
            "subquestions": []
        }
        
        for cot_item in cot_result:
            finall_cot["question"] += cot_item['question']
            for subquestion in cot_item['subquestions']:
                finall_cot['subquestions'].append({
                    "id": id,
                    "subquestion": subquestion['subquestion']
                })
                id += 1
        
        return [finall_cot]

