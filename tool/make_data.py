"""
Author: Mr.Blue

对数据做轻微加密处理

# 执行方法
同级目录新建如下结构 
  └─make_dfile
    ├─AU
    │  ├─dummy
    ├─CN
    │  └─dummy
    ├─HK
    │  └─dummy
    ├─IN
    │  └─dummy
    ├─MY
    │  ├─dummy
    ├─NZ
    │  └─dummy
    ├─SG
    │  └─dummy
    └─TW
        └─dummy
源文件放在地区（例如 AU）路径下，执行程序后，测试数据会生成到dummy

设定 all_path 参数，指定生成数据的地区。
  {"SG":SG,"CN":CN,"MY":MY,"AU":AU,"NZ":NZ,"IN":IN,"HK":HK,"TW":TW}
  
# 注意
cn的 alipay header部分需要编辑下

"""
import re
import os
import sys
import unicodedata
import pandas as pd

DATA_PATH = "make_dfile"
DUMY_DATA = "dummy"
skip_words =["ORDP","（","）","-","ORG","OGB","IND"]

CN=[("Alipay",[10,11,12,13,14],"gbk",["default"]),
    ("COD",[5,8,9,10,15,16],"gbk",["default"]),
    ("CCB",[2,3,8,10,11,15,16],"gbk",["default"]),
    ("Open Customer Back Orders",[12],"gbk",["default"]),
    ("Sales code",[1],"gbk",["Sales Mapping"]),
    ("AR Outstanding",[1,2,3],"gbk",["default"]),
    ("ADV-未解单",[3,4],"gbk",["Released"]),
    ("ASW650",[0,1,2,3,4,5,35,36],"gbk",["default"])]


MY=[("MY HSBC",[18],"utf-8",["Sheet1"]),
    ("ASW650",[0,1,2,3,4],"utf-8",["default"]),
    ("MALAYSIA",[1,2,3,4],"utf-8",["Sheet1"]),
    ("MY_AR Aging",[1,2],"utf-8",["MY_AR_Aging"]),
    ("MY MBB",[14,15,25,26],"utf-8",["default"]),
    ("MY M2U",[6,8,10,12],"utf-8",["default"])]

SG=[("SGD HSBC",[18],"utf-8",["Sheet1"]),
    ("THB HSBC",[18],"utf-8",["Sheet1"]),
    ("USD HSBC",[18],"utf-8",["Sheet1"]),
    ("KRW BOA",[10,11,16,48],"utf-8",["CashPro"]),
    ("ASW650",[0,1,2,3,4],"utf-8",["default"]),
    ("AGING",[2,3],"utf-8",["SG_AR_Outstanding_w"]),
    ("SG whitelist",[0,1,2],"utf-8",["SGD H02","USD H08","THB H11"]),
    ("SG Working",[1],"utf-8",["H11 THB A63","H08 USD A64","H03 KRW A60","H02 SGD A62"]),
    ("BOA TRACKER",[6],"utf-8",["updated","DONE"])  # not must need
    ]

AU=[("AU HSBC",[18],"utf-8",["Sheet1"]),
    ("AU Customer Master Data",[0,1,2,3,4],"utf-8",["default"]),
    ("Book2",[2,3],"utf-8",["AU"]),
    ("ANZ Cash Application Tracker",[3,12],"utf-8",["AU JAN 23"])]

NZ=[("NZ HSBC",[18],"utf-8",["Sheet1"]),
    ("NZ Customer Master Data",[0,1,2,3,4],"utf-8",["default"]),
    ("Book3",[2,3],"utf-8",["NZ"]),
    ("ANZ Cash Application Tracker",[3,12],"utf-8",["NZ JAN 23"]),
    ("NZ ASB",[10,11,16,48],"utf-8",["CashPro"])]

IN=[("INR BOA New Account",[10,11,16,48],"utf-8",["CashPro"]),
    ("ASW650",[0,1,2,3,4],"utf-8",["default"]),
    ("Receivable",[1,12,15,16],"utf-8",["Sheet1"]),
    ("History Tracker",[0,1],"utf-8",["Sheet1"]),
    ("open item",[2,3],"utf-8",["default"])]

HK=[("USD HSBC",[18],"utf-8",["default"]),
    ("HKD HSBC",[18],"utf-8",["default"]),
    ("ASW650",[1,2,3,4],"utf-8",["default"]),
    ("Hkaging",[2,3],"utf-8",["default"]),
    ("HKB HKD_USD Bank Details",[2],"utf-8",["HKD","USD"])]

