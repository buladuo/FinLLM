import sqlparse
from sqlparse.sql import Identifier, Function, Where, Comparison, Parenthesis, IdentifierList
from sqlparse.tokens import Keyword, DML, Punctuation
from sqlparse.tokens import Wildcard  # 确保导入Wildcard类型

def extract_parameters_from_function(function):
    """从函数中提取参数字段（忽略函数名和特殊符号）"""
    params = []
    inside = False
    for token in function.tokens:
        if isinstance(token, Parenthesis):
            inside = True
            for t in token.tokens:
                if t.ttype == Punctuation and t.value == '(':
                    continue
                if isinstance(t, Identifier):
                    params.append(t.get_real_name())
                elif isinstance(t, Function):
                    params.extend(extract_parameters_from_function(t))
                elif t.ttype is Wildcard:  # 处理Wildcard类型的*
                    params.append(t.value)
                elif t.value.upper() == 'DISTINCT':
                    continue  # 跳过DISTINCT关键字
            inside = False
        elif inside and isinstance(token, Identifier):
            params.append(token.get_real_name())
    return params

def extract_alias(identifier):
    """从标识符中提取别名"""
    alias = None
    as_seen = False
    for token in identifier.tokens:
        if token.ttype is Keyword and token.value.upper() == 'AS':
            as_seen = True
            continue
        if as_seen:
            if isinstance(token, Identifier):
                alias = token.get_real_name()
                break
            elif token.ttype is Keyword:
                alias = token.value
                break
    return alias

def process_identifier(identifier, fields):
    """处理标识符，提取别名或参数"""
    alias = extract_alias(identifier)
    if alias:
        fields.append(alias)
    else:
        # 检查是否是Function类型
        if isinstance(identifier, Function):
            params = extract_parameters_from_function(identifier)
            fields.extend(params)
        else:
            # 普通列名或表达式
            name = identifier.get_real_name()
            fields.append(name)

def extract_fields(parsed):
    """提取查询字段（处理别名和函数参数）"""
    fields = []
    select_seen = False
    from_seen = False
    for token in parsed.tokens:
        if token.ttype is DML and token.value.upper() == 'SELECT':
            select_seen = True
            continue
        if select_seen and token.ttype is Keyword and token.value.upper() == 'FROM':
            from_seen = True
            break
        if select_seen and not from_seen:
            if isinstance(token, IdentifierList):
                for identifier in token.get_identifiers():
                    process_identifier(identifier, fields)
            elif isinstance(token, (Identifier, Function)):
                process_identifier(token, fields)
    return [f for f in fields if f != '*']  # 过滤星号


def extract_where_conditions(parsed):
    """提取 WHERE 后面的条件字段（支持子查询）"""
    conditions = []
    for token in parsed.tokens:
        if isinstance(token, Where):
            for sub_token in token.tokens:
                if isinstance(sub_token, Comparison):
                    conditions.append(sub_token.left.value.split('.')[-1])
                elif isinstance(sub_token, Parenthesis) and not sub_token.is_group:
                    conditions.extend(extract_conditions_from_parenthesis(sub_token))
    return conditions

def extract_conditions_from_parenthesis(parenthesis):
    """从括号中提取条件字段"""
    conditions = []
    for token in parenthesis.tokens:
        if isinstance(token, Comparison):
            conditions.append(token.left.value.split('.')[-1])
        elif isinstance(token, Parenthesis):
            conditions.extend(extract_conditions_from_parenthesis(token))
    return conditions

def extract_tables(parsed):
    """提取表字段（精确处理JOIN和UNION）"""
    from_stream = extract_from_part(parsed)
    tables = []
    for token in from_stream:
        if token.value.upper() in ('INNER', 'LEFT', 'RIGHT', 'FULL', 'JOIN', 'UNION', 'ON'):
            continue  # 跳过连接关键字
        if isinstance(token, Identifier):
            tables.append(token.get_real_name())
        elif isinstance(token, Parenthesis) and not token.is_group:
            # 处理子查询中的表
            subquery_tables = extract_tables(token)
            tables.extend(subquery_tables)
    return tables
# extract_from_part、is_subselect、extract_table_identifiers 保持官方示例实现
def is_subselect(parsed):
    if not parsed.is_group:
        return False
    for item in parsed.tokens:
        if item.ttype is DML and item.value.upper() == 'SELECT':
            return True
    return False

def extract_from_part(parsed):
    from_seen = False
    for item in parsed.tokens:
        if from_seen:
            if item.ttype is Keyword and item.value.upper() in ('WHERE', 'GROUP', 'HAVING', 'ORDER', 'LIMIT'):
                return
            if is_subselect(item):
                for x in extract_from_part(item):
                    yield x
            else:
                yield item
        if item.ttype is Keyword and item.value.upper() == 'FROM':
            from_seen = True
            continue

def extract_table_identifiers(token_stream):
    for item in token_stream:
        if isinstance(item, IdentifierList):
            for identifier in item.get_identifiers():
                yield identifier.get_real_name()
        elif isinstance(item, Identifier):
            yield item.get_real_name()

# parse_sql和测试函数保持不变
def parse_sql(sql):
    parsed = sqlparse.parse(sql)[0]
    fields = extract_fields(parsed)
    where_conditions = extract_where_conditions(parsed)
    tables = extract_tables(parsed)
    return fields, where_conditions, tables

def test_parse_sql():
    sqls = [
        "SELECT name, age FROM users;",
        "SELECT COUNT(*) AS total_users, AVG(age) AS average_age FROM users;",
        "SELECT ROUND(price, 2) AS rounded_price, name FROM products;",
        "SELECT name, age FROM users WHERE age > 25 AND name = 'Alice';",
        "SELECT name, age FROM users WHERE age IN (SELECT age FROM users WHERE name = 'Alice');",
        "SELECT name FROM users WHERE age > 25 UNION SELECT name FROM employees WHERE age > 30;",
        "SELECT COUNT(DISTINCT name) AS unique_names, MAX(price) AS max_price FROM products WHERE price > 50;",
        "SELECT category, COUNT(*) AS product_count FROM products GROUP BY category HAVING COUNT(*) > 10;",
        "SELECT users.name, orders.amount FROM users INNER JOIN orders ON users.id = orders.user_id WHERE orders.amount > 100;"
    ]

    for sql in sqls:
        fields, where_conditions, tables = parse_sql(sql)
        print(f"SQL: {sql}")
        print(f"Fields: {fields}")
        print(f"Where Conditions: {where_conditions}")
        print(f"Tables: {tables}")
        print("-" * 40)

if __name__ == "__main__":
    test_parse_sql()