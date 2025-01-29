import os
import yaml
import logging

class PromptManager:
    def __init__(self, directory_path):
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.directory_path = directory_path
        self.prompts = self.load_prompts()

    def load_prompts(self):
        prompts = {}
        for root, dirs, files in os.walk(self.directory_path):
            for filename in files:
                if filename.endswith('.yaml'):
                    file_path = os.path.join(root, filename)
                    try:
                        with open(file_path, 'r') as file:
                            data = yaml.safe_load(file)
                            if data:  # 确保文件内容不为空
                                type = data.get('type')
                                if type:
                                    prompts[type] = {
                                        'default': data.get('default'),
                                        'prompts': data.get('prompts', [])
                                    }
                                else:
                                    self.logger.warning(f"YAML file '{file_path}' is missing 'type' key.")
                    except yaml.YAMLError as e:
                        self.logger.error(f"Error parsing YAML file '{file_path}': {e}")
                    except IOError as e:
                        self.logger.error(f"Error reading file '{file_path}': {e}")
        
        return prompts

    def get_prompt(self, prompt_type, prompt_id=None):
        if prompt_type in self.prompts:
            prompts_data = self.prompts[prompt_type]
            if prompt_id is None:
                prompt_id = prompts_data['default']  # 如果没有指定 ID，则使用默认 ID
            for prompt in prompts_data['prompts']:
                if prompt['id'] == prompt_id:
                    return prompt
        return None

