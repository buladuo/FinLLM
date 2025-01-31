import yaml
import os

# 定义要输出的 YAML 内容
yaml_data = {
    'default': 1,
    'database_name': 'db1',
    'database_name_zh': '数据库1',
    'table_name': 'user_info',
    'table_name_zh': '用户信息表',
    'table_describe': '存储用户信息',
    'externtion_annotation': [
        {'id': 1, 'content': '用户ID'},
        {'id': 2, 'content': '用户名'},
    ]
}

# 指定输出目录和文件名
output_dir = 'output_yaml_files'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

yaml_file_name = os.path.join(output_dir, 'db1.user_info.yaml')

# 将内容写入 YAML 文件，使用不同的 dump 方法参数控制格式
with open(yaml_file_name, 'w', encoding='utf-8') as yaml_file:
    yaml.dump(yaml_data, yaml_file, allow_unicode=True, sort_keys=False, default_flow_style=False,indent=2)

print(f"YAML 文件已生成: {yaml_file_name}")