TW=[("TW TWD&USD tracker",[18],"utf-8",["TW-USD"]), # TW-TWD 英文 汉字混合
    ("USD HSBC",[18],"utf-8",["default"]),
    ("TWD HSBC",[18],"utf-8",["default"]),
    ("ASW650",[1,2,3,4],"utf-8",["default"])]

# "SG":SG,"CN":CN,"MY":MY,"AU":AU,"NZ":NZ,"IN":IN,"HK":HK,"TW":TW
all_path={"AU":AU}

def shift_letter(char):
    """
    按字母顺序替换字母字符。例如：a -> b, b -> c, ..., z -> a.
    """
    if char.islower():
        return chr((ord(char) - ord('a') + 5) % 26 + ord('a'))
    elif char.isupper():
        return chr((ord(char) - ord('A') + 5) % 26 + ord('A'))
    else:
        return char

def replace_numbers(text):
    """
    替换字符串中的数字，首位数字不进行替换，其他数字做+1处理。
    """
    result = []
    text = str(text)  # 将数值转换为字符串
    for i, char in enumerate(text):
        if char.isdigit():
            if i == 0:
                result.append(char)
            else:
                new_char = str((int(char) + 1) % 10)
                result.append(new_char)
        else:
            result.append(char)
    return ''.join(result)

def replace_letters(text):
    """
    替换字符串中的字母字符，按照字母顺序替换字母。
    """
    return ''.join(shift_letter(char) for char in text)

def shift_gbk_char(char,skip_words=[]):
    """
    对GBK编码的中文汉字进行按编码顺序的替换。
    """
    try:
        # 将汉字字符转换为GBK编码的字节序列
        gbk_bytes = char.encode('gbk')
        if len(gbk_bytes) != 2:
            return char  # 如果不是双字节汉字，原样返回
        
        if char in skip_words:
            return char
        # 将字节转换成整数
        high_byte, low_byte = gbk_bytes
        
        # 对低字节进行加1操作，并处理溢出
        low_byte += 5
        if low_byte > 0xFE:
            low_byte = 0x40 if low_byte == 0xFF else 0x41  # 处理GBK的特殊区间
        
        # 将高字节和低字节重新组合
        new_bytes = bytes([high_byte, low_byte])
        
        # 将新的字节序列解码为汉字
        new_char = new_bytes.decode('gbk')
        return new_char
    except:
        return char  # 处理转换过程中可能出现的异常

def shift_gbk_string(input_string,skip_words=[]):
    """
    汉字转换
    """
    # 遍历字符串中的每个字符并进行转换
    result = []
    for char in input_string:
        result.append(shift_gbk_char(char,skip_words))
    
    # 将结果列表转换回字符串
    return ''.join(result)


def process_text(text, skip_words=[], skip_chars=[]):
    """
    处理字符串中的内容，对数字和字母字符进行替换，并跳过指定的单词和字符。
    
    :param text: 要处理的字符串
    :param skip_words: 指定不进行替换的单词列表
    :param skip_chars: 指定不进行替换的字符列表
    """
    def replacement(match):
        word = match.group(0)
        if word in skip_words:
            return word
        return replace_numbers(replace_letters(word))

    # 对字符串中的每个单词进行替换处理
    result = re.sub(r'\b\w+\b', replacement, text)

    # 处理指定不替换的字符
    for char in skip_chars:
        result = result.replace(replace_numbers(replace_letters(char)), char)
    
    return result


def process_replace(value, skip_words=[], skip_chars=[]):
    """
    根据数据类型对DataFrame中的值执行不同的替换方法。
    数值型数据执行replace_numbers，字符串型数据执行replace_letters。
    其他类型数据不执行任何操作。
    """
    if isinstance(value, (str,int, float)):
        if is_float(value):
            return replace_numbers(value)
        elif contains_chinese(value):
            return shift_gbk_string(value,skip_words)
        else:
            return process_text(value,skip_words,skip_chars)
    # elif isinstance(value, (int, float)):
    # elif is_float(value):
    #     return replace_numbers(value)
    
    else:
        return value

def is_float(s):
    """
    is number
    """
    try:
        float(s)
        return True
    except ValueError:
        return False

def contains_chinese(text):
    """
    conatains chinese
    """
    for char in text:
        if 'CJK' in unicodedata.name(char, ''):
            return True
    return False
