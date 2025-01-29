from tabulate import tabulate
from openai import OpenAI
from tqdm import tqdm
import httpx
import yaml

from paths import CONFIG_PATH

# 加载配置
def load_config(config_path: str):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)


# 初始化 OpenAI 客户端
def initialize_client(base_url: str, api_key: str):
    http_client = httpx.Client()
    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        http_client=http_client
    )
    return client


# 测试指定模型后端
def validate_single_model(client, model_name, prompt):
    try:
        # 调用模型生成接口
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        # 返回生成结果
        response = completion.choices[0].message.content[:15]
        return True, response.replace("\n", " ")
    except Exception as e:
        return False, str(e)



# 测试多个模型后端
def validate_models_from_config(config):
    models = config["models"]
    results = []

    for model_name, model_config in tqdm(models.items(), desc="Testing models", unit="model"):
        client = initialize_client(
            base_url=model_config["api_base"],
            api_key=model_config["api_key"]
        )
        # 设置测试的 prompt
        test_prompt = "Hello! Please introduce yourself by your name."
        success, response = validate_single_model(client, model_config["name"], test_prompt)
        results.append({
            "模型名称": model_config["name"],
            "模型描述": model_name,
            "是否可用": "✅" if success else "❌",
            "测试结果": response
        })

    return results

def print_results_table(results):
    table = []
    headers = ["模型名称", "模型描述", "是否可用", "测试结果"]

    for result in results:
        table.append([
            result["模型名称"],
            result["模型描述"],
            result["是否可用"],
            result["测试结果"]
        ])

    print(tabulate(table, headers=headers, tablefmt="grid"))

def test():
    # 加载配置文件
    config_path = CONFIG_PATH
    config = load_config(config_path)

    # 测试所有模型后端
    print("开始测试所有模型后端...\n")
    test_results = validate_models_from_config(config)

    # 打印汇总测试结果为表格
    print("\n所有模型测试完成，结果如下：\n")
    print_results_table(test_results)

# 主函数入口
if __name__ == "__main__":
    test()
