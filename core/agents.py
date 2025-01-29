from abc import ABC, abstractmethod
from tkinter import NO
from services.llm_client import LLMServiceFactory
from utils.json_extractor import JsonExtractor
from utils.sql_extractor import SqlExtractor
import logging

# 配置管理类
class AgentsConfigManager:
    _instance = None
    _initialized = False  # 用于标记是否已经初始化

    def __new__(cls, *args, **kwargs):
        # 确保只有一个实例被创建
        if cls._instance is None:
            cls._instance = super(AgentsConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_config=None, global_config=None, prompt_manager=None):
        # 只在第一次创建实例时进行初始化
        if not self._initialized:
            if model_config is not None and global_config is not None and prompt_manager is not None:
                self.model_name = model_config['name']
                self.model_config = model_config
                self.global_config = global_config
                self.prompt_manager = prompt_manager
                self._initialized = True
            else:
                raise ValueError("Insufficient parameters to initialize AgentsConfigManager")

    @classmethod
    def get_instance(cls):
        return cls._instance



class BaseAgent(ABC):
    def __init__(self):
        config = AgentsConfigManager()
        self.model_name = config.model_name
        self.model_config = config.model_config
        self.prompt_manager = config.prompt_manager
        self.global_config = config.global_config
        
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def query(self, question):
        pass


class EntityRecognitionAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.service = LLMServiceFactory.create_service(self.model_config, self.global_config)
        self.json_extractor = JsonExtractor()
        self.json_repair_agent = JsonFormatRepairAgent()

    def query(self, question, prompt_id=None):
        prompt = self.prompt_manager.get_prompt('entity_recognition', prompt_id)['content']
        response = self.service.query(prompt, question)
        self.logger.info(f"Received response: {response}.")
        extract_response = self.json_extractor.extract_json(response, model_name=self.model_name)
        # 如果返回的是空字典，则调用JsonFormatRepairAgent进行修复
        if not extract_response:  # response是{}
            self.logger.warning("Received empty JSON response, attempting to repair.")
            extract_response = self.json_repair_agent.query(response)
            
        return extract_response



class QuestionClassificationAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.service = LLMServiceFactory.create_service(self.model_config, self.global_config)
        self.json_extractor = JsonExtractor()
        self.json_repair_agent = JsonFormatRepairAgent()

    def query(self, question, prompt_id=None):
        prompt = self.prompt_manager.get_prompt('db_cls', prompt_id)['content']
        response = self.service.query(prompt, question)
        self.logger.info(f"Received response: {response}.")
        extract_response = self.json_extractor.extract_json(response, model_name=self.model_name)
        # 检查提取的响应是否为空
        if not extract_response:  # 如果 extract_response 为 []
            self.logger.warning("Received empty JSON response, attempting to repair.")
            extract_response = self.json_repair_agent.query(response)
            
            # 再次检查修复后的响应是否为空
            if not extract_response:  # 如果仍然为空
                self.logger.error("Repair attempt also returned empty response.")
                return []  # 或者根据需要返回一个合适的默认值

        return extract_response


class JsonFormatRepairAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.service = LLMServiceFactory.create_service(self.model_config, self.global_config)
        self.json_extractor = JsonExtractor()

    def query(self, question,prompt_id=None):
        prompt = self.prompt_manager.get_prompt('json_repair', prompt_id)['content']  # 提示说明
        response = self.service.query(prompt, question)  # 根据问题生成修复响应
        self.logger.info(f"Received repair response: {response}.")
        repaired_response = self.json_extractor.extract_json(response, model_name=self.model_name)
        return repaired_response

class SQLFormatRepairAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.service = LLMServiceFactory.create_service(self.model_config, self.global_config)
        self.sql_extractor = SqlExtractor()

    def query(self, question,prompt_id=None):
        prompt = self.prompt_manager.get_prompt('json_repair', prompt_id)['content']  # 提示说明
        response = self.service.query(prompt, question)  # 根据问题生成修复响应
        self.logger.info(f"Received repair response: {response}.")
        repaired_response = self.sql_extractor.extract_sql(response, model_name=self.model_name)
        return repaired_response

class TableLocatorAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.service = LLMServiceFactory.create_service(self.model_config, self.global_config)
        self.json_extractor = JsonExtractor()
        self.json_repair_agent = JsonFormatRepairAgent()

    def query(self, question, type, prompt_id=None):
        prompt = self.prompt_manager.get_prompt(type, prompt_id)['content']  # 提示说明
        database_name = self.prompt_manager.get_prompt(type, prompt_id)['database_name']
        response = self.service.query(prompt, question)
        self.logger.info(f"Received response: {response}.")
        
        # 提取 JSON 响应
        extract_response = self.json_extractor.extract_json(response, model_name=self.model_name)
        
        # 检查提取的响应是否为空
        if not extract_response:  # 如果 extract_response 为 []
            self.logger.warning("Received empty JSON response, attempting to repair.")
            extract_response = self.json_repair_agent.query(response)
            
            # 再次检查修复后的响应是否为空
            if not extract_response:  # 如果仍然为空
                self.logger.error("Repair attempt also returned empty response.")
                return []  # 或者根据需要返回一个合适的默认值
        return extract_response

    
class SQLGeneratorAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.service = LLMServiceFactory.create_service(self.model_config, self.global_config)
        self.sql_extractor = SqlExtractor()
        self.sql_repair_agent = SQLFormatRepairAgent()

    def query(self, question, prompt_id=None, data = None, table_desc=None,table_info=None):
        prompt = self.prompt_manager.get_prompt('sql_generator', prompt_id)['content']
        
        question =  f"{question}\n已知信息：{data}\n表描述：{table_desc}\n表信息：{table_info}"
        
        self.logger.info(question)
        
        response = self.service.query(prompt, question)
        self.logger.info(f"Received response: {response}.")
        extract_response = self.sql_extractor.extract_sql(response, model_name=self.model_name)
        if not extract_response:  # response是{}
            self.logger.warning("Received empty JSON response, attempting to repair.")
            extract_response = self.sql_repair_agent.query(response)
        return extract_response

class CotAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.service = LLMServiceFactory.create_service(self.model_config, self.global_config)
        self.json_extractor = JsonExtractor()
        self.json_repair_agent = JsonFormatRepairAgent()

    def query(self, question, prompt_id=None):
        prompt = self.prompt_manager.get_prompt('cot', prompt_id)['content']
        response = self.service.query(prompt, question)
        self.logger.info(f"Received response: {response}.")
        extract_response = self.json_extractor.extract_json(response, model_name=self.model_name)
        if not extract_response:  # response是{}
            self.logger.warning("Received empty JSON response, attempting to repair.")
            extract_response = self.json_repair_agent.query(response)  # 尝试修复
        return extract_response
