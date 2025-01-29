import pandas as pd
import logging
import json


class DatabaseTableManager:
    def __init__(self, excel_path):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.database_info = self._generate_database_info(excel_path)
        self.table_info = self._generate_table_info(excel_path)


    def _generate_database_info(self, excel_path):
        data = pd.read_excel(excel_path, sheet_name='库表关系')
        result = []
        # 按照数据字典中的库和表生成结构
        for _, row in data.iterrows():
            database_name = row['库名英文'].lower()
            database_name_zh = row['库名中文']

            # 创建一个新的数据库字典，如果该数据库还未在结果中
            db_info = next((item for item in result if item['database_name'] == database_name), None)
            if db_info is None:  # 如果找不到该数据库，在结果中创建一项
                db_info = {
                    'database_name': database_name,
                    'database_name_zh': database_name_zh,
                    'tables': []
                }
                result.append(db_info)

            # 创建表的信息
            table_info = {
                'table_name': row['表英文'].lower(),
                'table_name_zh': row['表中文'],
                'table_describe': row['表描述']
            }
            db_info['tables'].append(table_info)

        return result

    def _generate_table_info(self, excel_path):
        data = pd.read_excel(excel_path, sheet_name='表字段信息')

        result = {}
        # 使用提供的字段名称创建字段信息
        for _, row in data.iterrows():
            # print(row)
            table_name = row['table_name'].lower()

            # 创建一个新的表字典，如果该表还未在结果中
            if table_name not in result:
                result[table_name] = {
                    'fields': []
                }

            # 创建字段的信息
            field_info = {
                'column_name': row['column_name'],  # 字段英文
                'column_description': row['column_description'],  # 字段描述
                'annotation_zh': row['注释'],  # 使用中文的注释字段
                'annotation': row['Annotation']  # 英文注释
            }
            result[table_name]['fields'].append(field_info)

        return result

    def get_database_info(self):
        return self.database_info

    def get_table_info(self):
        return self.table_info

    def get_table_info_by_name(self, table_name):
        return self.table_info.get(table_name.lower(), None)

    def get_table_description_by_name(self, table_name):
        # 查找对应表的描述信息
        table_name_lower = table_name.lower()
        for db in self.database_info:
            for table in db['tables']:
                if table['table_name'] == table_name_lower:
                    return table['table_describe']
        return None


# 使用例子
if __name__ == "__main__":
    excel_path = './data/数据字典.xlsx'
    db_table_manager = DatabaseTableManager(excel_path)

    # 获取库表关系信息
    database_info = db_table_manager.get_database_info()

    # 获取表字段信息
    table_info = db_table_manager.get_table_info()

    # 获取指定表的字段信息
    specific_table_info = db_table_manager.get_table_info_by_name('指定表名')

    # 获取指定表的表描述
    table_description = db_table_manager.get_table_description_by_name('指定表名')

    # 打印结果
    print(json.dumps(database_info, ensure_ascii=False, indent=2))
    print(json.dumps(table_info, ensure_ascii=False, indent=2))
    print(json.dumps(specific_table_info, ensure_ascii=False, indent=2))
    print("表描述:", table_description)
