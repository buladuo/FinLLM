
import re
import json

class JsonExtractor:
    def __init__(self):
        # 正则表达式匹配以 ```json``` 开头和结尾的 JSON 字符串
        self.json_pattern = r'```json\s*(.*?)\s*```'
        # 正则表达式匹配所有的 {xxx} 字符串
        self.fallback_pattern = r'\{.*?\}'

    def extract_json(self, text:str , model_name=None):
        """从输入文本中提取 JSON 字符串"""
        
        text = text.replace('\n', ' ')
        text = self.preprocess(text,model_name)
        # 尝试匹配 ```json``` 块
        match = re.search(self.json_pattern, text, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                # 尝试将匹配的字符串转换为 JSON
                return json.loads(json_str)
            except json.JSONDecodeError:
                print("无法解析 JSON 数据")
                return None
        
        # 尝试匹配 {xxx} 中的所有 JSON 内容
        fallback_matches = re.findall(self.fallback_pattern, text)
        if fallback_matches:
            for fallback_json_str in fallback_matches:
                try:
                    return json.loads(fallback_json_str)
                except json.JSONDecodeError:
                    print(f"无法解析备用的 JSON 数据: {fallback_json_str}")
                    continue
        
        # 未找到匹配的 JSON
        return []
    
    def preprocess(self, text, model_name=None):
        # 如果没有提供模型名称，直接返回原始文本
        if model_name is None:
            return text
        
        if model_name in ['glm-4-zero', 'glm-4-think']:
            match = re.search(r'\[思考结束\](.*)', text,re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return text
        

if __name__ == '__main__':
    extractor = JsonExtractor()
    
    text = """
    这是一些包括 JSON 的文本：
    {
        "name": "测试",
        "value": 100,
        "more_data": {
            "details": "细节介绍"
        }
    }
    还有一些备用的内容：
    {
        "status": "成功",
        "info": "处理完成"
    }
    """

    result = extractor.extract_json(text)
    print(result)  # 输出: {'name': '测试', 'value': 100, 'more_data': {'details': '细节介绍'}}

# # 示例用法
# if __name__ == '__main__':
#     extractor = JsonExtractor()
    
#     # 尝试提取第一个 JSON 格式
#     text_1 = """@GPT-4o ```json
#     {"id":1,"class_name":"A股上市公司数据"}
#     ```"""
#     result_1 = extractor.extract_json(text_1)
#     print(result_1)  # 输出: {'id': 1, 'class_name': 'A股上市公司数据'}

#     # 尝试提取备用的 JSON 内容
#     text_2 = """这是一些文本内容。
#     包含多个 JSON: {"id": 5,"class_name": "股票市场数据"}, 另一个数据: {"status":"成功"}"""
    
#     result_2 = extractor.extract_json(text_2)
#     print(result_2)  # 输出: {'name': '测试', 'value': 100}
