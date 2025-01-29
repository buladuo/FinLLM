from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent

# 配置文件路径
CONFIG_PATH = ROOT_DIR / "configs/config.yaml"
PROMPTS_PATH = ROOT_DIR / "data/prompts"
EXCEL_PATH = ROOT_DIR / "data/DataDict.xlsx"
QUESTION_PATH = ROOT_DIR / "data/question.json"
OUTPUT_PATH = ROOT_DIR/"data"