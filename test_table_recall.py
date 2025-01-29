import os
import csv
import pytest
import argparse
import yaml
import logging
from sqlalchemy import Subquery
from paths import EXCEL_PATH, CONFIG_PATH, QUESTION_PATH, PROMPTS_PATH, OUTPUT_PATH
from core.question_manager import QuestionManager
from core.table_locator import TableLocator
from core.prompt_manager import PromptManager
import core.agents as Agents
from utils.logging_utils import LoggingUtils


def test_table_recall(model):
    model_name = model

    # 加载配置
    with open(CONFIG_PATH, "r") as file:
        config = yaml.safe_load(file)

    logging_config = config.get("logging", {})
    LoggingUtils.setup_logging(logging_config)

    # 获取指定模型的配置
    model_config = config["models"].get(model_name)
    if model_config is None:
        pytest.fail(f"Model configuration for '{model_name}' not found.")
        
    prompt_manager = PromptManager(PROMPTS_PATH)
    global_config = config["global"]
    agents_config_manager = Agents.AgentsConfigManager(model_config,global_config,prompt_manager)


    table_locator = TableLocator()
    question_manager = QuestionManager(QUESTION_PATH)
    
    output_file_path = os.path.join(OUTPUT_PATH, f"table_recall_by_{model_name}.csv")

    # 创建并写入CSV文件
    with open(output_file_path, mode='w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['id', 'question', 'result'])  # 写入CSV文件头
        
        for question in question_manager:
            # print("问题 TID:", question.get_tid())
            logging.info(f"问题ID：{question.get_tid()}")
            for sub_question in question:
                logging.info(f"Question is :{sub_question.get_question()}")
                result = table_locator.get_table_with_db(sub_question.get_question())
                result_str = ', '.join(result)  # 将结果字符用逗号连接

                # 写入每一行到CSV文件
                csv_writer.writerow([sub_question.get_id(), sub_question.get_question(), result_str])

    print(f"CSV file has been created at: {output_file_path}")

    # 验证输出 CSV 文件是否生成
    assert os.path.exists(output_file_path), "CSV file was not created."
    



def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Test table recall for a specified model.')
    parser.add_argument('--model', type=str, required=True, help='The model to use for testing.')
    args = parser.parse_args()

    # 调用测试函数，传入模型名称
    test_table_recall(args.model)

if __name__ == "__main__":
    main()