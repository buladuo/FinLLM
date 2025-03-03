from itertools import count
import os
import json
import uuid
import logging


import numpy as np

from tqdm import tqdm
from core.agents import QuestionExpandAgent
from services.embedding_client import OpenAIEmbeddingService

from collections import deque

class TemplatesManager:
    def __init__(self, embedding_client: OpenAIEmbeddingService, templates_path: list):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.embedding_client = embedding_client
        self.templates = {}
        
        self.load_templates(templates_path)
        
    def load_templates(self, templates_path):
        for path in tqdm(templates_path, desc="加载模板文件"):
            if os.path.exists(path):
                with open(path, encoding='utf8') as f:
                    templates = json.load(f)
                    for template in tqdm(templates, desc="处理模板", leave=False):
                        unique_id = self._generate_unique_id()
                        template_with_embedding = self._compute_embedding(template)
                        self.add_template(unique_id, template_with_embedding)
            else:
                self.logger.error(f"模板文件 {path} 不存在。")
                raise FileNotFoundError(f"模板文件 {path} 不存在。")
            
    
    def get_topk_questions(self, question_str) -> list:
        """
        根据问题选topk最相似的问题
        """
        if not question_str:
            return []

        question_embedding = self.embedding_client.get_embeddings([question_str])[0]
        similarities = []

        for template_id, template in self.templates.items():
            similarity = self._cosine_similarity(question_embedding, template['question_embedding'])
            similarities.append((template_id, similarity))

        topk_similarities = sorted(similarities, key=lambda x: x[1], reverse=True)
        return topk_similarities

    
    def get_topk_subquestions(self, question_str: str) -> list:
        """
        根据问题选择topk最相似的子问题
        """
        if not question_str:
            return []

        question_embedding = self.embedding_client.get_embeddings([question_str])[0]
        similarities = []

        for template_id, template in self.templates.items():
            for subquestion in template['subquestions']:
                subquestion_embedding = subquestion['sub_question_embedding']
                subquestion_id = subquestion['id']
                similarity = self._cosine_similarity(question_embedding, subquestion_embedding)
                similarities.append((template_id, subquestion_id, similarity))

        # 按相似度排序，返回前topk
        topk_similarities = sorted(similarities, key=lambda x: x[2], reverse=True)
        return topk_similarities

    def get_topk_questions_table_names(self, question_str: str, topk=5) -> list:
        """
        根据问题选出最相似的topk问题并返回每个问题的表名集合
        """
        examples = self.get_topk_questions(question_str)
        final_examples = []
        counter = 0

        for template_id, similarity in examples:
            counter += 1
            if counter > topk:
                break
            tables = []
            for subquestion in self.templates[template_id]['subquestions']:
                tables = list(set(tables + subquestion['table_name']))  # 先合并，再去重
            final_examples.append(
                {
                    'question': self.templates[template_id]['question'],
                    'tables_name': tables  # 转换为list
                }
            )
        return final_examples
    
    def get_topk_subquestions_table_names(self,question_str: str, topk=5) -> list:
        examples = self.get_topk_subquestions(question_str)
        final_examples = []
        counter = 0
        for template_id,subquestion_id, similarity in examples:

            for subquestion in self.templates[template_id]['subquestions']:
                if subquestion_id == subquestion['id']: # 确保表名为字符串
                    if not subquestion['table_name']:
                        continue
                    counter += 1
                    if counter > topk:
                        break
                    final_examples.append(
                        {
                            'question': subquestion['subquestion'],
                            'tables_name': list(subquestion['table_name'])  # 转换为list
                        }
                    )
        return final_examples
    
    def get_topk_questions_cot(self, question_str: str, topk=5) -> list:
        """
        根据问题选出最相似的topk问题并返回COT格式
        """
        examples = self.get_topk_questions(question_str)
        final_examples = []
        counter = 0

        for template_id, similarity in examples:
            counter += 1
            if counter > topk:
                break
            cot = {
                "question": self.templates[template_id]['question'],
                "subquestions": []
            }
            for subquestion in self.templates[template_id]['subquestions']:
                cot['subquestions'].append({
                    "id": subquestion['id'],
                    "subquestion": subquestion['subquestion']
                })
            final_examples.append(cot)
        return final_examples
    
    def get_topk_subquestions_sql(self, question_str: str, topk=5) -> list:
        """
        根据问题选出最相似的topk问题并返回SQL查询
        """
        examples = self.get_topk_subquestions(question_str)
        final_examples = []
        counter = 0
        
        for template_id,subquestion_id, similarity in examples:
            for subquestion in self.templates[template_id]['subquestions']:
                if subquestion_id == subquestion['id']:
                    
                    if not subquestion['sql'].strip():
                        continue
                    counter += 1
                    if counter > topk:
                        break
                    
                    # 通过;分割SQL查询
                    sqls = subquestion['sql'].split(';')
                    # 遍历SQL查询
                    sql_list = []
                    for sql in sqls:
                        if not sql.strip():
                            continue
                        sql_list.append(
                            {
                                'id': subquestion_id,
                                'question': subquestion['subquestion'],
                                'reason': subquestion['reason'],
                                'sql': sql.strip()
                            }
                        )
                    final_examples.append(sql_list)
        return final_examples

    def add_template(self, template_id: str, template: dict):
        """
        添加模板到内存中
        """
        self.templates[template_id] = template
        self.logger.info(f"模板 {template_id} 已添加。")
    
    def _generate_unique_id(self) -> str:
        unique_id = uuid.uuid4().hex[:16]
        return f"impl-{unique_id}"
    
    def _compute_embedding(self, template: dict) -> dict:
        """
        计算模板和子问题的嵌入并返回
        """
        template_str = template['question']
        template['question_embedding'] = self.embedding_client.get_embeddings([template_str])[0] if template_str else []

        for subquestion in template['subquestions']:
            subquestion_str = subquestion['subquestion']
            subquestion['sub_question_embedding'] = self.embedding_client.get_embeddings([subquestion_str])[0] if subquestion_str else []
        
        return template
    
    def _cosine_similarity(self, embedding1, embedding2) -> float:
        """
        计算两个嵌入向量之间的余弦相似度
        """
        embedding1 = np.array(embedding1)
        embedding2 = np.array(embedding2)
        similarity = np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
        return similarity
    
    def __iter__(self):
        """迭代器，用于遍历模板"""
        return iter(self.templates.items())

    def test_topk_question_table_names(self, question_str: str, topk=5):
        """
        测试获取表名
        """
        self.logger.info(f"测试问题: {question_str}")
        examples = self.get_topk_questions_table_names(question_str, topk)
        for example in examples:
            self.logger.info(f"问题: {example['question']}")
            self.logger.info(f"表名: {example['tables_name']}")
    
    def test_topk_subquestions_table_names(self, question_str: str, topk=5):
        """
        测试获取子问题表名
        """
        self.logger.info(f"测试问题: {question_str}")
        examples = self.get_topk_subquestions_table_names(question_str, topk)
        for example in examples:
            self.logger.info(f"问题: {example['question']}")
            self.logger.info(f"表名: {example['tables_name']}")
    def test_topk_questions_cot(self, question_str: str, topk=5):
        """
        测试获取COT
        """
        self.logger.info(f"测试问题: {question_str}")
        examples = self.get_topk_questions_cot(question_str, topk)
        for example in examples:
            self.logger.info(f"问题: {example['question']}")
            for subquestion in example['subquestions']:
                self.logger.info(f"子问题 ID: {subquestion['id']}")
                self.logger.info(f"子问题: {subquestion['subquestion']}")
    
    def test_topk_subquestions_sql(self, question_str: str, topk=5):
        """
        测试获取SQL查询
        """
        self.logger.info(f"测试问题: {question_str}")
        examples = self.get_topk_subquestions_sql(question_str, topk)
        for example in examples:
            for sql in example:
                self.logger.info(f"\t子问题 ID: {sql['id']}")
                self.logger.info(f"\t子问题: {sql['question']}")
                self.logger.info(f"\t原因: {sql['reason']}")
                self.logger.info(f"\tSQL 查询: {sql['sql']}")