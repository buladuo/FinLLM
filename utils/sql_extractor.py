import re
import logging

class SqlExtractor:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        # 正则表达式匹配以 ```sql``` 开头和结尾的 SQL 语句
        self.sql_pattern = r'```sql\s*(.*?)\s*```'
        # 正则表达式匹配所有的 SQL 语句（简单匹配 SELECT, INSERT, UPDATE, DELETE）
        self.fallback_pattern = r'(SELECT|INSERT|UPDATE|DELETE).*?;'

    def extract_sql(self, text: str, model_name=None):
        """从输入文本中提取 SQL 语句"""
        self.logger.debug("Starting SQL extraction.")
        
        if not isinstance(text, str):
            self.logger.error("Input text must be a string.")
            return None
        
        text = text.replace('\n', ' ')
        
        # 尝试匹配 ```sql``` 块
        match = re.search(self.sql_pattern, text, re.DOTALL)
        if match:
            sql_str = match.group(1)
            self.logger.info(f"Found SQL block: {sql_str.strip()}")
            return sql_str.strip()
        
        # 尝试匹配所有可能的 SQL 语句
        fallback_matches = re.findall(self.fallback_pattern, text, re.DOTALL)
        if fallback_matches:
            self.logger.info(f"Found fallback SQL statements: {fallback_matches}")
            return fallback_matches[0].strip()
        
        # 未找到匹配的 SQL 语句
        self.logger.warning("No matching SQL statements found.")
        return None
    