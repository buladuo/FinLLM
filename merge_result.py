import json
import os

def merge_answers(input_files, output_file):
    merged_data = []

    for file in input_files:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                tid = item['tid']
                # 如果 merged_data 中没有该 tid，就新建一个条目
                if not any(d['tid'] == tid for d in merged_data):
                    merged_data.append({
                        "tid": tid,
                        "team": []
                    })
                
                # 找到对应的条目并合并 answer
                for team in item['team']:
                    team_id = team['id']
                    answer = team['answer']
                    for merged_item in merged_data:
                        if merged_item['tid'] == tid:
                            # 检查是否已经存在相应的团队
                            for merged_team in merged_item['team']:
                                if merged_team['id'] == team_id:
                                    # 合并 answer
                                    if answer:  # 如果 answer 不是空
                                        merged_team['answer'] += " " + answer.strip()
                                    break
                            else:
                                # 如果没有找到对应的团队，直接添加
                                merged_item['team'].append({
                                    "id": team_id,
                                    "question": team['question'],
                                    "answer": answer.strip()
                                })
                            break

    # 将合并后的数据写入到新的 JSON 文件
    with open(output_file, 'w', encoding='utf-8') as outfile:
        json.dump(merged_data, outfile, ensure_ascii=False, indent=4)

# 示例用法：
input_files = ['/home/buladuo/Projects/FinLLM/data/merged_result.json', '/home/buladuo/Projects/FinLLM/data/result.json']  # 替换为你的 JSON 文件名
output_file = '/home/buladuo/Projects/FinLLM/data/merged_result_2.json'
merge_answers(input_files, output_file)
