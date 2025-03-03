import argparse
from ast import arg
from core.finllm import FINLLM
from tqdm import tqdm

def parse_items(items,max_size):
    parsed_items = []
    for item in items:
        if '-' in item:
            start, end = map(int, item.split('-'))
            if start > end:
                raise ValueError(f"起始编号 {start} 不能大于结束编号 {end}。")
            if start < 1 or end > max_size:
                raise ValueError(f"编号必须在1到{max_size}之间。")
            parsed_items.extend(range(start, end + 1))
        else:
            number = int(item)
            if number < 1 or number > max_size:
                raise ValueError(f"编号 {number} 必须在1到{max_size}之间。")
            parsed_items.append(number)
    return parsed_items

def main():
    parser = argparse.ArgumentParser(description='处理FINLLM项目中的题目编号。')
    parser.add_argument('--items', nargs='+', default=None, help='一个或多个题目编号，可以是单个编号、多个编号或一个范围。')
    parser.add_argument('--cot', action='store_true', help='如果提供此参数，则使用COT特定接口。')
    parser.add_argument('--process-templates',nargs='+', help='如果提供此参数，则调用process_templates方法。')
    parser.add_argument('--interactive', action='store_true', help='进入交互模式，允许用户不断输入id并处理相应的题目。')
    parser.add_argument('--expand', action='store_true', help='根据已经写好的模板进行扩充')
    args = parser.parse_args()
    
    finllm = FINLLM()
    
    try:
        items = parse_items(args.items,finllm.get_total_num_questions()) if args.items else list(range(1, finllm.get_total_num_questions() + 1))
    except ValueError as e:
        parser.error(str(e))
        return
    
    try:
        template_items = parse_items(args.process_templates,finllm.get_total_num_questions()) if args.process_templates else list(range(1, finllm.get_total_num_questions() + 1))
    except ValueError as e:
        parser.error(str(e))
        return
    
    if args.expand:
        finllm.question_expand()
    
    if args.cot:
        finllm.cot_questions()
        
    if args.process_templates:
        for item in tqdm(template_items):
            finllm.process_templates(item - 1)
    
    if args.items:
        for item in tqdm(items):
            try:
                finllm.process_item(item - 1)
                finllm.save_result()
            except Exception as e:
                print(f"处理项目 {item} 时发生错误: {e}")

        
    # if args.items:
    #     for item in tqdm(items):
    #         finllm.process_item(item - 1)
        # finllm.save_result()
    
    if args.interactive:
        while True:
            user_input = input("请输入要处理的题目编号 (或输入 'q' 退出): ")
            if user_input.lower() == 'q':
                break
            try:
                item_id = int(user_input)
                if item_id < 1 or item_id > finllm.get_total_num_questions():
                    print(f"编号 {item_id} 必须在1到{finllm.get_total_num_questions()}之间。")
                else:
                    finllm.process_item(item_id - 1)
                    finllm.save_result()
                    print(f"题目 {item_id} 处理完成。")
            except ValueError:
                print("请输入有效的数字编号。")

if __name__ == "__main__":
    main()
