"""
# Data Loading Action
"""
import os
import sys
from datetime import datetime
import traceback
import json
import re
import math
import codecs
from dateutil import parser
import pandas as pd
from pandas import Timestamp

from exceptions import CustomException,ConcurrencyException
from utils.db_util import Database
from utils.file_util import FileUtil
from utils.comm_util import CommUtil
from global_state import GlobalState

state = GlobalState()

class LoadAction:
    """
    # Data Loading Action
    """
    C_SRC = "src_col"
    C_DST ="dst_col"
    # MYM2U = 'MYM2U'
    # MYMBB = 'MYMBB'

    EXT_CSV = 'csv'
    EXT_XLSX = 'xlsx'
    EXT_XLS = 'xls'
    EXT_TXT = 'txt'

    C_INDEX ="col_index"
    C_TYPE ="col_type"
    C_NAME ="col_name"
    C_FMT = "col_format"
    C_LEN = "col_length"
    C_NVL = "col_isnull"

    TP_NUM = 'num'
    TP_STR = 'str'
    TP_DATE = 'date'
    TP_TIME = 'time'
    TP_PCT = 'persent'
    COL_N_NVL = 'notnull'
    TP_D_TZ = 'TZ'
    FM_DUMPLICATE = 'dump'

    bank_diff_col = ['otc_region', 'account_number', 'value_date', 'amount', 'balance', 'data_key','bank_name']
    bank_cod_diff_col = ['otc_region', 'account_number', 'value_date', 'amount','data_key','bank_name']

    POST_ACT = "_PostAction"
    ACT_LOCK = "lock"
    ACT_FREE = "un_lock"

    # GB='gb2312'
    # UTF8='utf-8'

    def  __init__(self, name: str, prefix: str, region: str,logger) -> None:
        self.name = name
        self.prefix = prefix
        self.region = region
        self.logger = logger
        self.bank_data = 0
        self.file_parts = 0
        self.na_values = "" #[None,'\xa0', '',' ','-','--']
        self.db = Database(logger=logger)
        self.file_util = FileUtil(state = state, logger=logger)
        self.comm_util = CommUtil(logger=logger)

        self.logger.info(f'Init Load Action Class. to load {prefix}')

    def run_path(self,subdir):
        '''
        取得运行路径
        '''
        # # script_path = get_repo_path()
        # print('abspath')
        # # script_path = os.path.abspath('default_repo/')
        # script_path = 'default_repo/'
        # print(script_path)

        # script_directory = os.path.dirname(script_path)
        # script_directory = os.path.join(script_directory, 'files',subdir)

        script_path = os.path.abspath(sys.argv[0])
        script_directory = os.path.dirname(script_path)
        script_directory = os.path.join(script_directory, 'files',subdir)

        return script_directory
        

    def read_pfile_to_table(self,region,prefix,action_user="system",kicker="comm"):
        '''
        读取数据文件到DB表
        指定参数 地区，文件名
        call by webapi 
        call by aging load alocate
        '''
        ret = False
        self.logger.info(f'Start load file {prefix}.')
        self.region = region
        self.prefix = prefix
        bill_files=["Invoice weekly Report","Invoice Pool List","VAT issue list"]
        action_name=f"{region}{self.POST_ACT}"
        # 不是agingaloc触发的情况下，需要skip load 。 待定 并且 不是batch触发  ("batch" in action_user) and ("@" not in action_user)
        # 不是billing 对象文件的情况下，需要 skip load
        if (kicker!="aging" and (not self.is_prefix_in_bill_files(prefix,bill_files))):
            if self.comm_util.check_is_lock(region,action_name,action_user,kicker):
                self.logger.info(f'Load Action is locking  :{prefix}.')
                return ret
            self.comm_util.update_div_status(region=region,action_name=action_name,ac_status=self.ACT_LOCK,ac_user=action_user)

        def_list = self.get_file_to_raw_def(prefix,region)
        self.file_parts = len(def_list)
        state.set_total_parts(file_parts=self.file_parts)
        
        if not def_list.empty:
            for ind_d, def_row in def_list.iterrows():
                ret = self.read_def_file_body(def_row,action_user)
        else:
            bz_date = self.comm_util.get_daytime_string()
            self.comm_util.update_loading_status(region = self.region, action_name='read_file_to_table',business_date=bz_date,
                                                status=self.comm_util.BL_STS['9'],
                                                bl_message=f'Failed.There is no file :{self.prefix} .please check filename.',ac_user=action_user)
        # 当agingaloc之外的情况下，解锁。agingaloc时，不做锁操作
        if (kicker!="aging"):
            self.comm_util.unlock_action(region=region,action_name=action_name,ac_status=self.ACT_FREE,ac_user=action_user)

        self.logger.info(f'Finish load file {prefix}.')

        return ret

    # def read_file_to_table(self,action_user="system"):
    #     '''
    #     读取数据文件到DB表
        
    #     '''
    #     self.logger.info(f'Start load file {self.prefix}.')

    #     def_list = self.get_file_to_raw_def(self.prefix,self.region)
    #     if not def_list.empty:
    #         for ind_d, def_row in def_list.iterrows():
    #             self.read_def_file_body(def_row,action_user)
                
    #     self.logger.info(f'Finish load file {self.prefix}.')

    #     return None
    
    def read_region_all_file(self,action_user="system"):
        '''
        读取全部文件配置
        call by timer schedule
        '''
        self.logger.info(f'Start load region {self.region} all files.')

        action_name=f"{self.region}{self.POST_ACT}"
        if self.comm_util.check_is_lock(self.region,action_name,action_user):
            self.logger.info(f'Load Action is locking  :{self.prefix}.')
            return self.bank_data
    
        self.comm_util.update_div_status(region=self.region,action_name=action_name,ac_status=self.ACT_LOCK,ac_user=action_user)


        def_list = self.get_region_file_to_raw_def(self.region)
        
        if not def_list.empty:
            for ind_d, def_row in def_list.iterrows():
                # 定时任务下载1sheet文件
                state.set_total_parts(file_parts=1)
                self.read_def_file_body(def_row,action_user)
        self.logger.info(f'Finish load region {self.region} all files.')

        self.comm_util.unlock_action(region=self.region,action_name=action_name,ac_status=self.ACT_FREE,ac_user=action_user)

        return self.bank_data

    def read_def_file_body(self,def_row,action_user):
        '''
        根据表sc_raw_file_define 的定义，读取文件数据
        '''
        ret = True
        target_file,bucket_name=None,None
        file_prefix = def_row['file_action_name']
        file_sheet =  def_row['sheet_name']
        file_action_name = def_row['file_action_name']
        bz_date = self.comm_util.get_daytime_string()
        file_maping_str = def_row['file_raw_field_mapping']
        raw_tbl_mapping_str = def_row['raw_bl_field_mapping']
        file_ext = def_row['file_ext']
        data_area = def_row['data_area']
        sheet_name = def_row['sheet_name']
        file_type = def_row['file_type']
        prefix = def_row['file_prefix']
        sub_dir =  def_row['otc_region']
        raw_table_name = def_row['raw_table_name']
        bl_table_name =  def_row['bl_table_name']
        encode = def_row['file_encode']
        try:
            # read file to df
            target_file,bucket_name = self.file_util.find_file_by_prefix(directory=sub_dir,file_prefix=prefix)         

            if target_file:
                # 取得常量
                self.get_comm_defines()
                # 更新流程控制状态表
                self.comm_util.update_loading_status(region = self.region, action_name=file_action_name,business_date=bz_date,
                            status=self.comm_util.BL_STS['2'],bl_message=f'load file:{self.prefix} start.',ac_user=action_user)
                # 更新文件load控制表 源文件已经被移动，并发控制解除 0
                self.comm_util.update_file_ctl_status(ac_status=0,prefix=prefix,region=self.region,ac_user=action_user)

                column_definitions = self.file_column_define(file_maping_str)
                col_dtype = self.generate_dtype_from_result_list(column_definitions)

                df = self.read_file(file_ext=file_ext,file_name=target_file,sheet_name = sheet_name, data_area=data_area, dtype = col_dtype,encoding = encode)
                # 检查文件行数
                self.check_total_count(df)
                raw_df,excep_data = self.convert_csv_to_dataframe(df,column_definitions,sheet_name = sheet_name)
                
                if excep_data:
                    self.output_file(target_file,excep_data,'err_data')
                # IN 特殊处理
                self.set_bank_customer_account(region = self.region,src_df= raw_df,table_name =raw_table_name)

                if raw_tbl_mapping_str:
                    # 列映射定义
                    raw_column_definitions = self.raw_column_define(raw_tbl_mapping_str)
                    # raw data to bl data
                    bl_df = self.create_target_dataframe(raw_df,raw_column_definitions)

                    # 检查银行数据是否重复
                    if self.bank_data_multi_upload(table_name=bl_table_name,file_df=bl_df,region = self.region):
                        self.logger.info(f'Band statment data already uploaded. file name: {prefix}, sheet{file_sheet} action name:{file_action_name}')
                        bl_msg = f'load file:{self.prefix} Stoped.The bank statment data already uploaded .'
                        self.save_log_status(file_action_name,self.comm_util.BL_STS['9'], bz_date, bl_msg,action_user)
                        # 备份文件 银行文件出错，不备份 保存在原位置
                        self.rename_file(target_file,bucket_name,back_name="dupdata_")
                        # self.file_util.backup_file(target_file,bucket_name)
                        return ret
                    else:
                        # 特殊处理
                        bl_df = self.re_orgnaize_df(raw_table_name,bl_table_name,bl_df)
                        
                        # 提交raw 数据表
                        self.update_talbe(file_type, raw_table_name, raw_df,'raw')
                        # 提交 bl数据表
                        if not bl_df.empty:
                            self.update_talbe(file_type, bl_table_name, bl_df, 'bl')
                        # 特殊处理
                        self.set_bank_info_after_update(region=self.region,table_name=bl_table_name)

                        self.logger.info(f'Transfor to {bl_table_name} Successfully {prefix} ')
                        
                else:
                # 如果没有bl表，单独登录raw数据
                    # 提交raw 数据表
                    self.update_talbe(file_type, raw_table_name, raw_df, 'raw')
                
                # 备份文件
                self.file_util.backup_file(target_file,bucket_name)
                self.logger.info(f'Load file Successfully file name: {prefix}, sheet{file_sheet} action name:{file_action_name}')
            
                bl_msg = f'load file:{self.prefix} Successfully.'

                self.save_log_status(file_action_name,self.comm_util.BL_STS['3'], bz_date, bl_msg,action_user)
            else:
                ret = False
                self.logger.info(f'There is no file : {prefix}, sheet: {file_sheet} action name:{file_action_name}')
            
                # self.comm_util.update_loaded_status(region = self.region, action_name=file_action_name,business_date=bz_date,
                #                                 status=self.comm_util.BL_STS['9'],
                #                                 bl_message=f'load file:{self.prefix} Failed.There is no file :{self.prefix} .please check filename.')
            

        # except CustomException as e:
        #     self.logger.error(e.message)
        # except Exception as e:
        #     self.logger.error(str(e.args))
        except (ConcurrencyException) as e:
            self.logger.info(f"Load file control. skiped. Region:{self.region},user {action_user}, {e}")
        except (CustomException, Exception) as e:
            ret=False
            self.logger.error(e.message if isinstance(e, CustomException) else str(e.args))
            self.logger.error(traceback.format_exc())
            self.logger.error(f"load file exception error. region: {self.region} .file name: {prefix}")
            self.comm_util.update_loaded_status(region = self.region, action_name=file_action_name,business_date=bz_date,
                                                status=self.comm_util.BL_STS['9'],
                                                bl_message=f'load file:{prefix} Failed .',ac_user=action_user)
            self.rename_file(target_file,bucket_name,back_name="error_")
        return ret

    def rename_file(self,target_file,bucket_name,back_name="back_"):
        """
        出错的文件在当前路径备份
        """
        self.logger.debug(f"back up file in same bucket. target_file:{target_file}. bucket_name:{bucket_name}")
        if (target_file is not None) and (bucket_name is not None):
            self.file_util.rename_live_file(target_file,bucket_name,back_name=back_name)
            self.logger.debug(f"back up file success . target_file:{target_file}. bucket_name:{bucket_name}")

    def save_log_status(self, file_action_name, status, bz_date, bl_msg, action_user):
        """
        更新日志
        """
        self.comm_util.update_loaded_status(region = self.region, action_name=file_action_name,business_date=bz_date,
                                                status=status,bl_message=bl_msg,ac_user=action_user)

    def update_talbe(self,file_type, table_name, table_df, raw_flg = 'raw' ):
        '''
        更新数据到表
        当配置为clean的时候，删除全部数据

        '''
        if (file_type == 'clean') or ((file_type == 'cleanraw') and (raw_flg == 'raw')):
            if table_name=='bl_aging_history':
                self.delete_all_by_region(table_name=table_name,region=self.region)
            else:
                self.delete_all(table_name=table_name)
        # table_df['update_time'] = datetime.now()
        if(len(table_df)>0):
            if not self.db.upsert_table(table_df,table_name):
                self.logger.error(f'Finished load file {self.prefix} failed .')
                raise CustomException(f'Finished load file {self.prefix} table {table_name} failed .')

    def delete_all(self,table_name):
        '''
        删除全部数据
        '''
        sql_query = f"delete from {table_name} "
        parameters = ( )
        self.db.execute_update_query(sql_query,parameters)

    def delete_bank_errdata(self,region,bank_branch_name,cod_type):
        '''
        删除银行错误数据

        '''
        if region=='CN':
            sql_query = "delete from bl_bank_statement_err where otc_region = %s and bank_branch_name =%s and trans_type = %s "
            parameters = ( region,bank_branch_name,cod_type)
        else:
            sql_query = "delete from bl_bank_statement_err where otc_region = %s and bank_branch_name =%s "
            parameters = ( region,bank_branch_name)
        
        self.logger.debug(f"delete bank errdata SQL: {sql_query} . param region:{region}.branch:{bank_branch_name}. cod:{cod_type}")

        self.db.execute_update_query(sql_query,parameters)


    def delete_all_by_region(self,table_name,region):
        '''
        删除全部数据
        '''
        sql_query = f"delete from {table_name} where otc_region = %s "
        parameters = ( region,)
        self.db.execute_update_query(sql_query,parameters)

    def bank_data_multi_upload(self, table_name,file_df,region):
        """
        检查银行数据是否重复上传
        """
        if table_name == 'bl_bank_statement':
            branch_bank = file_df.loc[0, 'bank_branch_name']
            cod_type=''
            if self.region =="CN":
                cod_type = file_df.loc[0, 'trans_type']
            self.delete_bank_errdata(self.region,branch_bank,cod_type)
            bank_db_df = self.get_table_bank_data(region)
            same_row = self.comp_bank_data(file_df,bank_db_df,cod_type)
            if not same_row.empty  :
                # 保存有重复信息的处理
                self.save_err_bank_data(same_row)
                self.save_to_log(err_row=same_row)
                return True
        return False
    
    def save_to_log(self, err_row):
        """
        保存到日志
        """
        self.logger.error(f'Bank statment data upload Duplicate count {len(err_row)}')
        self.logger.error(err_row)
    def save_err_bank_data(self,err_row):
        """
        保存到错误信息表
        """
        err_row['update_time'] = datetime.now()
        # bl_bank_statement_err
        bl_bank_statement_err = 'bl_bank_statement_err'
        
        if not self.db.upsert_table(err_row,bl_bank_statement_err):
            self.logger.error('update table bl_bank_statement_err failed .')


    def comp_bank_data(self,file_df,table_df,cod_type):
        """
        比较数据是否存在相同内容
        """
        cols = self.bank_diff_col
        # 当COD 顺丰的时候，balance在文件中不存在，所以，合并相同内容不用balance
        if cod_type=='shunfeng':
            cols = self.bank_cod_diff_col

        # 合并两个 DataFrame，并通过 indicator 标记每行数据的来源
        merged_df = pd.merge(file_df, table_df, on=cols, how='outer', indicator=True)
        # 筛选出两边都有的行
        same_rows = merged_df[merged_df['_merge'] == 'both']
        same_rows_values = same_rows[cols]
        for col in cols:
            table_df[col] = table_df[col].astype(same_rows_values[col].dtype)
        matching_rows = table_df.merge(same_rows_values, on=cols, how='inner')
        return matching_rows


    def get_table_bank_data(self,region):
        """
        取得当日的bank数据
        """
        sql_query = """SELECT * FROM bl_bank_statement WHERE otc_region = %s """
                        # and value_date = DATE_TRUNC('day', CURRENT_DATE) - INTERVAL '1 day'  """
        parameters = (region,)
        df_rg = self.db.execute_query_to_pandas(sql_query,parameters)
        return df_rg

    def output_file(self,org_file,file_data,addition):
        '''
        输出文件
        '''
        # 确保 org_file 是绝对路径
        org_file = os.path.abspath(org_file)

        # 获取文件名和扩展名
        path, file_name = os.path.split(org_file)
        file_name, file_extension = os.path.splitext(file_name)

        # Get the current date and time
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")  # Format can be adjusted as needed

        # 构建新的文件名
        new_filename = f"{addition}_{file_name}{formatted_datetime}.csv"
        new_fullfile_name = os.path.join(path, new_filename)

        # 将列表内容写入新文件
        df = pd.DataFrame(file_data)
        df.to_csv(new_fullfile_name, index=False)
        # 保存这个文件到云存储
        if self.file_util.is_local == 0:
            self.move_file_to_cos(region=self.region,item_name=new_filename,out_file_path=new_fullfile_name)
        

    def move_file_to_cos(self,region, item_name, out_file_path):
        """
        保存到云存储
        """
        self.file_util.upload_file_2_bucket(region, item_name, out_file_path)
        os.remove(out_file_path)
    # def find_file_by_prefix(self,directory, file_prefix):
    
    def read_file(self, file_ext,file_name, sheet_name, data_area, dtype,encoding = 'utf-8'):
        '''
        读文件到DF
        根据定义的数据起始位置 行数

        '''
        if data_area.isdigit():
            row_index = int(data_area)
            if file_ext == self.EXT_CSV:
                df = pd.read_csv(file_name, skiprows=range(0, row_index), encoding = encoding,
                                 encoding_errors='ignore',na_values=self.na_values,dtype=dtype,thousands=',')
            elif file_ext == self.EXT_XLSX:
                if sheet_name == 'default':
                    df = pd.read_excel(file_name, skiprows=range(1, row_index), na_values=self.na_values,dtype=dtype,thousands=',')
                else:
                    df = pd.read_excel(file_name, sheet_name = sheet_name, skiprows=range(1, row_index), na_values=self.na_values,dtype=dtype,thousands=',')
            elif file_ext == self.EXT_XLS:
                if sheet_name == 'default':
                    df = pd.read_excel(file_name, skiprows=range(1, row_index), engine = 'xlrd', na_values=self.na_values,dtype=dtype,thousands=',')
                else:
                    df = pd.read_excel(file_name, sheet_name = sheet_name, skiprows=range(1, row_index), engine = 'xlrd',na_values=self.na_values,dtype=dtype,thousands=',')
        else:
            if file_ext == self.EXT_TXT:
                df = self.read_text_file(file_ext=file_ext, file_name = file_name,data_area=data_area)
            else:
                df = self.read_complex_file(file_ext=file_ext, file_name = file_name,data_area=data_area,encoding = encoding)
        return df

    
    def read_one_format_text(self,content,pattern):
        """
        读取一个格式的固定长文本
        """
        account_orders = []
        release_order = {}
        current_datetime = datetime.now()
        cnt = 1
        for line in content.split('\n'):
            match = re.match(pattern[0]['pattern'], line)
            if match:
                if release_order:
                    account_orders.append(release_order)
                    release_order = {}
                account_number,account_name,release_date,releaseby,sales_order,currency,order_value = match.groups()
                release_order['otc_region'] = self.region
                release_order['customer_id'] = account_number
                release_order['customer_name'] = account_name
                release_order['sales_order'] = str(sales_order).replace("-", "")
                release_order['order_value'] = order_value
                release_order['order_curr'] = currency
                release_order['release_date'] = release_date
                release_order['release_by'] = releaseby
                release_order['update_time'] = current_datetime
        if release_order:
            account_orders.append(release_order)
        df = pd.DataFrame(account_orders)
        self.logger.debug(f"SalesOrder release file data count: {len(df)}")
        return df
    
    def read_one_format_text2(self,content,pattern):
        """
        读取一个格式的固定长文本
        """
        account_orders = []
        release_order = {}
        current_datetime = datetime.now()
        cnt = 1
        for line in content.split('\n'):
            # match = re.match(pattern[0]['pattern'], line)
            match = re.findall(pattern[0]['pattern'], line)
            if match:
                match.extend([""] * (8 - len(match)))
                if release_order:
                    account_orders.append(release_order)
                    release_order = {}
                account_number,account_name,overdue_day_3,overdue_day_2,overdue_day_1,overdue_day_0,turnover_last_year,turnover_actual_year = match
                if account_number.strip().isdigit():
                    release_order['otc_region'] = self.region
                    release_order['customer_id'] = account_number.strip()
                    release_order['customer_name'] = account_name.strip()
                    release_order['overdue_day_3'] = self.convert_minus(overdue_day_3)
                    release_order['overdue_day_2'] = self.convert_minus(overdue_day_2)
                    release_order['overdue_day_1'] = self.convert_minus(overdue_day_1)
                    release_order['overdue_day_0'] = self.convert_minus(overdue_day_0)
                    release_order['turnover_last_year'] = turnover_last_year.strip()
                    release_order['turnover_actual_year'] = turnover_actual_year.strip()
                    release_order['update_time'] = current_datetime
        if release_order:
            account_orders.append(release_order)
        df = pd.DataFrame(account_orders)
        self.logger.debug(f"Over due file data count: {len(df)}")
        return df
    def convert_minus(self,overdueday):
        """
        数字转换
        """
        overdueday = overdueday.strip()
        # 如果字符串以负号结尾，将其转换为负数
        if overdueday.endswith("-"):
            return -int(overdueday[:-1])  # 去掉最后一个字符，并将剩余部分转换为整数，然后取负数
        elif overdueday=='':
            return ''
        else:
            return int(overdueday)  # 直接将字符串转换为整数
        
    def read_tow_format_text(self,content,pattern):
        """
        读取两个格式的固定长文本
        """
        accounts = []
        current_account = {}
        current_account_number = None
        current_datetime = datetime.now()
        # 按行分割文件内容，然后逐行处理
        for line in content.split('\n'):
            current_account = self.get_2_fmt_text_data(pattern, accounts, current_account, current_account_number, line)
        # 循环结束后，添加最后一个账户到列表中
        if current_account:
            accounts.append(current_account)

        # 创建一个空的 DataFrame，用于存储展开的账户和订单信息
        expanded_accounts = []
        # 遍历账户列表，将每个订单信息与账户信息合并，并添加到新列表中
        for account in accounts:
            for order in account['orders']:
                # 创建一个包含账户信息和订单信息的字典
                account_order_info = {
                    'otc_region' : self.region,
                    'customer_id': account['customer_id'],
                    'customer_name': account['customer_name'],
                    'sales_order': str(order['order_ref']).replace("-", ""),
                    'order_value': order['order_value'],
                    'order_curr': order['order_curr'],
                    'update_time': current_datetime
                }
                # 将字典添加到列表中 
                expanded_accounts.append(account_order_info)
        # 将新列表转换为 DataFrame
        df = pd.DataFrame(expanded_accounts)
        self.logger.debug(f"SalesOrder on hold file data count: {len(df)}")
        return df

    def get_2_fmt_text_data(self, pattern, accounts, current_account, current_account_number, line):
        """
        解析行，抽取数据到list
        """
        match = re.match(pattern[0]['pattern'], line)
        if match:
            customer_id, customer_name = match.groups()
                # 如果遇到新的账户号码，更新当前账户
            if current_account_number != customer_id:
                if current_account:
                        # 如果当前账户不为空，将其添加到accounts列表中
                    accounts.append(current_account)
                    # 创建新的账户字典，并更新当前账户号码
                current_account = {'customer_id': customer_id, 'customer_name': customer_name, 'orders': []}
                current_account_number = customer_id
            
            # 匹配 Order Ref, Order Value, Order Curr
        match = re.match(pattern[1]['pattern'], line)
        if match:
            order_ref, order_value, order_curr = match.groups()
                # 将新的订单信息添加到当前账户的Orders列表中
            current_account['orders'].append({
                    'order_ref': order_ref,
                    'order_value': order_value,
                    'order_curr': order_curr
                })
            
        return current_account
    
    def read_text_file(self,file_ext,file_name, data_area):
        """
        读取固定长文本文件
        """
        data = json.loads(data_area)
        file_type = data['file_type']
        pattern = data['regex']
        # with open(file_name, 'r',encoding='utf-8') as file:
        with codecs.open(file_name, "r", encoding="utf-16") as file:
            content = file.read()
        if file_type == 'release':
            df = self.read_one_format_text(content = content, pattern = pattern)
        elif  file_type == 'hold':
            df = self.read_tow_format_text(content = content, pattern = pattern)
        elif  file_type == 'overdue':
            df = self.read_one_format_text2(content = content, pattern = pattern)
        return df
    
    def read_complex_file(self,file_ext,file_name, data_area,encoding):
        '''
        # 读取特殊格式的CSV文件
        配置内容Json格式，如下

        {
            "row": [{
                "rowindex": 5,
                "prefix": "REPORT DATE : ",
                "type":"date",
                "format":"%Y-%m-%d",
                "targetcol":"report_date"
            }]
            "area": [{
                "line": 10,
                "end":"SERVICE"
            }]
        }
        '''
        data = json.loads(data_area)
        rows_def = data['row']
        areas_def = data['area']
        # 读取区域数据到DF
        area_dfs = []
        # 遍历配置，取得所有配置数据
        for ad in areas_def:
            area_df = self.read_area_value(file_ext = file_ext, file_name=file_name,area_def=ad,encoding = encoding)
            area_dfs.append(area_df)
        # 合并DF
        merged_df = pd.concat(area_dfs, ignore_index=True)

        # 遍历配置，取得所有配置数据
        for rd in rows_def:
            col_name = rd['targetcol']
            value = self.read_line_value(file_ext= file_ext,file_name=file_name,row_def=rd,encoding = encoding)
            merged_df[col_name] = value
        return merged_df
    
    # final_df = pd.concat([df1_selected, df2_selected], ignore_index=True)


    def read_line_value(self,file_ext,file_name,row_def,encoding):
        '''
        读取指定行的值
        并根据配置格式化

        '''
        ridx = row_def['rowindex']
        prefix = row_def['prefix']
        data_type = row_def['type']
        data_format = row_def['format']
        cidx = row_def['colindex']
        # 取得文件指定行的数据
        df = self.read_csv_row(file_ext = file_ext,file_name = file_name, nrow = ridx,encoding = encoding)
        # 取出最后一行数据
        selected_row = df.iloc[ridx -1 ]
        # 取出第一列数据 过滤掉prefix
        value = str(selected_row[cidx]).replace(prefix,'')
        # 根据配置定义做格式化
        value = self.format_value_by_type(value=value,column_type=data_type,column_format=data_format,column_name='')
        return value


    def read_area_value(self,file_ext,file_name,area_def,encoding):
        '''
        # 根据配置内容，读入csv数据到DF
        
        '''
            # 起始行 不包含表头
        row_from = area_def['line']
        # 取得截至标志
        row_end = area_def['end']
        # 列类型定义
        col_types = area_def['types']

        dtype_dict = {col_type['col']: col_type['type'] for col_type in col_types}

        df = self.read_csv_area(file_ext = file_ext, file_name = file_name,row_from = row_from,dtype=dtype_dict,encoding = encoding)
        # 过滤定义
        col_trims = area_def['trims']
        new_df = pd.DataFrame(columns=df.columns)
        # 遍历 DataFrame 的行
        for index, row in df.iterrows():
            if (row[0] == row_end) or (str(row[0]).startswith(row_end)):
                break  # 当遇到 'mark' 时跳出循环
            new_df = new_df.append(row)
        # 创建一个字典，键是列号，值是需要替换的字典列表
        dtrims = {item["col"] : item["vals"] for item in col_trims}

        if dtrims:
            # 遍历字典，对每一列进行替换
            for index, row in new_df.iterrows():
                for col, vals in dtrims.items():
                    tmp = str(row[f'{col}'])
                    for val_dict in vals:
                        val_to_replace = val_dict["val"]
                        tmp = tmp.replace(val_to_replace, '')
                    new_df.loc[index,f'{col}'] = tmp

        return new_df

    
    def read_csv_row(self,file_ext,file_name,nrow,encoding):
        '''
        # 读入文件行
        
        '''
        if file_ext == self.EXT_CSV:
            df = pd.read_csv(file_name,nrows= nrow, na_values=self.na_values,encoding = encoding)
        elif file_ext == self.EXT_XLSX:
            df = pd.read_excel(file_name,nrows= nrow, na_values=self.na_values)
        return df
    

    def read_csv_area(self,file_ext,file_name,row_from,dtype,encoding):
        '''
        # 读入文件区域到DF
        
        '''
        if file_ext == self.EXT_CSV:
            df = pd.read_csv(file_name,skiprows=range(0, row_from),dtype = dtype, na_values=self.na_values,encoding = encoding)
        elif file_ext == self.EXT_XLSX:
            df = pd.read_excel(file_name,skiprows=range(0, row_from),dtype = dtype, na_values=self.na_values)
        return df

    

    def file_column_define(self,maping_str):
        '''
        解析文件 数据表映射定义
        存储为 List Dict结构，方便使用

        '''
        result_list = []
        for line in maping_str.split(';'):
            if line:
                parts = line.strip().split('|')
                col_index, col_name, col_type, col_format, col_length, col_isnull = parts
                col_info = {
                    self.C_INDEX: int(col_index),
                    self.C_NAME: col_name,
                    self.C_TYPE: col_type,
                    self.C_FMT: col_format,
                    self.C_LEN: col_length,
                    self.C_NVL: col_isnull
                }
                result_list.append(col_info)
        return result_list

    def map_col_type_to_dtype(self,col_type):
        '''
        # 定义映射关系，将col_type映射到Pandas支持的数据类型
        '''
        type_mapping = {
            'str': 'object',
            'num': 'float',
            'date': 'object',
            'time': 'object',
            # 添加其他可能的映射关系
        }
        
        # 根据映射关系获取Pandas数据类型
        dtype = type_mapping.get(col_type, 'object')
        return dtype

    def generate_dtype_from_result_list(self,result_list):
        ''' 
        # 生成dtype字典
        '''
        dtype_dict = {col_info['col_index']: self.map_col_type_to_dtype(col_info['col_type']) for col_info in result_list}
        return dtype_dict


    def raw_column_define(self, maping_str):
        '''
        解析列名到列名的定义映射
        到List Dict结构
        SG|otc_region;account_name|account_name;account_number|account_number;
        '''
        result_list = []
        for line in maping_str.split(';'):
            if line:
                parts = line.strip().split('|')
                col_src, col_dst = parts
                col_info = {
                    self.C_SRC: col_src,
                    self.C_DST: col_dst
                }
                result_list.append(col_info)
        return result_list


    def format_column_value(self,column_definition, value):
        '''
        根据字段类型定义，
        日期型的数据根据format定义，转换格式
        异常情况下，抛出异常

        '''
        column_name = column_definition[self.C_NAME]
        column_type = column_definition[self.C_TYPE] 
        column_format = column_definition[self.C_FMT]
        column_length = column_definition[self.C_LEN]
        column_isnull = column_definition[self.C_NVL]

        if column_isnull:
            if column_isnull == self.COL_N_NVL:
                if (value == '') or (value is None) or (str(value) == 'nan'):
                    raise CustomException(f"Data should set value '{column_name}' ")

        if column_length:
            if(str(value) == 'nan'):
                return None
            else:
                if (column_format == self.FM_DUMPLICATE):
                    value = self.remove_duplicates(str(value))
                if len(str(value)) > int(column_length):
                        raise CustomException(f"Data length exceeds : [{column_name}],  value is: [{value}]. defined limit length is: [{column_length}]")
            
        return self.format_value_by_type(value = value,column_type= column_type,
                                         column_format=column_format,column_name=column_name)
    
    def process_string(self,input_string):
        """
        trim the last .0
        """
        # 判断字符串末尾是否存在 .0
        if input_string.endswith('.0'):
            # 判断字符串长度是否小于10
            if len(input_string) < 10:
                # 去掉字符串末尾的.0
                processed_string = input_string[:-2]
                return processed_string
        # 如果条件不满足，则返回原始字符串
        return input_string

    def remove_duplicates(self,input_string, delimiter='\\'):
        '''
        有些文件的数据重复内容太多，需要过滤掉重复值

        '''
        # 使用 set 来过滤重复内容
        filtered_set = set(input_string.split(delimiter))

        # 将集合转换回字符串
        filtered_string = delimiter.join(filtered_set)

        return filtered_string

    def format_value_by_type(self,value,column_type,column_format,column_name):
        '''
        格式化
        '''
        if column_type == self.TP_STR:
            
            if(str(value) == 'nan'):
                return ''
            else:
                if (column_format == self.FM_DUMPLICATE):
                    value = self.remove_duplicates(str(value))
                    return value
                else:
                    value = self.process_string(str(value))
                    return str(value).replace('\xa0', '')
        elif column_type == self.TP_DATE:
            return self.format_date(value=value, column_format=column_format,column_name=column_name)
        elif column_type == self.TP_TIME:
        
            return self.format_time(value=value, column_format=column_format,column_name=column_name)
        
        elif column_type == self.TP_NUM:
        
            return self.format_num(value = value, column_name = column_name)
        
        elif column_type == self.TP_PCT:
            try:
                return float(str(value).replace('%',''))/100
            except (ValueError, TypeError) as e1:
                raise CustomException("Rate percent type is wrong for column '{}'.".format(column_name),e = e1)
        else:
            raise CustomException("Unsupported column type '{}' for column '{}'.".format(column_type, column_name))

    def format_num(self,value,column_name):
        '''
        格式化数字
        '''
        try:
            if self.is_numeric(value):
                if math.isnan(value):
                    return 0
                else:
                    return value
            else:
                value = str(value).replace(',','').replace('-','').replace(' ','')
                if '.' in str(value):
                    return float(value)
                elif value == '':
                    return 0
                else:
                    return int(value)
        except (ValueError, TypeError) as e:
            raise CustomException("Number type is wrong for column '{}'.".format(column_name),e = e)

    def format_time(self,value,column_name,column_format):
        '''
        格式化时间
        '''
        try:
            if column_format == self.TP_D_TZ:
                if len(value) > 8:
                    time_part = str(value).split()[0]
                    return parser.parse(time_part).time()
                else :
                    return None
            else:
                if type(value) is datetime or type(value) is Timestamp:
                    return value
                else:  
                    return datetime.strptime(value, column_format).time()
        except (ValueError, TypeError) as e:
            raise CustomException( message= f"Time type is wrong for column '{column_name}'.",e = e)
                    

    def format_date(self,value,column_name,column_format):
        '''
        格式化日期
        '''
        try:
            if column_format == self.TP_D_TZ:
                if len(value) > 8:
                    time_part = str(value).split()[0]
                    return parser.parse(time_part).date()
                else :
                    return None
            else:
                if pd.isna(value):
                    return datetime.min
                elif isinstance(value, datetime) or isinstance(value, Timestamp):
                    return value
                else:
                    # return parser.parse(str(value)).strftime("%Y-%m-%d")
                    # return datetime.strptime(str(value), column_format).date()
                    return self.format_uniform_date(value=value,column_format=column_format)
        except (ValueError, TypeError) as e:
            raise CustomException(message= f"Data type is wrong for column '{column_name}' Value [{value}].",e = e)

    def format_uniform_date(self,value,column_format,uniform_format='%Y-%m-%d'):
        """
        处理非标准日期格式字符串
        当存在与定义格式不同的日期字符串时，返回其自身日期值
        """
        try:
            return datetime.strptime(str(value), column_format).date()
        except (ValueError, OverflowError) as e:
            return parser.parse(str(value)).strftime(uniform_format)
        
    def is_numeric(self,value):
        '''
        是否数字类型
        '''
        return isinstance(value, (int, float, complex))


    def convert_csv_to_dataframe(self, csv_data, column_definitions,sheet_name):
        '''
        根据定义 
        文件列定义，列名
        转换为DF的列名

        '''
        dest_columns = []
        dest_data = []
        excep_data = []

        for column_definition in column_definitions:
            dest_columns.append(column_definition[self.C_NAME])

        for idx, row in csv_data.iterrows():
            dest_row = []
            try:
                for column_definition in column_definitions:
                    dest_row.append(self.format_column_value(column_definition, row.iloc[column_definition[self.C_INDEX]]))
            except (CustomException , TypeError) as e:
                row['err_message'] = e.message
                excep_data.append(row)
                self.logger.error(f"Input file format error at sheet: {sheet_name} row index: [{idx}] , {e.message}. ")
                # self.logger.error(e)
                continue

            dest_data.append(dest_row)

        dest_df = pd.DataFrame(dest_data, columns=dest_columns)
        return dest_df,excep_data

    def create_target_dataframe(self, src_df, mapping_list):
        '''
        DF to DF convert

        根据 raw DF to bl DF 的字段映射定义
        把 src_data rawDF 转换为 dest_df blDF

        '''

        dest_df = pd.DataFrame(dtype=object)

        add_cols = {}
        for mapping in mapping_list:
            col_src = mapping[self.C_SRC]
            col_dst = mapping[self.C_DST]

            # Check if source column exists in the source DataFrame
            if col_src in src_df.columns:
                # Copy the source column values to multiple destination columns dest_val1 = dest_val1.replace('\xa0', '')
                dest_df[col_dst] = src_df[col_src].copy().replace('\xa0', '')
            else:
                # 定义的源列名不在表中时，用列名赋值内容。
                if col_src.find("+") == -1:
                    dest_df[col_dst] = str(col_src)
                    add_cols[col_dst] = col_src
                else:
                    # dest_df[col_dst] = src_df.apply(lambda row: ''.join([str(row[col]) for col in col_src.split("+")]), axis=1)
                    dest_df[col_dst] = src_df.apply(lambda row: ''.join([str(row[col])[:20] if row[col] is not None else '' for col in col_src.split("+")]), axis=1)
                    add_cols[col_dst] = dest_df[col_dst]
        
        # 为什么要这样才能赋值成功？
        for key,value in add_cols.items():
            dest_df[key] = value.replace('\xa0', '')

        # self.logger.debug(dest_df)
        # use sequence set to datakey
        # dest_df['data_key'] = str(range(1, len(dest_df) + 1))
        dest_df = self.set_none_col_seq(dest_df,"data_key")
        
        return dest_df
    
    def set_none_col_seq(self,df,colname):
        """
        设指定列空值为序列号
        """
        if colname in df.columns:
            # 初始化序列起始值
            sequence_start = 1

            # 获取空值的索引
            # na_indices = df[df['data_key'].isna()].index

            na_indices = df[df[colname].isna() | (df[colname].astype(str).str.strip().isin(['0', '0.0', 'nan']))].index

            # 为每个空值设置序列数字并转换为字符串
            for i, idx in enumerate(na_indices):
                df.at[idx, 'data_key'] = str(sequence_start + i)

            # 将所有值转换为字符串
            df['data_key'] = df['data_key'].astype(str)
        return df


    def rename_columns(self,dest_df, mapping_list):
        '''
        转换列名
        '''
        column_mapping = {mapping[self.C_SRC]: mapping[self.C_DST] for mapping in mapping_list}
        dest_df.rename(columns=column_mapping, inplace=True)
        return dest_df



    def get_file_to_raw_def(self,prefix,region):
        '''
        从数据文件定义表，读取配置数据
        TODO 提交 Mage 需要修改
        '''
        sql_query = "SELECT * FROM sc_raw_file_define WHERE file_prefix = %s and otc_region = %s and del_flg = 0 order by file_action_name;"
        # parameters = ("MY HSBC","MY",)
        parameters = (prefix,region,)
        rst = self.db.execute_query_col_name(sql_query,parameters)
        return rst

    def get_region_file_to_raw_def(self,region):
        '''
        取得数据文件定义配置信息
        '''
        sql_query = "SELECT * FROM sc_raw_file_define WHERE otc_region = %s and del_flg = '0' and is_post_file='1' order by file_action_name;"
        parameters = (region,)
        rst = self.db.execute_query_col_name(sql_query,parameters)
        return rst
    
 
    # def backup_file(self,src_file,bucket_name):
    #     '''
    #     备份文件
    #     '''       
    #     # 获取文件名和目录
    #     file_dir, file_name = os.path.split(src_file)
    #     # 获取文件夹名称
    #     dir_name = os.path.basename(os.path.normpath(file_dir))

    #     # 构建 backup 目录路径
    #     backup_dir = os.path.join(file_dir, '..', 'backup', dir_name)

    #     # 检查 backup 目录是否存在，不存在则创建
    #     if not os.path.exists(backup_dir):
    #         os.makedirs(backup_dir)

    #     # 添加时间戳
    #     timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    #     backup_file_name = f"{timestamp}_{file_name}"

    #     # 构建备份文件的路径
    #     backup_path = os.path.join(backup_dir, backup_file_name)

    #     try:
    #         # 拷贝文件到 backup 目录
    #         shutil.copy2(src_file, backup_path)
    #         if self.is_local == 0:
    #             # 删除源文件
    #             # TODO 生产环境下 删除
    #             os.remove(src_file)
    #             cos,_ = self.file_util.create_cos()
    #             self.file_util.backup_cloud_file('doing_'+file_name, backup_file_name, bucket_name, cos)

    #         self.logger.info(f"Backup successful: {src_file} -> {backup_path}")

    #     except Exception as e:
    #         self.logger.error(f"Backup failed: {e}")
        


    def re_orgnaize_df(self,raw_table_name,bl_talbe_name, src_df):
        """
        重新组织 列数据
        按照规则设置列值

        """
        if bl_talbe_name == 'bl_sg_boa_tracker':
            src_df = self.re_orgnaize_df_sg_boa(src_df)
        elif bl_talbe_name == 'bl_bank_statement':
            # 把空值设定为固定值
            # src_df = self.re_set_df_bankstatment(src_df)
            # 如果已经post的数据，不再load处理
            # src_df = self.skip_posted_bank_statment(src_df)
            # 顺丰COD数据，没有balance，会造成主键缺失，丢数据。
            src_df = self.set_df_doctype(df=src_df,region=self.region)
            src_df = self.set_cod_balance(raw_table_name=raw_table_name,rc_df=src_df)
            src_df = self.trim_Number_nan(src_df)
            nowtime = datetime.now()
            src_df['update_time'] = nowtime
            src_df['upload_time'] = nowtime
            # 保存银行数据条数
            self.bank_data=self.bank_data+len(src_df)
        elif bl_talbe_name == 'bl_vat_issue_list':
            src_df = self.re_set_df_vat_issue_list(src_df)
        # 客户信用日期数据，collection页面关联显示用信息
        elif bl_talbe_name == 'bl_overdue_day':
            src_df = self.set_customer_overdue(src_df)
            src_df['update_time'] = datetime.now()
        elif bl_talbe_name == 'bl_invoice_weekly':
            src_df = self.set_inv_weekly(src_df)
        elif bl_talbe_name == 'bl_aging_history' and self.region == "CN":
            src_df = self.set_cn_default_index(src_df)
        elif bl_talbe_name == 'bl_exchange_rate' or bl_talbe_name == 'sc_month_open_date':
            nowtime = datetime.now()
            src_df['update_time'] = nowtime

        return src_df
    
    def trim_Number_nan(self,df):
        """
        在mage环境下发生NaN
        读入的时候已经处理过，这里强制过滤为0
        """
        for col in ['amount', 'credit_amount', 'debit_amount']:
            if col in df.columns:
                if df[col].isnull().any():
                    # 使用fillna()方法填充NaN值
                    df[col].fillna(0, inplace=True)
        return df
        
    def set_inv_weekly(self,rc_df):
        """
        设置 bl_invoice_weekly period_end 列值为唯一值
        """
        defaut_value = datetime.min
        if(len(rc_df)>1):
            mask = (rc_df['period_end'] == defaut_value)  # 找出不等于默认值的行
            replacement_value = rc_df.loc[rc_df['period_end'] != defaut_value, 'period_end'].iloc[0]  # 获取特定值
            rc_df.loc[mask, 'period_end'] = replacement_value  # 替换值
            
        return rc_df
    
    def set_cod_balance(self,raw_table_name,rc_df):
        """
        顺丰COD数据，没有balance，会造成主键缺失，丢数据。
        把amount合计保存为balance
        """
        if raw_table_name =='raw_cn_cod':
            rc_df['balance'] = rc_df['amount'].cumsum()
        return rc_df

    def set_customer_overdue(self,rc_df):
        """
        Over due day 
        """
        # rc_df['overdue_day'] = rc_df[['overdue_day_0', 'overdue_day_1', 'overdue_day_2', 'overdue_day_3']].mean()
        # rc_df['overdue_day'] = rc_df[['overdue_day_0', 'overdue_day_1', 'overdue_day_2', 'overdue_day_3']].mean(axis=1, skipna=True)
        
        # 计算合计列
        rc_df['total'] = rc_df[['overdue_day_0', 'overdue_day_1', 'overdue_day_2', 'overdue_day_3']].sum(axis=1)

        # 计算不为0的列的数量
        num_nonzero = (rc_df[['overdue_day_0', 'overdue_day_1', 'overdue_day_2', 'overdue_day_3']] != 0).sum(axis=1)

        # 计算不为0的列的平均值
        rc_df['overdue_day'] = rc_df['total'] / num_nonzero

        return rc_df

    def set_cn_default_index(self,src_df):
        """
        设定默认顺序，保存
        """
        src_df = src_df.reset_index().rename(columns={'index': 'cn_index'})
        return src_df

    def skip_posted_bank_statment(self, src_df):
        """
        对已经post完毕的银行数据，不再load。
        已经判断不可以重复load银行数据，所以这个没有用了。
        """
        # 取得数据库数据 region，date，amount
        # 数据是否已经存在于DB中，如果存在，
        # 判断post 状态, 如果已经post,删除这条df数据,不更新.
        # TODO
        rows_to_remove = []
        for idx, row in src_df.iterrows():
            # 如果已经被POST，这条数据将跳过不处理
            rst_df = self.check_bank_statement(row['otc_region'],row['account_number'],row['value_date'],row['amount'],row['balance'])
            if not rst_df.empty:
                rows_to_remove.append(idx)
                # if row['ipf_status'] == '特定值':
                #     src_df = src_df.drop(idx)
        src_df = src_df.drop(rows_to_remove)
        return src_df
    

    def check_bank_statement(self,region,act_num,value_date,amount,balance):
        """
        检查银行账单是否已经被POST
        
        """
        sql_query = """SELECT * FROM bl_bank_statement 
                        WHERE otc_region = %s and account_number = %s and value_date = %s and amount = %s and balance = %s
                        and (ipf_status = 'data_posted' or ipf_status = 'data_posted'); """
        #  user_edit user_confirmed 是否需要？ TODO
        parameters = (region,act_num,value_date,amount,balance,)
        
        rst = self.db.execute_query_col_name(sql_query,parameters)

        return rst


    def set_bank_customer_account(self,region,src_df,table_name):
        """
        印度的银行数据有两份
        其中邮件发送的数据中的  Remitter Account No ，Remitter Name，
        在下载数据中没有，
        可以转存到 下载数据的 bank statment
        通过 valuedate， reference1，amount 3个值匹配
        """
        # raw_in_boa_acc
        if region == 'IN' and table_name == 'raw_in_boa_acc':
            self.logger.debug("update india  raw_in_boa_acc to bank statement")
            for idx, row in src_df.iterrows():
                value_date = row['value_date']
                reference1 = row['remitter_ref']
                amount = row['amount']
                customer_account = row['remitter_account_no'] 
                customer_name = row['remitter_name']

                sql_query = """ update bl_bank_statement 
                    set account_no_customer= %s ,
                        customer_name = %s
                    WHERE value_date = %s 
                        and reference1 = %s 
                        and amount = %s ; """
                
                parameters = (customer_account,customer_name, value_date, reference1,amount,)

                self.db.execute_update_query(sql_query,parameters)

    def set_bank_info_after_update(self,region,table_name):
        """
        还是对印度的特殊处理，
        两份银行数据先后更新确保用，
        不对数据load先后做控制，
        """
        if region == 'IN' and table_name == 'bl_bank_statement':
            sql_query ="""UPDATE bl_bank_statement
                            SET
                                account_no_customer = raw_in_boa_acc.remitter_account_no,
                                customer_name = raw_in_boa_acc.remitter_name
                            FROM
                                raw_in_boa_acc
                            WHERE
                                bl_bank_statement.value_date = raw_in_boa_acc.value_date
                                AND bl_bank_statement.reference1 = raw_in_boa_acc.remitter_ref
                                AND bl_bank_statement.amount = raw_in_boa_acc.amount
                                AND EXISTS (
                                    SELECT 1
                                    FROM raw_in_boa_acc
                                    WHERE
                                        bl_bank_statement.value_date = raw_in_boa_acc.value_date
                                        AND bl_bank_statement.reference1 = raw_in_boa_acc.remitter_ref
                                        AND bl_bank_statement.amount = raw_in_boa_acc.amount
                                );"""
            parameters = ( )
            self.db.execute_update_query(sql_query,parameters)

    def re_orgnaize_df_sg_boa(self, src_df):
        """
        按照规则设置列值
        bl_sg_boa_tracker     
        """
        for idx, row in src_df.iterrows():
            src_val = row['correct_by_order']
            src_val2 = row['by_order']
            if src_val is None or src_val =='':
                src_val = src_val2

            dlist = self.extract_numbers(str(src_val))
            result_dict = {}
            # 按照 id字符串的长度进行分组
            for numid in dlist:
                length = len(numid)
                if length not in result_dict:
                    result_dict[length] = []
                result_dict[length].append(numid)

            # 按照不同的长度，保存到对应的字段
            for length, words in result_dict.items():
                if length == 6:
                    # row['customer_id'] = ' '.join(words)
                    src_df.loc[idx, 'customer_id'] = ' '.join(words)
                elif length == 7:
                    # row['invoice_no'] = ' '.join(words)
                    src_df.loc[idx, 'invoice_no'] = ' '.join(words)
                elif length == 8:
                    # row['sales_order'] = ' '.join(words)   
                    src_df.loc[idx, 'sales_order'] = ' '.join(words)  
        return src_df


    def re_set_df_bankstatment(self,src_df):
        """
        NZ 的BOA 银行信息 narrative1 在DEBIT数据时为空，
        但 bl_bank_statement 的 narrative1是主键，把narrative1设置为固定值
        
        """
        for idx, row in src_df.iterrows():
            nar =  row['narrative1']
            if nar == '' or pd.isna(nar):
                src_df.loc[idx, 'narrative1'] = 'NON'
        return src_df

    def re_set_df_vat_issue_list(self,src_df):
        """
        bl_vat_issue_list的sales_order = remarks按'/IN:'切割后提取的值

        """
        for idx, row in src_df.iterrows():
            remarks_val =  row['remarks']
            # remarkary = remarks_val.split('/IN:')
            # sales_order_val=''
            # if(len(remarkary)>1):
            #     sales_order_val = remarks_val.split('/IN:')[1].replace('/', '')
            # src_df.loc[idx, 'sales_order'] = sales_order_val

            cc_match = re.search(r"CC:(\d+)", remarks_val)
            so_match = re.search(r"SO:(\d+)", remarks_val)
            in_match = re.search(r"IN:(\d+)", remarks_val)

            cc_number = cc_match.group(1) if cc_match else ''
            so_number = so_match.group(1) if so_match else ''
            in_number = in_match.group(1) if in_match else ''

            src_df.loc[idx, 'customer_id'] = cc_number
            src_df.loc[idx, 'sales_order'] = so_number
            src_df.loc[idx, 'inv_no'] = in_number

        return src_df
    

    def extract_numbers(self,input_str):
        """
        提取特定长度的数字字符串

        """
        # 使用斜线、逗号、&号、空格分割字符串，保存为list1
        list1 = re.split(r'[/,&\s]+', input_str)
        # 过滤掉全部数字以外的字符，提取出所有数字字符
        all_numbers = []
        for item in list1:
            numbers = re.findall(r'\d+', item.replace('-',''))
            all_numbers.extend(numbers)
        # 提取数字，包括6位、7位、8位数字
        result = []
        for num in all_numbers:
            # print(num)
            if len(num) == 6 or len(num) == 7 or len(num) == 8:
                result.append(num)
        return result
    
    
    def get_comm_defines(self):
        """
        取得DB定义常量配置
        [None,'\xa0', '',' ','-','--']

        """
        com_df = self.comm_util.get_comm_define(self.region)
        com_df.set_index("def_type", inplace=True)
        na_val = self.comm_util.get_com_def_by_name(com_df,"NA_VAL")
        self.na_values = na_val.split(',')

    def check_total_count(self,df):
        """
        检查数据完整性，数据条数正确
        Totalcount
        """
        total_col_name = "totalcount".upper()
        df.columns = [col.upper() if isinstance(col, str) else col for col in df.columns]
        # df.columns= [col.upper() for col in df.columns]
        if total_col_name in df.columns:
            total_count = df.loc[0,total_col_name]
            if len(df) == total_count:
                self.logger.info(f"The number of data rows in the data file is correct. {self.prefix} count:{total_count}")
            else:
                self.logger.error(f"The number of rows in the data file is incorrect, please verify the file. {self.prefix} right count:{total_count}, file count:{len(df)}")
    
    def is_prefix_in_bill_files(self,prefix, bill_files):
        """
        check if the prefix is in any of the bill_files elements
        """
        return any(prefix.lower() in bill_file.lower() for bill_file in bill_files)

    listscq = ['175','399']

    def set_doctype(self, df, listscq):
        """
        设定doctype   
        1. 175，399 是 SCQ
        2. 175,399 以外，是 SBT
        """
        # 确保 ctype 是字符串并补齐到3位
        df['ctype'] = df['ctype'].astype(str).str.zfill(3)
        
        # 默认全部设为 SBT
        df['doctype'] = 'SBT'
        
        # 条件匹配 175,399 设为 SCQ
        df.loc[df['ctype'].isin(listscq), 'doctype'] = 'SCQ'
        
        return df

    def set_df_doctype(self,df,region):
        """
        根据地区设置doctype
        IN地区：根据Transaction Type确定doctype
        其他地区：根据payment字段确定doctype
        """
        if region=="IN":
            df['ctype'] = df['narrative2'].apply(self.extract_tran_num)
            df = self.set_doctype(df, self.listscq)
        
        return df    
    
    def extract_tran_num(self,val):
        """
        提取括号中的数字
        """
        number=0
        if isinstance(val, (str, bytes)):
            match = re.search(r'\((\d+)\)', val)
            if match:
                number = match.group(1)
        return number