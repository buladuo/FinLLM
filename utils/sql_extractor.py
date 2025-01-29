import re

class SqlExtractor:
    def __init__(self):
        # 正则表达式匹配以 ```sql``` 开头和结尾的 SQL 语句
        self.sql_pattern = r'```sql\s*(.*?)\s*```'
        # 正则表达式匹配所有的 SQL 语句（简单匹配 SELECT, INSERT, UPDATE, DELETE）
        self.fallback_pattern = r'(SELECT|INSERT|UPDATE|DELETE).*?;'

    def extract_sql(self, text: str, model_name=None):
        """从输入文本中提取 SQL 语句"""
        
        text = text.replace('\n', ' ')
        text = self.preprocess(text, model_name)
        
        # 尝试匹配 ```sql``` 块
        match = re.search(self.sql_pattern, text, re.DOTALL)
        if match:
            sql_str = match.group(1)
            return sql_str.strip()
        
        # 尝试匹配所有可能的 SQL 语句
        fallback_matches = re.findall(self.fallback_pattern, text, re.DOTALL)
        if fallback_matches:
            return fallback_matches[0].strip()
        
        # 未找到匹配的 SQL 语句
        return None
    
    def preprocess(self, text, model_name=None):
        # 如果没有提供模型名称，直接返回原始文本
        if model_name is None:
            return text
        
        if model_name in ['glm-4-zero', 'glm-4-think']:
            match = re.search(r'\[思考结束\](.*)', text, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return text