import argparse
import os
import shutil
import pandas as pd
import logging
import yaml
import json

class YamlTableInfoGenerator:
    """A utility class for generating YAML files from an Excel database schema."""
    
    def __init__(self, excel_path):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.database_info = self._generate_database_info(excel_path)
        self.table_info = self._generate_table_info(excel_path)

    def _generate_database_info(self, excel_path):
        data = pd.read_excel(excel_path, sheet_name='库表关系')
        result = []
        for _, row in data.iterrows():
            database_name = row['库名英文'].lower()
            database_name_zh = row['库名中文']

            db_info = next((item for item in result if item['database_name'] == database_name), None)
            if db_info is None:
                db_info = {
                    'database_name': database_name,
                    'database_name_zh': database_name_zh,
                    'tables': []
                }
                result.append(db_info)

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
        for _, row in data.iterrows():
            table_name = row['table_name'].lower()

            if table_name not in result:
                result[table_name] = {
                    'fields': []
                }

            field_info = {
                'column_name': row['column_name'],
                'column_description': row['column_description'],
                'annotation_zh': row['注释'],
                'annotation': row['Annotation']
            }
            result[table_name]['fields'].append(field_info)

        return result

    def generate_yaml_files(self, output_dir):
        """Generates YAML files for each table in the databases."""
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        
        os.makedirs(output_dir)

        for db in self.database_info:
            database_name = db['database_name']
            database_name_zh = db['database_name_zh']

            for table in db['tables']:
                table_name = table['table_name']
                table_name_zh = table['table_name_zh']
                table_describe = table['table_describe'].replace("\n", "").replace("\r", "")

                # Get fields for the current table
                table_fields = self.table_info.get(table_name, {}).get('fields', [])
                # Construct the YAML data structure
                yaml_data = {
                    'default': 1,
                    'full_table_name': f"{database_name}.{table_name}.yaml".lower(),
                    'database_name': database_name,
                    'database_name_zh': database_name_zh,
                    'table_name': table_name,
                    'table_name_zh': table_name_zh,
                    'table_describe': table_describe,
                    'externtion_annotation': [
                        {
                            'id': 1,
                            'content': ""
                        }
                    ],
                    'fields': table_fields  # Add table fields information
                    
                }

                # Generate YAML file name
                yaml_file_name = f"{database_name}.{table_name}.yaml"
                yaml_file_path = os.path.join(output_dir, yaml_file_name.lower())

                # Write to YAML file
                with open(yaml_file_path, 'w', encoding='utf-8') as yaml_file:
                    yaml.dump(yaml_data, yaml_file, allow_unicode=True,sort_keys=False)

def main():
    parser = argparse.ArgumentParser(description="Generate YAML files from an Excel database schema.")
    parser.add_argument("--excel_path", type=str, required=True, help="Path to the Excel file.")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save the generated YAML files.")
    
    args = parser.parse_args()

    generator = YamlTableInfoGenerator(args.excel_path)
    generator.generate_yaml_files(args.output_dir)


if __name__ == "__main__":
    main()