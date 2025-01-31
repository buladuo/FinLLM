import json
import os
import logging

class Question:
    def __init__(self, question_data):
        self.tid = question_data["tid"]
        self.team = [SubQuestion(q) for q in question_data["team"]]
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_tid(self):
        return self.tid

    def get_subquestion(self, index):
        if index < len(self.team):
            return self.team[index]
        else:
            raise IndexError("Index out of range for sub-questions.")
        
    def get_all_question(self) -> str:
        all_question = ""
        for subquestion in self.team:
            all_question += subquestion.question
        return all_question
    
    def __iter__(self):
        """使 Question 实例可迭代。这里迭代的是其子问题。"""
        return iter(self.team)

class SubQuestion:
    def __init__(self, question_data):
        self.id = question_data["id"]
        self.question = question_data["question"]

    def get_id(self):
        return self.id

    def get_question(self):
        return self.question

class QuestionManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.questions = []
        self.load_questions()

    def load_questions(self):
        """从 JSON 文件加载问题数据。"""
        if os.path.exists(self.file_path):
            with open(self.file_path, encoding='utf8') as f:
                all_questions = json.load(f)
                for item in all_questions:
                    self.questions.append(Question(item))
        else:
            print(f"文件 {self.file_path} 不存在。")

    def get_question(self, index) -> Question:
        """获取指定索引的问题。"""
        if index < len(self.questions):
            return self.questions[index]
        else:
            raise IndexError("Index out of range for questions.")

    def __iter__(self):
        """使 QuestionManager 实例可迭代。这里迭代的是问题列表。"""
        return iter(self.questions)

# 示例如何使用 QuestionManager
if __name__ == "__main__":
    # 创建 QuestionManager 实例
    manager = QuestionManager('data/question.json')

    print("所有问题:")
    for question in manager:
        print("问题 TID:", question.get_tid())
        for sub_question in question:
            print("小问题 ID:", sub_question.get_id())
            print("小问题 内容:", sub_question.get_question())
