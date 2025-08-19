import re
import os

  # 定义一个函数，根据sql语句生成定义字符串
def generate_definition_string(sql):
  
  # date_fmt = '%m/%d/%Y' '%d/%m/%Y' "%d/%m/%Y %H:%M:%S" %Y/%m/%d
  # %Y%m%d  '%d/%m/%Y' '%Y-%m-%d'  "%d/%m/%Y %H:%M:%S" '%d-%m-%Y' '%Y%m%d'
  date_fmt = '%d-%m-%Y'

  # print(sql)

  # 导入正则表达式模块
  # 定义一个空列表，用于存储定义字符串的各个部分
  definition_parts = []
  # 定义一个序号变量，初始值为0
  index = 0
  # 用正则表达式匹配sql语句中的列名，类型，长度和是否为空
  pattern = r'\s*(\w+)\s+([a-z]+)(?:\(?(\d+)(?:,\s*\d+)?\)?)?\s*(not\s+null)?'
  matches = re.findall(pattern, sql, re.IGNORECASE)
  # 遍历匹配结果，生成定义字符串的各个部分
  for match in matches:
    # 获取列名，类型，长度和是否为空
    column_name = match[0]
    if column_name == 'CONSTRAINT':
      break

    column_type = match[1].lower()
    column_length = match[2]
    column_not_null = match[3].lower() if match[3] else ''
    # 根据类型生成类型定义
    if column_type in ('numeric', 'decimal', 'float', 'real', 'double precision', 'int', 'integer', 'smallint', 'bigint'):
      type_definition = 'num'
    elif column_type in ('character', 'character varying', 'varchar', 'text'):
      type_definition = 'str'
    elif column_type in ('date', 'timestamp', 'timestamp with time zone', 'timestamp without time zone'):
      type_definition = 'date'
    elif column_type in ('time', 'time with time zone', 'time without time zone'):
      type_definition = 'time'
    else:
      type_definition = column_type # 其他类型不做处理，直接使用原始类型
    # 根据类型生成格式定义
    if type_definition == 'date':
      format_definition = date_fmt
    else:
      format_definition = '' # 其他类型不需要格式定义，留空
    # 根据类型生成长度定义
    if type_definition == 'str':
      length_definition = column_length
    else:
      length_definition = '' # 其他类型不需要长度定义，留空
    # 根据是否为空生成是否为空定义
    if column_not_null == 'not null':
      not_null_definition = 'notnull'
    else:
      not_null_definition = '' # 不为空时，留空
    # 生成定义字符串的一个部分，用|分隔各个字段
    definition_part = f'{index}|{column_name}|{type_definition}|{format_definition}|{length_definition}|{not_null_definition}'
    # 将定义字符串的一个部分添加到列表中
    definition_parts.append(definition_part)
    
    print(definition_part)
    # 序号加一
    index += 1

  # 用分号连接列表中的所有部分，生成完整的定义字符串
  definition_string = ';'.join(definition_parts)
  # 返回定义字符串
  return definition_string

def get_inner(sql):
    m = re.search(r'\((.+)\)', sql, re.DOTALL)
    if m:
       sr = m.group(1)
    return sr
script_dir = os.path.dirname(os.path.abspath(__file__))

def process_sql_file(sql_file_path):
    with open(sql_file_path, 'r', encoding= 'utf-8') as file:
        sql_content = file.read()

    # 用正则表达式分割多个 CREATE TABLE 语句
    create_sql_list = re.findall(r'(.*?;)', sql_content, flags=re.DOTALL)

    for create_sql in create_sql_list:
        # 从每个 CREATE TABLE 语句中提取表名
        match = re.search(r'CREATE\s+TABLE\s+(\w+.\w+)', create_sql)
        if match:
            table_name = match.group(1)
            print(table_name)
            output_file_path = f"{table_name}.define.txt"
            output_file_path = os.path.join(script_dir, 'output',output_file_path)
            print(create_sql)
            # 提取字段并输出到文件
            result = generate_definition_string(get_inner(create_sql))
            if result:
                with open(output_file_path, 'w') as output_file:
                    for line in result:
                        output_file.write(line)
    


process_sql_file('testsql.sql')