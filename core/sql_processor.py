import re
import os
import json
import logging
import core.agents as Agents

from paths import TEMPLATE_PATH
from services.db_client import DBClient

from utils.logging_utils import LoggingUtils

class SqlProcessor:
    def __init__(self):
        # self.db_client = db_client
        # self.llm_agent = llm_agent
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _normalize_query(self, query: str):
        """移除多余的空格并将 SQL 转为小写"""
        return re.sub(r'\s+', ' ', query).lower()

    def _extract_from_query(self, query: str):
        """从 SQL 查询中提取表名，支持子查询和别名"""
        tables = []
        
        # 正则匹配 FROM 和 JOIN 后面的表名或子查询（包括别名）
        pattern = r'(from|join)\s+(\([^\)]+\)|[^\s,;]+(?:\s+as\s+[^\s,;]+)?)'
        for match in re.findall(pattern, query):
            table = match[1]
            # 如果是子查询，提取括号内的查询并递归调用提取表名
            if table.startswith('('):
                subquery_tables = self._extract_from_query(table)
                tables.extend(subquery_tables)
            else:
                # 去除别名部分，仅保留实际表名
                table = table.split(' as ')[0]
                tables.append(table)
        
        return tables
    
    def extract_fields(self, query: str):
        """
        提取 SQL 查询中的字段列表，支持子查询和多个 SQL 查询
        """
        query = self._normalize_query(query)
        fields = []
        
        # 处理多条 SQL 查询语句
        for subquery in self._split_queries(query):
            # 匹配 SELECT 子句中的字段
            match = re.search(r'select\s+(.*?)\s+from', subquery)
            if match:
                fields_str = match.group(1)
                # 按照逗号分割字段，去除空格
                fields.extend([field.strip() for field in fields_str.split(',')])
        
        return fields

    def extract_tables(self, query: str):
        """
        提取 SQL 查询中的表名，支持子查询和多个 SQL 查询
        """
        query = self._normalize_query(query)
        tables = []
        
        # 处理多条 SQL 查询语句
        for subquery in self._split_queries(query):
            # 提取表名
            tables.extend(self._extract_from_query(subquery))
        
        return tables
    
    def _split_queries(self, query: str):
        """
        通过 ';' 分割多个 SQL 查询语句，并处理嵌套查询
        """
        queries = []
        depth = 0
        current_query = []
        
        # 遍历字符并根据分号分割 SQL 查询
        for char in query:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ';' and depth == 0:
                queries.append(''.join(current_query).strip())
                current_query = []
                continue
            current_query.append(char)
        
        if current_query:
            queries.append(''.join(current_query).strip())  # 最后一个查询
        
        return queries