def run_path(subdir):
    """
    取得路径
    """
    script_path = os.path.abspath(sys.argv[0])
    script_directory = os.path.dirname(script_path)
    script_directory = os.path.join(script_directory, "files", subdir)

    return script_directory


def find_file_by_prefix(directory, file_prefix):
    '''
    根据文件名前缀
    查找指定路径的文件
    返回
    如果多个，抛出异常。

    '''
    path = run_path(directory)
    all_files = os.listdir(path)
    # 在所有文件中找到匹配前缀的文件
    matching_files = [file for file in all_files if file.startswith(file_prefix)]
    if matching_files:
        return os.path.join(path,matching_files[0])
    else:
        return None

def mask_file(file_name,file_extension,m_cols,encoding,sheetnames):
    """
    加密文件指定列
    """
    dfs=[]
    if file_extension.upper() == ".CSV":
        df = pd.read_csv(file_name, skiprows=range(0, 0), na_values="None,\xa0,, ,-,--",encoding = encoding, encoding_errors='ignore')
        dfs.append(df)
    elif (file_extension.upper() == ".XLSX") or (file_extension.upper() == ".XLS") :
        for sheetname in sheetnames:
            if sheetname == 'default':
                df = pd.read_excel(file_name, skiprows=range(0, 0), na_values="None,\xa0,, ,-,--")
            else:
                df = pd.read_excel(file_name,sheet_name=sheetname, skiprows=range(0, 0), na_values="None,\xa0,, ,-,--")
            dfs.append(df)
    df_transformed = mask_dfs(dfs,m_cols)
    return df_transformed

def mask_df(df: pd.DataFrame, columns: list):
    """
    加密 DataFrame 的指定列。
    
    参数:
    df (pd.DataFrame): 输入的 DataFrame。
    columns (list): 需要处理的列索引列表。
    
    返回:
    pd.DataFrame: 处理后的 DataFrame。 skip_words
    """
    for col in columns:
        col2=col+1
        df.iloc[:, col:col2] = df.iloc[:, col:col2].applymap(lambda x: process_replace(x,skip_words=skip_words))
    return df


def mask_dfs(dfs: list, columns: list):
    """
    加密 DataFrame 的指定列。
    
    参数:
    df (pd.DataFrame): 输入的 DataFrame。
    columns (list): 需要处理的列索引列表。
    
    返回:
    pd.DataFrame: 处理后的 DataFrame。 skip_words
    """
    rdfs=[]
    for df in dfs:
        for col in columns:
            col2=col+1
            df.iloc[:, col:col2] = df.iloc[:, col:col2].applymap(lambda x: process_replace(x,skip_words=skip_words))
        rdfs.append(df)
    return rdfs

def get_all_files_and_extensions(directory):
    """
    收集指定目录下文件信息
    """
    file_info = []
    suffix ="_new"
    # 遍历指定目录及其子目录
    directory = os.path.join(DATA_PATH, directory)


    # 获取指定目录下的所有条目
    entries = os.listdir(directory)

    # 遍历条目
    for entry in entries:
        full_path = os.path.join(directory, entry)
        if os.path.isfile(full_path):
            # 获取文件名和扩展名
            file_name, file_extension = os.path.splitext(entry)
            new_file_name = f"{file_name}{suffix}{file_extension}"
            new_full_path = os.path.join(directory, DUMY_DATA, new_file_name)
            # 添加文件信息到列表
            file_info.append((file_name, file_extension, full_path, new_full_path))

    return file_info

def process_all_pat():
    """
    处理指定路径下指定文件的指定列
    """
    for path,file_info in all_path.items():
        print(f"Path: {path}")
        files_and_extensions = get_all_files_and_extensions(path)
        
        for file_pre_name,m_cols,encoding,sheetnames in file_info:
            print(f"  File Name: {file_pre_name},{m_cols},{sheetnames}")
            for file_name, file_extension,full_path,new_full_path in files_and_extensions:
                if file_name.startswith(file_pre_name):
                    dfs = mask_file(full_path,file_extension,m_cols,encoding,sheetnames)

                    if file_extension.upper() == ".CSV":
                        dfs[0].to_csv(new_full_path, index=False,encoding=encoding, na_rep='')
                    elif (file_extension.upper() == ".XLSX") or (file_extension.upper() == ".XLS"):
                        with pd.ExcelWriter(new_full_path) as writer: # pylint: disable=abstract-class-instantiated
                            for index, sheetname in enumerate(sheetnames):
                                dfs[index].to_excel(writer, sheet_name=sheetname, index=False)


process_all_pat()
