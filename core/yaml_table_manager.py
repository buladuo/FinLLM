import os
import yaml
import logging

class YamlTableManager:
    def __init__(self, directory_path):
        """初始化 YamlTableManager，遍历指定目录加载所有 YAML 文件中的数据库信息。"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.database_info = self._load_yaml_files_from_directory(directory_path)

    def _load_yaml_files_from_directory(self, directory_path):
        """遍历目录，加载所有 YAML 文件并返回数据库信息。"""
        database_info = []
        try:
            for filename in os.listdir(directory_path):
                if filename.endswith('.yaml'):
                    full_path = os.path.join(directory_path, filename)
                    with open(full_path, 'r', encoding='utf-8') as file:
                        data = yaml.safe_load(file)
                        if data:
                            database_info.append(data)
                            self.logger.debug(f"Loaded data from {filename}")
        except Exception as e:
            self.logger.error(f"Failed to load YAML files: {e}")
        return database_info

    def get_all_database_names(self):
        """获取所有数据库名称。"""
        return {info['database_name'] for info in self.database_info}

    def get_table_info(self, table_name):
        """根据表名获取特定表的信息。"""
        for info in self.database_info:
            if info['table_name'] == table_name:
                return info
        return None

    def get_table_description(self, table_name):
        """根据表名获取表的描述。"""
        table_info = self.get_table_info(table_name)
        if table_info:
            return table_info.get('table_describe', None)
        return None

    def get_fields_from_table(self, table_name):
        """根据表名获取表的字段。"""
        table_info = self.get_table_info(table_name)
        if table_info:
            return table_info.get('fields', [])
        return []

    def get_table_names(self):
        """获取所有表名。"""
        return {info['table_name'] for info in self.database_info}
    
    def get_full_table_name(self, table_name):
        """根据表名获取完整的表名称。"""
        table_info = self.get_table_info(table_name)
        if table_info:
            return table_info.get('full_table_name', None)
        return None

    def get_extension_annotations(self, table_name):
        """根据表名获取扩展注释信息。"""
        table_info = self.get_table_info(table_name)
        if table_info:
            return table_info.get('externtion_annotation', [])
        return []

# 使用示例
if __name__ == "__main__":
    manager = YamlTableManager('/home/buladuo/Projects/FinLLM/data/table_infos')

    # 示例：获取所有数据库名称
    print(manager.get_all_database_names())

    # 示例：获取特定表的信息
    # print(manager.get_table_info('lc_areacode'))

    # 示例：获取特定表的描述
    print(manager.get_table_description('qt_stockperformance'))

    # 示例：获取特定表的字段
    # print(manager.get_fields_from_table('lc_areacode'))

    # 示例：获取所有表名
    # print(manager.get_table_names())
