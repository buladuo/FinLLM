import re
import json
import logging


class JsonExtractor:
    def __init__(self):
        # 正则表达式匹配以 ```json``` 开头和结尾的 JSON 字符串
        self.json_pattern = r'```json\s*(.*?)\s*```'
        # 正则表达式匹配所有的 [xxx] 字符串
        self.fallback_pattern = r'\[.*?\]'
        self.logger = logging.getLogger(self.__class__.__name__)

    def extract_json(self, text: str, model_name=None):
        """从输入文本中提取 JSON 字符串"""
        self.logger.debug(f"开始提取 JSON 数据，输入文本: {text}")
        
        text = text.replace('\n', ' ')
        text = self.preprocess(text, model_name)
        
        # 尝试匹配 ```json [{xxx}] ``` 格式的 JSON 块
        match = re.search(self.json_pattern, text, re.DOTALL)
        if match:
            json_str = match.group(1)
            self.logger.info(f"找到 ```json [xxx] ``` 格式的 JSON 块，内容: {json_str}")
            try:
                # 尝试将匹配的字符串转换为 JSON
                json_data = json.loads(json_str)
                self.logger.info("成功解析 JSON 数据")
                return json_data
            except json.JSONDecodeError as e:
                self.logger.error(f"无法解析 JSON 数据: {e}")
                return None
        
        # 尝试匹配所有的 [xxx] 字符串
        fallback_matches = re.findall(self.fallback_pattern, text)
        if fallback_matches:
            self.logger.info(f"找到备用的 JSON 数据块，内容: {fallback_matches}")
            for fallback_json_str in fallback_matches:
                try:
                    json_data = json.loads(fallback_json_str)
                    self.logger.info("成功解析备用的 JSON 数据")
                    return json_data
                except json.JSONDecodeError as e:
                    self.logger.error(f"无法解析备用的 JSON 数据: {fallback_json_str}, 错误: {e}")
                    continue
        
        # 未找到匹配的 JSON
        self.logger.warning("未找到匹配的 JSON 数据")
        return []
    
    def preprocess(self, text, model_name=None):
        # 如果没有提供模型名称，直接返回原始文本
        if model_name is None:
            self.logger.debug("未提供模型名称，跳过预处理")
            return text
        
        if model_name in ['glm-4-zero', 'glm-4-think']:
            self.logger.debug(f"处理模型: {model_name}")
            match = re.search(r'\[思考结束\](.*)', text, re.DOTALL)
            if match:
                processed_text = match.group(1).strip()
                self.logger.debug(f"预处理后的文本: {processed_text}")
                return processed_text
        
        self.logger.debug("未匹配到预处理规则，返回原始文本")
        return text
