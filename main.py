import argparse
from core.finllm import FINLLM
from tqdm import tqdm

def parse_items(items):
    parsed_items = []
    for item in items:
        if '-' in item:
            start, end = map(int, item.split('-'))
            if start > end:
                raise ValueError(f"起始编号 {start} 不能大于结束编号 {end}。")
            if start < 1 or end > 101:
                raise ValueError(f"编号必须在1到101之间。")
            parsed_items.extend(range(start, end + 1))
        else:
            number = int(item)
            if number < 1 or number > 100:
                raise ValueError(f"编号 {number} 必须在1到101之间。")
            parsed_items.append(number)
    return parsed_items

def main():
    parser = argparse.ArgumentParser(description='处理FINLLM项目中的题目编号。')
    parser.add_argument('--items', nargs='+', default=None, help='一个或多个题目编号，可以是单个编号、多个编号或一个范围。')
    parser.add_argument('--cot', action='store_true', help='如果提供此参数，则使用COT特定接口。')
    args = parser.parse_args()
    
    try:
        items = parse_items(args.items) if args.items else list(range(1, 102))
    except ValueError as e:
        parser.error(str(e))
        return
    
    finllm = FINLLM()
    
    if args.cot:
        finllm.cot_questions()
    
    if args.items:
        for item in tqdm(items):
            finllm.process_item(item - 1)
        
        finllm.save_result()
    

if __name__ == "__main__":
    main()
