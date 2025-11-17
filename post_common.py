"""
# Cash Posting Action
"""

import re
import math
import traceback
from datetime import datetime
from collections import namedtuple
import pandas as pd
from fuzzywuzzy import fuzz
import json

from utils.db_util import Database
from utils.file_util import FileUtil
from utils.comm_util import CommUtil
from exceptions import CustomException,ConcurrencyException

# 定义 namedtuple 结构
RuleItem = namedtuple(
    "RuleItem",
    [
        "rule_name",
        "rule_seq",
        "src_table",
        "src_field1",
        "dst_field1",
        "search_rule1",
        "div_rule1",
        "src_field2",
        "div_rule2",
        "dst_field2",
        "search_rule2",
        "result_field",
        "add_fields",
        "result_comment",
        "rule1",
        "rule2",
        "dst_table1",
        "dst_table2",
        "temp_fields",
        "confidence",
    ],
)


class PostAction:
    """
    # Cash Posting Action
    """

    ###########################################
    # Cash Posting Action
    ###########################################
    RUL_NUMBER = "num"
    RUL_STRING = "str"
    RUL_MSTR = "mstr"
    RUL_EXCLUD = "exc"
    RUL_DEBIT = "debit"
    RUL_CONST = "const"
    RUL_CHECK = "chk"

    R_TYPE = "type"
    R_PRIFIX = "prefix"
    R_COUNT = "count"
    R_SPLIT = "split"
    R_TRIM = "trim"
    RULE_ITEM_CNT = 5
    RULE_SPLIT = ":"

    PO_METHOD = "method"
    PO_RULE = "method_rules"

    POST_ACT = "_PostAction"
    ACT_LOCK = "lock"
    ACT_FREE = "un_lock"

    # 银行数据状态标记
    SINGLE_MATCHED = "single_matched"
    MULTI_MATCHED = "multi_matched"
    USER_EDIT = "user_edit"
    USER_CONFIRMED = "user_confirmed"
    DATA_POSTED = "data_posted"
    NEED_CONFIRM = "need_confirm"

    # IND_FILTER = """PRIVATE LIMITED,Private Limited,PRIVATE LIMIT,PRIVATE LIMI,
    #             PRIVATE LIM,PRIVATE LTD,PRIVATE LI,SYSTEMS,PRIVATE,PRIVA,
    #             LIMITED,LIMITED,P  LTD,PVT LTD,PVT LT,PVT L,P.LTD,PVT.,PVT,LTD.,LTD,M S., IN ,.,"""
    # TIME_STR = """JANUARY,FEBRUARY,MARCH,APRIL,MAY ,JUNE,JULY,AUGUST,SEPTEMBER,OCTOBER,NOVEMBER,DECEMBER,
    #         JAN ,FEB ,MAR ,APR,MAY ,JUN ,JUL ,AUG ,SEP ,OCT,NOV,DEC ,DIRECT CREDIT,ACCOUNT,CUST.,
    #         ACCT ,AC NO,ACC ,A/C,INV,ELEMENT14,CUSTOMERNO,NONREF,PAYMENT,COMMUNICATIONS,PTY,LTD,EFT-,
    #         """
    
    def __init__(self, name: str, logger=None) -> None:
        self.name = name
        self.logger = logger
        self.tole = 0
        self.region = ""
        self.def_data = None
        self.dest_dfs_dict = None
        self.ind_filter_def = ""
        self.time_filter_def = ""
        self.ptsetc_def=""
        self.reg_str_def=""
        self.thrd_confidence="4"
        self.au_trip=""
        self.au_trim_d=""

        self.db = Database(logger=logger)
        self.file_util = FileUtil(logger=logger)
        self.comm_util = CommUtil(logger=logger)

    def excute_region_posting(self, region, action_user="system"):
        """
        以地区为单位，处理bankstatement数据
        查找 客户ID
        """
        self.region = region
        self.logger.info(f"Post Start. Region: {region} ")
        df_rg = self.get_all_region_methods(region)

        # self.logger.info(f"Post Region count : {len(df_rg)} ")
        act_name=f"{self.region}{self.POST_ACT}"
        if self.comm_util.check_is_lock(self.region,act_name,action_user):
            self.logger.info(f'Post Action is locking :{region} . End Post.')
            return
        
        self.comm_util.update_div_status(region=self.region,action_name=act_name,ac_status=self.ACT_LOCK,ac_user=action_user)

        for ind_s, row_s in df_rg.iterrows():
            r_region = row_s["region_name"]
            r_bank = row_s["bank_name"]
            r_cur = row_s["currency"]

            self.logger.info(
                f"Excete Post  Region: {region} bank:{r_bank},cur:{r_cur} ,index: {ind_s} "
            )
            self.execute_posting(region=r_region, bank_name=r_bank, currency=r_cur,action_user = action_user)
        
        self.comm_util.unlock_action(region=self.region,action_name=act_name,ac_status=self.ACT_FREE,ac_user=action_user)

        self.logger.info(f"Post Finished. Region: {region} ")

    def execute_posting(self, region, bank_name, currency, action_user="system"):
        """
        以 地区，银行，货币为单位，处理bankstatement数据
        查找 客户ID
        """
        self.logger.info(
            f"Excute post start. Region: {region},Bank: {bank_name},Currency: {currency} "
        )
        self.region =region
        try:
            bz_date = self.comm_util.get_daytime_string()
            post_action_name = f"{region}_{bank_name}_{currency}_post"
            # 当源数据文件load有错误时，退出，并保存skip状态
            if self.comm_util.check_data_load_err(self.region):

                # self.comm_util.update_posting_status(
                #         region=region,
                #         action_name=post_action_name,
                #         business_date=bz_date,
                #         status=self.comm_util.BL_STS["21"],
                #         bl_message=f"""Post matching source data not ready.Region:{region} ,Bank: {bank_name}, Cur: {currency}. skiped.""",
                #         ac_user=action_user,)
                
                self.logger.error(
                    f"""Post matching Source data not ready.region: {region}, bank: {bank_name}, currency: {currency} """
                )

                # return
            # else:
            self.comm_util.update_posting_status(
                    region=region,
                    action_name=post_action_name,
                    business_date=bz_date,
                    status=self.comm_util.BL_STS["4"],
                    bl_message=f"""Post matching action on
                                                    Region:{region} ,
                                                    Bank: {bank_name},
                                                    Currency: {currency}  start.""",
                    ac_user=action_user,
                )
            # 取得Post处理的所有具体处理步骤的方法名，根据 地区，银行，币种 定义
            rg_methods = self.get_region_bank_method(
                region=region, bank=bank_name, cur=currency
            )
            # 如果没有定义，退出
            if rg_methods.empty:
                self.logger.info(
                    f"""Table sc_region_method has no data in
                                  region: {region}, bank: {bank_name}, currency: {currency} """
                )
            else:
                # 取出Post处理源数据表，唯一
                src_table_name = rg_methods.iloc[0]["src_table"]

                # 取出配置数据 查找目标表，方法名
                # 方法名
                post_methods = {}
                # 目标表
                dest_tables_set = set()

                for _, row in rg_methods.iterrows():
                    dest_tables_set.update(row["dst_table"].split(","))
                    post_methods[row["method"]] = row["method_rules"]

                # 目标表
                dest_tables = list(dest_tables_set)
                src_table = self.get_src_bl_table(src_table_name, region, bank_name, currency)
                
                self.logger.info(
                    f"Bank {bank_name} statament data count: {len(src_table)} "
                )

                if not src_table.empty:
                    # self.comm_util.update_posting_status(
                    #     region=region,
                    #     action_name=post_action_name,
                    #     business_date=bz_date,
                    #     status=self.comm_util.BL_STS["4"],
                    #     bl_message=f"""Post matching action on
                    #                                     Region:{region} ,
                    #                                     Bank: {bank_name},
                    #                                     Currency: {currency}  start.""",
                    #     ac_user=action_user,
                    # )
                    # 取得常量
                    self.get_comm_defines()
                    # 目标表DataFrame 的Dict
                    self.dest_dfs_dict = self.get_dest_tables_dataframes(
                        dest_tables, region, currency
                    )

                    # 标识字段清空，重新查找。 sales_order
                    src_table.loc[:, "post_text"] = ""
                    src_table.loc[:, "custom_found"] = ""

                    # 动态执行规则方法
                    src_table = self.excute_rule_methods(
                        post_methods, src_table, self.dest_dfs_dict
                    )

                    # 处理结果源表数据更新回数据库表
                    self.logger.info(
                        f"Posting bank data up to DB talbe: {src_table_name}."
                    )
                    src_table["update_time"] = datetime.now()
                    self.db.upsert_table(src_table, src_table_name)

            self.comm_util.update_posted_status(
                region=region,
                action_name=post_action_name,
                business_date=bz_date,
                status=self.comm_util.BL_STS["5"],
                bl_message=f"Post matching action on Region:{region} ,Bank: {bank_name}, Currency: {currency}  Successfully .",
                ac_user=action_user,
            )
        except (ConcurrencyException) as e:
            self.logger.info(f"Post matching Concurrency control. skiped. Region:{region},user {action_user}, {e}")
        except (CustomException, Exception) as e:
            self.logger.error(
                e.message if isinstance(e, CustomException) else str(e.args)
            )
            self.logger.error(traceback.format_exc())
            self.comm_util.update_posted_status(
                region=region,
                action_name=post_action_name,
                business_date=bz_date,
                status=self.comm_util.BL_STS["10"],
                bl_message=f"Post matching action on Region:{region} ,Bank: {bank_name}, Currency: {currency}  Failed .",
                ac_user=action_user,
            )

        self.logger.info(
            f"Post Finished. Region: {region},Bank: {bank_name}, Currency: {currency} "
        )

    def excute_rule_methods(self, rule_methods, src_table, dest_dfs_dict):
        """
        动态执行定义的method
        执行顺序由配置决定
        filter_data
        aging_search
        history_search
        cmd_search
        bank_search
        set_const
        """
        for func_name, rule_name in rule_methods.items():
            self.logger.debug(f"DoSearch method :{func_name}  rule: {rule_name} ")
            rules = self.get_search_rule_def(rule_name)
            func = getattr(self, func_name)
            src_table = func(src_table, dest_dfs_dict, rules)
        return src_table

    def history_search(self, src_df, dest_dfs_dict, rules):
        """
        从History数据查找
        """
        for _, row in rules.iterrows():
            self.single_search(row, src_df, dest_dfs_dict, rules)
        return src_df

    def cmd_search(self, src_df, dest_dfs_dict, rules):
        """
        从ASW650 CMD数据查找
        """
        for _, row in rules.iterrows():
            self.single_search(row, src_df, dest_dfs_dict, rules)
        return src_df

    def bank_search(self, src_df, dest_dfs_dict, rules):
        """
        查找银行固定信息
        """
        for _, row in rules.iterrows():
            self.bank_info_search(row, src_df, dest_dfs_dict, rules)
        return src_df

    def set_const(self, src_df, dest_dfs_dict, rules):
        """
        给结果集设置固定值
        post_text 字段中包含 Exclude 的数据行排除
        if row_s["post_text"] is None or row_s["post_text"] == "":
        if "Exclude" not in row_s["post_text"]:
        """
        for _, row in rules.iterrows():
            rule_item = self.get_rule_define_item(row)
            if rule_item.rule1[self.R_TYPE] == self.RUL_CONST:
                for ind_s, row_s in src_df.iterrows():
                    if "Exclude" not in row_s["post_text"]:
                        extract, vl = self.extract_src_value("", rule_item.rule1)
                        s_val = row_s[rule_item.result_field]
                        if rule_item.rule1[self.R_TRIM] == "rem":
                            if s_val == "" or (s_val is None):
                                self.set_srcdf_const(src_df, rule_item, ind_s, extract)
                                self.logger.debug(f"Const set row:[{ind_s}] filed:[{rule_item.src_field1}] val:[{extract}]")
                                # src_df.loc[ind_s, 'post_text'] = result_comment
                        elif rule_item.rule1[self.R_TRIM] == "rep":
                            self.set_srcdf_const(src_df, rule_item, ind_s, extract)
                            self.logger.debug(f"Const set row:[{ind_s}] filed:[{rule_item.src_field1}] val:[{extract}]")
                        elif rule_item.rule1[self.R_TRIM] == "cond":
                            self.set_df_cond_const(src_df, rule_item, ind_s, extract)
                            self.logger.debug(f"Const condition set row:[{ind_s}] filed:[{rule_item.src_field1}] val:[{extract}]")
                        elif rule_item.rule1[self.R_TRIM] == "incld":
                            self.set_df_include_const(src_df, rule_item, ind_s, extract)
                            self.logger.debug(f"Const include set row:[{ind_s}] filed:[{rule_item.src_field1}] val:[{extract}]")
                        elif rule_item.rule1[self.R_TRIM] == "field":
                            self.set_df_field_const(src_df, rule_item, ind_s, extract)
                            self.logger.debug(f"Const field set row:[{ind_s}] filed:[{rule_item.src_field1}] val:[{extract}]")
                    
        return src_df

    def set_srcdf_const(self, src_df, rule_item, ind_s, extract):
        """
        设定源DF固定值
        """
        src_df.loc[ind_s, rule_item.result_field] = extract
        if rule_item.add_fields:
            for field in rule_item.add_fields.split(","):
                src_df.loc[ind_s, field] = extract


    def set_df_cond_const(self, src_df, rule_item: RuleItem, ind_s, extract):
        """
        有条件的 设定源DF 固定值
        当 dst_field1 有值设定时，判断这个 src_df 的这个值是否等于 search_rule1（忽略大小写并去除前后空格），
        成立的条件下，设定 extract 值
        """
        if rule_item.dst_field1:
            val = src_df.loc[ind_s, rule_item.dst_field1]
            if pd.notna(val) and str(val).strip().lower() == str(rule_item.search_rule1).strip().lower():
                src_df.loc[ind_s, rule_item.result_field] = extract

    def set_df_field_const(self, src_df, rule_item: RuleItem, ind_s, extract):
        """
        有条件的 设定源DF 指定值
        当 dst_field1 有值设定时，直接设定这个字段到目标字段，
        成立的条件下，设定 destfield 值
        """
        if rule_item.dst_field1:
            val = src_df.loc[ind_s, rule_item.dst_field1]
            src_df.loc[ind_s, rule_item.result_field] = val

    def set_df_include_const(self, src_df, rule_item : RuleItem, ind_s, extract):
        """
        有条件的 设定源DF 固定值
        当destfield1 有值设定时，判断这个srcdf 的这个值，是包含searchrule1，
        成立的条件下，设定extract值
        """
        if rule_item.dst_field1:
            val = src_df.loc[ind_s, rule_item.dst_field1]
            if pd.notna(val) and rule_item.search_rule1.lower() in str(val).lower():
                src_df.loc[ind_s, rule_item.result_field] = extract


    def exclude_debit(self, src_df, src_field1, src_field2, result_comment):
        """
        Debit amount > 0 有值 不为空
        Credit amount < 0 没有值 空
        """
        for ind_s, row_s in src_df.iterrows():
            debit = row_s[src_field1]
            credit = row_s[src_field2]
            trans_type = row_s["trans_type"]

            # if (debit != "" and (credit is None or credit == "" or math.isnan(credit)) or trans_type == "DEBIT":
            if ((debit != "" and debit != 0) and self.safe_convert_to_number(credit)==0) or (trans_type == "DEBIT"):
                row_s["post_text"] = result_comment
                src_df.loc[ind_s, "post_text"] = result_comment
                self.logger.debug(
                    f"Debit exculde row index:[{ind_s}] Debit amount :[{debit}], Credit :[{credit}]"
                )

        return src_df

    def safe_convert_to_number(self,credit):
        """
        安全转换，
        判定是否数字
        不报错
        """
        if credit is None or credit == "" or math.isnan(credit):
            return 0
        try:
            num = float(credit)
            if num == 0:
                return credit
            return num
        except ValueError:
            return credit
    
    def filter_data(self, src_df, dest_dfs_dict, rules):
        """
        exclude data not need
        """
        for _, row in rules.iterrows():

            rule_item = self.get_rule_define_item(row)

            if rule_item.rule1[self.R_TYPE] == self.RUL_DEBIT:
                src_df = self.exclude_debit(
                    src_df=src_df,
                    src_field1=rule_item.src_field1,
                    src_field2=rule_item.src_field2,
                    result_comment=rule_item.result_comment,
                )
            elif rule_item.rule1[self.R_TYPE] == self.RUL_EXCLUD:
                dst_df = dest_dfs_dict[rule_item.dst_table1]
                src_df = self.exclude_noar(
                    src_df=src_df,
                    src_field=rule_item.src_field1,
                    exclude_list=dst_df,
                    dest_field=rule_item.dst_field1,
                    search_rule=rule_item.search_rule1,
                    result_comment=rule_item.result_comment,
                    rule_item=rule_item,
                )

        return src_df
    
    def single_search(self, row, src_df, dest_dfs_dict, rules):
        """
        单条件查找 通用方法
        """
        rule_item = self.get_rule_define_item(row)

        self.logger.debug(f"single search history cmd rule {rule_item.rule_name}, seq:{rule_item.rule_seq}")
        dst_df = dest_dfs_dict[rule_item.dst_table1]
        # 单条件的情况下
        for ind_s, row_s in src_df.iterrows():
            # 当 post_text 有值 并且 result field 是 customer id的情况下 就不找了。
            # 如果post_text 有值  当 result field 不是 customer id的情况下， 也要查找
            # 当 post_text 为空，或者 result field 不是 customer id 查找
            if row_s["post_text"] is None or row_s["post_text"] == "":
                content = row_s[rule_item.src_field1]
                if content is not None:
                    if rule_item.rule1[self.R_TYPE] == self.RUL_MSTR:
                        self.search_str(
                            ind_s,
                            content,
                            src_df,
                            dst_df,
                            rule_item,
                            fuz_type=2
                        )
                    elif rule_item.rule1[self.R_TYPE] == self.RUL_NUMBER:
                        self.search_num(
                            ind_s,
                            content,
                            src_df,
                            dst_df,
                            rule_item,
                        )
                    elif rule_item.rule1[self.R_TYPE] == self.RUL_STRING:
                        self.search_str(
                            ind_s,
                            content,
                            src_df,
                            dst_df,
                            rule_item
                        )
                    else:
                        continue
        self.logger.debug("history cmd search result df:")
        # self.logger.debug(src_df[['narrative1','amount','search_cusname','customer_id','post_text']].to_string(index=False))

    def bank_info_search(self, row, src_df, dest_dfs_dict, rules):
        """
        设定非客户ID的银行数据信息
        """
        rule_item = self.get_rule_define_item(row)

        dst_df = dest_dfs_dict[rule_item.dst_table1]

        # 单条件的情况下
        for ind_s, row_s in src_df.iterrows():
            content = row_s[rule_item.src_field1]
            if content is not None:
                if rule_item.rule1[self.R_TYPE] == self.RUL_MSTR:
                    self.search_str(
                        ind_s,
                        content,
                        src_df,
                        dst_df,
                        rule_item,
                        result_set_flg=False,
                    )
                elif rule_item.rule1[self.R_TYPE] == self.RUL_NUMBER:
                    self.search_num(
                        ind_s,
                        content,
                        src_df,
                        dst_df,
                        rule_item,
                    )
                elif rule_item.rule1[self.R_TYPE] == self.RUL_STRING:
                    self.search_str(
                        ind_s,
                        content,
                        src_df,
                        dst_df,
                        rule_item,
                        result_set_flg=False,
                    )
                else:
                    continue
            else:
                if rule_item.rule1[self.R_TYPE] == self.RUL_CHECK:
                    self.check_rule_define(ind_s,
                        row_s,
                        src_df,
                        rule_item)
                else:
                    continue

    def aging_search(self, src_df, dest_dfs_dict, rules):
        """
        Aging 数据查找
        """
        for _, row in rules.iterrows():
            rule_item = self.get_rule_define_item(row)

            # 获取目标 DataFrame
            dst_df = dest_dfs_dict[rule_item.dst_table1]
            # 给输出表添加列
            src_df = self.add_column_if_not_exists(src_df, rule_item.temp_fields)
            # self.logger.debug('Aging search rule row :')
            # self.logger.debug(row)

            self.logger.debug(
                f"aging search rule {rule_item.rule_name}, seq:{rule_item.rule_seq}"
            )
            # 单条件的情况下
            if rule_item.search_rule2 == "":
                for ind_s, row_s in src_df.iterrows():
                    if row_s["post_text"] is None or row_s["post_text"] == "":
                        content = row_s[rule_item.src_field1]
                        if rule_item.rule1[self.R_TYPE] == self.RUL_NUMBER:
                            self.search_num(
                                ind_s=ind_s,
                                src_content=content,
                                src_df=src_df,
                                dst_df=dst_df,
                                rule_item=rule_item,
                            )
                        elif rule_item.rule1[self.R_TYPE] == self.RUL_STRING or rule_item.rule1[self.R_TYPE] == self.RUL_MSTR:
                            self.search_str(
                                ind_s=ind_s,
                                src_content=content,
                                src_df=src_df,
                                dst_df=dst_df,
                                rule_item=rule_item
                            )
                        else:
                            continue

            # 多条件，2个条件
            else:
                rule2 = self.parse_rule_string(rule_item.div_rule2)
                for ind_s, row_s in src_df.iterrows():
                    if row_s["post_text"] is None or row_s["post_text"] == "":
                        content1 = row_s[rule_item.src_field1]
                        content2 = row_s[rule_item.src_field2]
                        self.search_cnd_mix(
                            rule1=rule_item.rule1,
                            rule2=rule2,
                            ind_s=ind_s,
                            src_content1=content1,
                            src_content2=content2,
                            src_df=src_df,
                            dst_df1=dst_df,
                            rule_item=rule_item,
                        )
        self.logger.debug("aging search finished.")
        # self.logger.debug(src_df[['narrative1','amount','search_cusname','customer_id','post_text']].to_string(index=False))
        return src_df


    def add_column_if_not_exists(self, df, col_names, default_value=None):
        """
        查找规则表中配置的列，添加到DF

        """
        # 将逗号分隔的列名字符串拆分成列表
        col_list = col_names.split(",")
        # 遍历列名列表
        for col_name in col_list:
            col_name = col_name.strip()  # 移除可能的空格
            # 检查列是否已经存在
            if col_name not in df.columns:
                # 不存在则添加列
                df = df.assign(**{col_name: default_value})
        return df

    def search_num(
        self,
        ind_s,
        src_content,
        src_df,
        dst_df,
        rule_item,
        result_set_flg=True,
    ):
        """
        查找 number定义
        type:prefix:count:split:trim
        num:23:7::
        """
        extract_val, vl = self.extract_src_value(src_content, rule_item.rule1)
        if extract_val:
            rst_df = self.check_values_in_list(dst_df, rule_item.dst_field1, vl)
            if (rst_df.empty):
                self.set_src_df_add_item(src_df=src_df, ind_s=ind_s,rule_item=rule_item,extract_val=extract_val)
            for ind_d, row_d in rst_df.iterrows():
                self.set_row_field(
                    src_df,
                    ind_s,
                    row_d,
                    rule_item,
                    result_set_flg,
                )
        return src_df

    def check_values_in_list(self, df, dst_field1, extract_val):
        """
        查找List是否存在于DF的列数据中
        列数据过滤掉'-'
        返回包含List数据的DF
        """
        # 使用正则表达式生成包含数字字符串的模式
        # pattern = '|'.join(extract_val)
        # $ 固定长度匹配，不超过给定值的长度
        if isinstance(extract_val, list):
            # extract_val=extract_val+'$'
            # pattern = '|'.join([f'{word}$' for word in extract_val])
            pattern = "|".join(extract_val)
            # 对指定列进行处理并使用 str.contains 进行判断
            result = df[dst_field1].str.replace("-", "").str.contains(pattern)
        elif isinstance(extract_val, (int, float, complex)):
            result = df[dst_field1]==extract_val
        else:
            pattern = str(extract_val) + "$"
            # 对指定列进行处理并使用 str.contains 进行判断
            result = df[dst_field1].str.replace("-", "").str.contains(pattern)
        

        # 返回包含结果的 DataFrame（可选）
        result_df = df[result]
        self.logger.debug(
            f"search dest field [{dst_field1}] extract value: [{extract_val}]"
        )
        # self.logger.debug(result_df[['narrative1','amount','search_cusname','customer_id','post_text']].to_string(index=False))
        return result_df

    def search_cnd_mix(
        self,
        rule1,
        rule2,
        ind_s,
        src_content1,
        src_content2,
        src_df,
        dst_df1,
        rule_item:RuleItem,
    ):
        """
        多条件查找
        两个条件同时成立
        配置方式为  rule1 str, rule2 num . 同时成立
        """
        extract_val1, vl = self.extract_src_value(src_content1, rule1)
        extract_val2, vl = self.extract_src_value(src_content2, rule2)
        data_type1 = rule1[self.R_TYPE]
        data_type2 = rule2[self.R_TYPE]
        if extract_val1 and extract_val2:
            custom_amt = 0
            amt_row = []
            
            if ((data_type1 == self.RUL_STRING) or (data_type1 == self.RUL_MSTR)) and (data_type2 == self.RUL_NUMBER):
                if rule_item.search_rule2 == "sum":
                    self.set_srcdf_tempfield(src_df, ind_s, rule_item.temp_fields, extract_val1)
                    str_df = self.find_vector_str(src_val=extract_val1,dest_df=dst_df1,rule_item=rule_item,multi=1)
                    # self.logger.debug(f"Mix Search name, and amount match .name:{extract_val1}  count:{len(str_df)}")
                    if len(str_df) > 0:
                        self.logger.debug(f"Mix sum search value:{extract_val1}")
                        for _, row_d in str_df.iterrows():
                            dest_val1, dest_val2 = self.ex_rule_values(rule_item, row_d)
                            custom_amt = custom_amt + dest_val2
                            amt_row = row_d
                            # self.logger.debug(f"Mix Search name, and amount match aging:{dest_val2} bank amount :{custom_amt}")
                            if custom_amt != 0 and extract_val2 == custom_amt:
                                self.set_row_field(
                                    src_df, ind_s, amt_row,rule_item
                                )
                                self.logger.debug(
                                    f"Mix customer name Sum amount mactch value:[{src_content1}][{src_content2}]  extract value: [{extract_val1}]  [{extract_val2}], Amount [{custom_amt}]  field:[{rule_item.dst_field1}] [{rule_item.dst_field2}] rule1:[{rule_item.search_rule1}] rule2:[{rule_item.search_rule2}]."
                                )
                else:
                    self.set_srcdf_tempfield(src_df, ind_s, rule_item.temp_fields, extract_val1)
                    str_df = self.find_vector_str(src_val=extract_val1,dest_df=dst_df1,rule_item=rule_item)
                    if len(str_df) > 0:
                        mix_df = self.find_value_eq(src_val=extract_val2,dest_df=str_df,dest_field=rule_item.dst_field2)
                        self.set_row_mix_result(ind_s, src_df, rule_item, extract_val1, extract_val2, mix_df)


            elif (data_type1 == self.RUL_STRING) and (
                data_type2 == self.RUL_STRING
            ):
                self.set_srcdf_tempfield(src_df, ind_s, rule_item.temp_fields, extract_val2)
                str_df = self.find_vector_str(src_val=extract_val1,dest_df=dst_df1,rule_item=rule_item)
                if len(str_df) > 0:
                    mix_df = self.find_vector_rule2_str(src_val=extract_val2,dest_df=str_df,rule_item=rule_item)
                    self.set_row_mix_result(ind_s, src_df, rule_item, extract_val1, extract_val2, mix_df)

            # 客户ID，客户名 结合判断
            elif (data_type1 == self.RUL_NUMBER) and (
                data_type2 == self.RUL_STRING
            ):
                eqr_df = self.find_value_eq(src_val=extract_val1,dest_df=dst_df1,dest_field=rule_item.dst_field1)
                if len(eqr_df) > 0:
                    mix_df = self.find_vector_rule2_str(src_val=extract_val2,dest_df=eqr_df,rule_item=rule_item)
                    self.set_row_mix_result(ind_s, src_df, rule_item, extract_val1, extract_val2, mix_df)
            elif (data_type1 == self.RUL_NUMBER) and (
                data_type2 == self.RUL_MSTR
            ):
                eqr_df = self.find_value_eq(src_val=extract_val1,dest_df=dst_df1,dest_field=rule_item.dst_field1)
                if len(eqr_df) > 0:
                    mix_df = self.find_vector_rule2_str(src_val=extract_val2,dest_df=eqr_df,rule_item=rule_item)
                    self.set_row_mix_result(ind_s, src_df, rule_item, extract_val1, extract_val2, mix_df)

            # Id ，amount 结合判定
            elif (data_type1 == self.RUL_NUMBER) and (
                data_type2 == self.RUL_NUMBER
            ):
                if rule_item.search_rule1 == "eq" and rule_item.search_rule2 == "eq":

                    eqr_df = self.find_value_eq(src_val=extract_val1,dest_df=dst_df1,dest_field=rule_item.dst_field1)
                    if len(eqr_df) > 0:
                        mix_df = self.find_value_eq(src_val=extract_val2,dest_df=eqr_df,dest_field=rule_item.dst_field2)
                        self.set_row_mix_result(ind_s, src_df, rule_item, extract_val1, extract_val2, mix_df)
                elif rule_item.search_rule1 == "eq" and rule_item.search_rule2 == "sum":
                    for ind_d, row_d in dst_df1.iterrows():
                        dest_val1, dest_val2 = self.ex_rule_values(rule_item, row_d)
                        if extract_val1 == dest_val1:
                            custom_amt = custom_amt + dest_val2
                            amt_row = row_d
                            amt_idx = ind_s
                    if custom_amt != 0 and extract_val2 == custom_amt:
                        self.set_row_field(
                            src_df, ind_s, amt_row,rule_item
                        )
                        self.logger.debug(
                            f"Mix id Sum amount mactch value:[{src_content1}][{src_content2}]  extract value: [{extract_val1}]  [{extract_val2}], Amount [{custom_amt}]  field:[{rule_item.dst_field1}] [{rule_item.dst_field2}] rule1:[{rule_item.search_rule1}] rule2:[{rule_item.search_rule2}]."
                        )
                
        return src_df

    def set_row_mix_result(self, ind_s, src_df, rule_item, extract_val1, extract_val2, mix_df):
        """
        保存设定结果信息
        """
        if len(mix_df) > 0:
                # 如果 匹配多个加权匹配率合格的值，则多个值同时保存
            self.set_rows_field(
                    src_df,
                    ind_s,
                    mix_df,
                    rule_item,
                    True,
                )
            self.logger.debug(
                    f"Mix name amount String mactch value:[{extract_val1}][{extract_val2}]  field:[{rule_item.dst_field1}] [{rule_item.dst_field2}] rule:[{rule_item.search_rule1}], [{rule_item.search_rule2}]."
                )

    def ex_rule_values(self, rule_item, row_d):
        """
        提取查找定义目标值
        """
        dest_val1 = row_d[rule_item.dst_field1]
        dest_val2 = row_d[rule_item.dst_field2]
        dest_val1 = self.trim_sales_order(dest_val1, rule_item.dst_field1)
        dest_val2 = self.trim_sales_order(dest_val2, rule_item.dst_field2)
        return dest_val1,dest_val2
    

    def trim_sales_order(self, val, dst_field):
        """
        过滤掉非必要的字符
        """
        if dst_field == "sales_order":
            return val.replace("-", "")
        else:
            return val

    def trim_search_value(self, src_val, dest_val, rule):
        """
        过滤掉非必要的字符
        """
        rtrim = rule[self.R_TRIM]
        if rtrim:
            # parentheses
            if rtrim == "PTS":
                # src_val = re.sub(r"[\(\)\（\）]", "", src_val)
                # src_val = re.sub(r"\t", "", src_val)
                # dest_val = re.sub(r"[\(\)\（\）]", "", dest_val)
                # dest_val = re.sub(r"\t", "", dest_val)

                src_val = re.sub(self.ptsetc_def, "", src_val)
                dest_val = re.sub(self.ptsetc_def, "", dest_val)

            elif rtrim == "IND":
                pattern = r'[A-Z]+\/\d+@\w+'
                src_val = re.sub(pattern, '', src_val)
                for value in self.ind_filter_def.split(
                    ","
                ):
                    src_val = src_val.replace(value, "")
                    dest_val = dest_val.replace(value, "")

            elif rtrim =="dd":
                dest_val = self.filter_identi_numbers(dest_val)

        return src_val, dest_val

    def search_str(
        self,
        ind_s,
        src_content,
        src_df,
        dst_df,
        rule_item:RuleItem,
        result_set_flg=True,
        fuz_type=2,
    ):
        """
        查找 str 的定义
        type:prefix:count:split:trim
        str:22:::
        """

        extract_val, vl = self.extract_src_value(src_content, rule_item.rule1)
        if extract_val and len(extract_val.strip())>1:
            self.set_srcdf_tempfield(src_df, ind_s, rule_item.temp_fields, extract_val)
            # 调用向量查找 TODO
            matched_df = self.find_vector_dataframe(src_val=extract_val,dest_df=dst_df,rule_item=rule_item)

            if len(matched_df) > 0:
                # 如果 匹配多个加权匹配率合格的值，则多个值同时保存
                self.set_rows_field(
                    src_df,
                    ind_s,
                    matched_df,
                    rule_item,
                    result_set_flg,
                )
                self.logger.debug(
                    f"""String mactch value src content :[{src_content}]  
                                    extract value: [{extract_val}]
                                    rule:[{rule_item.rule1}] [{rule_item.search_rule1}]."""
                )
            
        return src_df

    
    def get_rule_define_item(self, row):
        """
        保存定义到结构
        """
        rule2 = None
        if row["div_rule2"]:
            rule2 = self.parse_rule_string(row["div_rule2"])
        return RuleItem(
            rule_name=row["rule_name"],
            rule_seq=row["rule_seq"],
            src_table=row["src_table"],
            src_field1=row["src_field1"],
            div_rule1=row["div_rule1"],
            dst_table1=row["dst_table1"],
            dst_field1=row["dst_field1"],
            search_rule1=row["search_rule1"],
            src_field2=row["src_field2"],
            div_rule2=row["div_rule2"],
            dst_table2=row["dst_table2"],
            dst_field2=row["dst_field2"],
            search_rule2=row["search_rule2"],
            result_field=row["result_field"],
            add_fields=row["add_fields"],
            result_comment=row["result_comment"],
            rule1=self.parse_rule_string(row["div_rule1"]),
            temp_fields=row["temp_df_fields"],
            confidence=row['confidence'],
            rule2=rule2,
        )
    
    def get_all_match_result(self, fuz_ratio, row_d, match_list):
        """
        保存所有超出阈值的结果
        """
        data_structure = {"fuz_ratio": fuz_ratio, "row_d": row_d}
        match_list.append(data_structure)
        return match_list

    def is_multi_values(self, result_value):
        """
        从所有超出阈值的结果中，保留匹配度最大的结果
        判断是否超出一个cid的长度
        """
        if len(result_value.strip()) > 8:
            return True, re.sub(r"&|\\", r" ", result_value)
        else:
            return False, result_value

    def set_row_field(
        self,
        src_df,
        ind_s,
        row_d,
        rule_item:RuleItem,
        result_set_flg=True,
    ):
        """
        保存查询结果
        """
        if rule_item.add_fields:
            self.set_add_fields(src_df, ind_s, row_d, rule_item.add_fields)
        if row_d[rule_item.result_field]:
            is_multi, result_value = self.is_multi_values(row_d[rule_item.result_field])
            sts = self.set_confidence(rule_confidence=rule_item.confidence)
            if is_multi:
                sts = self.MULTI_MATCHED
            src_df.loc[ind_s, rule_item.result_field] = result_value
            # if rule_item.add_fields:
            #     self.set_add_fields(src_df, ind_s, row_d, rule_item.add_fields)
            if result_set_flg:
                # src_df.loc[ind_s, 'post_text'] = result_comment
                src_df = self.set_match_result(
                    src_df=src_df, ind_s=ind_s, post_text=self.concat_if_not_empty(rule_item.result_comment, " cfd: " , rule_item.confidence), ipf_status=sts
                )
                # custom_found
        return src_df

    def set_add_fields(self, src_df, ind_s, row_d, add_fields):
        """
        设值保存字段值
        如果sales order时，判定是否为合法的8位。进行格式化处理。
        """
        for field in add_fields.split(","):
            if field == "sales_order" and len(str(row_d[field]).strip()) > 8:
                src_df.loc[ind_s, field] = row_d[field]
                pattern = r"\d{4}-\d{4}|" + r"\d{8}"
                matches = re.findall(pattern, row_d[field])
                if matches:
                    matches = [match.replace("-", "") for match in matches]
                    src_df.loc[ind_s, field] = matches[0]
            else:
                src_df.loc[ind_s, field] = row_d[field]

    def set_confidence(self,rule_confidence):
        """
        判断规则匹配置信度是否高于阈值
        如果高于阈值 ，判断为可以直接发送
        """
        if self.thrd_confidence < rule_confidence:
            ret = self.SINGLE_MATCHED
        else:
            ret = ""
        return ret
    
    def set_rows_field(
        self,
        src_df,
        ind_s,
        matched_df,
        rule_item:RuleItem,
        result_set_flg=True,
    ):
        """
        保存多行查询结果
        """
        result_cid = ""
        # # 取得所有行的目标字段值 去重保存
        # for row_d in rows_d:
        #     if row_d[result_field]:
        #         result_cid = result_cid + "\\" + row_d[result_field]

        result_cid,add_values,single_bool = self.get_values_from_result_df(matched_df,rule_item=rule_item)
        # 保存结果的结果df的目标字段
        if result_cid !='':
            src_df.loc[ind_s, rule_item.result_field] = self.remove_duplicates(result_cid)

            if rule_item.add_fields:
                add_fields = rule_item.add_fields.split(",")
                for index, value in enumerate(add_fields):
                    if add_values[index]:
                        src_df.loc[ind_s, value] = (add_values[0])[:10] if len(add_fields) == 1 else (add_values[index])[:10]

            if result_set_flg:
                ipf_sts= self.MULTI_MATCHED
                if single_bool:
                    ipf_sts = self.set_confidence(rule_confidence=rule_item.confidence)

                src_df = self.set_match_result(
                    src_df=src_df,
                    ind_s=ind_s,
                    post_text=self.concat_if_not_empty(rule_item.result_comment, " cfd: " , rule_item.confidence),
                    ipf_status=ipf_sts,
                )
        return src_df

    # def set_rows_field(
    #     self,
    #     src_df,
    #     ind_s,
    #     rows_d,
    #     result_field,
    #     add_fields,
    #     result_comment,
    #     result_set_flg=True,
    # ):
    #     """
    #     保存多行查询结果
    #     """
    #     result_cid = ""
    #     # 取得所有行的目标字段值 去重保存
    #     for row_d in rows_d:
    #         if row_d[result_field]:
    #             result_cid = result_cid + " \ " + row_d[result_field]
    #     # 保存结果的结果df的目标字段
    #     src_df.loc[ind_s, result_field] = self.remove_duplicates(result_cid)
    #     if result_set_flg:
    #         # src_df.loc[ind_s, 'post_text'] = result_comment
    #         src_df = self.set_match_result(
    #             src_df=src_df,
    #             ind_s=ind_s,
    #             post_text=result_comment,
    #             ipf_status=self.MULTI_MATCHED,
    #         )
    #     return src_df
    
    def set_match_result(self, src_df, ind_s, post_text, ipf_status=None):
        """
        如果匹配成功，保存成功标记
        单独匹配，复数匹配区分
        """
        src_df.loc[ind_s, "post_text"] = post_text
        if ipf_status:
            src_df.loc[ind_s, "ipf_status"] = ipf_status
        return src_df

    def remove_duplicates(self, input_string, delimiter="\\"):
        """
        有些文件的数据重复内容太多，需要过滤掉重复值
        """
        # 使用 set 来过滤重复内容
        filtered_set = set(input_string.split(delimiter))

        # 将集合转换回字符串
        filtered_string = " ".join(filtered_set)

        return filtered_string

    def set_srcdf_tempfield(self, src_df, ind_s, temp_fields, extract_val):
        """
        # 赋值给临时列，
        主要目的是 临时保存查找出来的 客户公司名 赋给 search_cusname 列
        供后续查找使用
        """
        if temp_fields:
            for tmp_fld in temp_fields.split(","):
                if isinstance(extract_val, list):
                    # 将列表元素以空格分隔连接成字符串
                    extracted_str = " ".join(map(str, extract_val))
                    # 赋值给 DataFrame
                    if pd.isna(src_df.loc[ind_s, tmp_fld]):
                        src_df.loc[ind_s, tmp_fld] = extracted_str
                else:
                    # 如果不是列表，直接赋值
                    if pd.isna(src_df.loc[ind_s, tmp_fld]):
                        src_df.loc[ind_s, tmp_fld] = extract_val

    

    def get_dest_tables_dataframes(self, dest_tables, region, currency):
        """
        Get table data frame to dict .
        {tablename,talbe dataframe}
        """
        dataframes_dict = {}
        for dest_table in dest_tables:
            df = self.get_bl_table(dest_table, region, currency)
            dataframes_dict[dest_table] = df

        return dataframes_dict

    def exclude_noar(
        self, src_df, src_field, exclude_list, dest_field, search_rule, result_comment,rule_item:RuleItem
    ):
        """
        排除包含在exclude的数据

        """
        for ind_s, row_s in src_df.iterrows():
            nar = row_s[src_field]
            # nar,_ = self.extract_src_value(nar, rule_item.rule1)
            for ind_d, row_d in exclude_list.iterrows():
                exc = row_d[dest_field]
                f_bool, f_radio = self.fuzzy_match(nar, exc, search_rule, fuz_type=3,correction_verification=False)
                if f_bool:
                    row_s["post_text"] = result_comment
                    src_df.loc[ind_s, "post_text"] = result_comment

                    self.logger.debug(
                        f"Exclude Non AR row index:[{ind_s}] Narrative :[{nar}] "
                    )
                    break

        return src_df

    def get_search_rule_def(self, rule_name):
        """
        取得规则表定义
        """
        sql_query = "SELECT * FROM sc_search_rule WHERE rule_name = %s and is_live = '1' order by group_order, rule_seq ;"
        parameters = (rule_name,)

        rst = self.db.execute_query_to_pandas(sql_query, parameters)

        return rst

    def get_all_region_methods(self, region):
        """
        取得全部地区定义
        """
        sql_query = "SELECT distinct region_name,bank_name,currency  FROM sc_region_method WHERE region_name = %s "
        parameters = (region,)
        df_rg = self.db.execute_query_to_pandas(sql_query, parameters)

        return df_rg

    def get_region_bank_method(self, region, bank, cur):
        """
        取得sc_region_method表 数据
        """
        sql_query = "SELECT * FROM sc_region_method WHERE region_name = %s and bank_name = %s and currency = %s order by run_prior;"
        parameters = (
            region,
            bank,
            cur,
        )

        rst = self.db.execute_query_to_pandas(sql_query, parameters)

        return rst
    

    def get_bl_table(self, table_name, region, currency):
        """
        取得参数指定表 数据 bl_history_tracker
        """
        # sql_query = f"SELECT * FROM {table_name} WHERE otc_region = %s and currency = %s"
        # parameters = (region,currency,)

        if (table_name.lower() == "bl_history_tracker") or (table_name.lower() == "bl_exclude_list"):
            sql_query = f"SELECT * FROM {table_name} WHERE otc_region = %s"
            parameters = (region,)
        elif (table_name.lower() == "bl_customer_master") and (self.region =='SG'):
            sql_query = f"""SELECT customer_id   , 
                            customer_name   , otc_region   , 
                            c_status   , c_country   , 
                            payment   , currency   , 
                            customer_name_cn   , 
                            sales_code   , sales_name  
                            FROM {table_name} WHERE trim(currency) = %s and otc_region ='SG' """
            parameters = (currency,)
        elif (table_name.lower() == "bl_customer_master") and (self.region =='CN'):
            sql_query = f"""SELECT customer_id   ,
                            customer_name   , otc_region   ,
                            c_status   , c_country   ,
                            payment   , currency   ,
                            customer_name_cn   , sales_code   ,
                            sales_name
                            FROM {table_name} WHERE otc_region = %s and trim(currency) = %s and sales_code != 'CLOSED' """
            parameters = (region, currency,)
        elif (table_name.lower() == "bl_customer_master"):
            sql_query = f"""SELECT customer_id   , 
                            customer_name   , otc_region   , 
                            c_status   , c_country   , payment   , 
                            currency   , customer_name_cn   , 
                            sales_code   , sales_name  
                            FROM {table_name} WHERE otc_region = %s and trim(currency) = %s """
            
            parameters = (region, currency,)
        elif (table_name.lower() == "bl_customer_order"):
            sql_query = f"SELECT * FROM {table_name} WHERE trim(currency) = %s"
            parameters = (currency,)
        else:
            sql_query = f"SELECT * FROM {table_name} WHERE otc_region = %s and trim(currency) = %s"
            parameters = (region, currency,)

        if (table_name.lower() == "bl_his_bank_statement"):
            sql_query = f"SELECT * FROM {table_name} WHERE otc_region = %s and trim(currency) = %s and customer_id is not null order by value_date desc "

        if (table_name.lower() == "bl_au_nz_rec_info"):
            sql_query = sql_query + " order by value_date desc "

        rst = self.db.execute_query_to_pandas(sql_query, parameters)
        return rst

    def get_src_bl_table(self, table_name, region, bank, currency):
        """
        取得参数指定表 数据
        """
        sql_query = f"""SELECT * FROM {table_name} WHERE otc_region = %s AND
                bank_branch_name = %s AND currency = %s
                AND (ipf_status !='data_posted' OR ipf_status is null OR ipf_status = '' )"""
        parameters = (
            region,
            bank,
            currency,
        )
        rst = self.db.execute_query_to_pandas(sql_query, parameters)
        return rst

    def execute_match(self, search_value, dest_value, search_rate):
        """
        按照比较规则，比较源数据与目标数据
        一致返回 True
        不一致  False
        """
        if search_rate == 1:
            if search_value == dest_value:
                return True
        elif search_rate < 1:
            rt = fuzz.ratio(search_value, dest_value)
            if rt > search_rate:
                return True

        return False

    def extract_src_value(self, content, rule):
        """
        按照规则，提取查询源数据
        type : prefix : count : split : trim
        """
        data_type = rule[self.R_TYPE]
        prefix = rule[self.R_PRIFIX]
        count = rule[self.R_COUNT]
        split = rule[self.R_SPLIT]
        trim = rule[self.R_TRIM]
        extract_val = ""
        ext_vallist = None
        if data_type == self.RUL_NUMBER:
            if count == "":
                count = 0
            extract_val, ext_vallist = self.extract_cont_number(
                content=content, prefix=prefix, count=count
            )
        elif data_type == self.RUL_STRING or data_type == self.RUL_EXCLUD:
            extract_val = self.extract_cont_string(
                content=content, prefix=prefix, endstr=split, split=split, trim=trim
            )
        elif data_type == self.RUL_MSTR:
            extract_val = self.extract_multi_string(
                content=content, prefix=prefix, split=split, trim=trim
            )
        elif data_type == self.RUL_CONST:
            extract_val = prefix

        return extract_val, ext_vallist

    def extract_cont_number(self, content, prefix, count, trim=""):
        """
        提取数字
        从 content 中提取 prefix开头的数字
        如果 count 是 0 ,那么取得prefix开头的全部数字
        如果 count 大于 0 ,那么取得prefix开头,长度count的数字
        """
        if content:
            if count == 999:
                return content, content
            else:
                if count > 0:
                    # 如果 count 为 8，需要匹配连续 8 位数字或 xxxx-xxxx 格式的数字
                    if count == 8:
                        if(len(prefix)==1):
                            pattern = prefix + r"\d{3}-\d{4}|" + prefix + r"\d{7}"
                        elif(len(prefix)==2):
                            pattern = prefix + r"\d{2}-\d{4}|" + prefix + r"\d{6}"
                        else:
                            pattern = prefix + r"\d{7}"
                    else:
                        count = count - len(prefix)
                        # 可以匹配 指定开头，位数的数字 例如 AC 765431，787866，712322/ AC713989
                        pattern = prefix + r"\b\d{" + str(count) + r"}(?:\s?|/?)\b"
                        pattern = (
                            pattern
                            + "|"
                            + r"\b"
                            + prefix
                            + r"\d{"
                            + str(count)
                            + r"}(?:\s?|/?)\b"
                        )
                        pattern = (pattern
                            + "|"
                            + r"\D" + prefix + r"(?:\s*\d){" + str(count) + r"}(?:\s?|/?)\b"
                        )
                        pattern = (
                            pattern
                            + "|"
                            + r"\b"
                            + prefix
                            + r"(?:\s*\d){"
                            + str(count)
                            + r"}(?:\s?|/?)\b"
                        )
                        pattern = (
                            pattern
                            + "|"
                            + r"\D"
                            + prefix
                            + r"(?:\s*\d){"
                            + str(count)
                            + r"}(?:\s?|/?|[A-Za-z]+)"
                        )
                elif count == 0:
                    pattern = prefix + r"\d+"
                # 使用re.findall函数来提取所有符合条件的数字
                matches = re.findall(pattern, content)
                if matches:

                    if count == 8:
                        # 使用列表推导式，对每个匹配结果去掉 -
                        matches = [match.replace("-", "") for match in matches]
                    else:
                        matches = [
                            "".join(char for char in match if char.isdigit())
                            for match in matches
                        ]
                    # 返回提取结果

                    return matches[0], matches
                else:
                    return 0, 0
        else:
            return 0, 0

    def extract_multi_string(self, content, prefix="", split="", trim="", count=0):
        """
        单纯替换掉trim定义的内容
        type : prefix : count : split : trim
        """
        # 当trim 定义为 d 的时候，过滤掉数字，日期相关的内容
        if trim == "d":
            return self.filter_time_string(input_string=content)
        elif trim == "dd":
            return self.filter_identi_numbers(content)
        else:
            content = content.replace(trim, "")
            if split !="":
                elements = content.split(split)
            else:
                elements = content
            return elements[0] if elements else elements

    def filter_time_string(self, input_string):
        """
        过滤字符
        """
        if input_string is None:
            return ""

        filtered_string = input_string.upper()
        # 步骤2: 过滤掉给定列表中的值
        for value in self.time_filter_def.split(
            ","
        ):
            value = r"(?<![A-Za-z])" + value + r"(?![A-Za-z])"
            filtered_string = re.sub(value, '', filtered_string)
        # 步骤1: 过滤掉字符串中的所有数字
        filtered_string = "".join(char for char in filtered_string if not char.isdigit())

        return filtered_string

    def extract_cont_string(
        self, content, prefix, endstr="/", split="", trim="", count=0
    ):
        """
        提取字符串
        type : prefix :  count :  split :  trim
        """
        if endstr == "":
            endstr = " "

        if content is None:
            # 处理 content 为 None 的情况
            return None  # 或者根据需要返回一个默认值

        # 任意定义字符串开头的情况
        result = ""
        if prefix == "*":
            # 如果 prefix 是 *，则取得全部非数字的字符
            result = re.sub(r"\d", "", content)
            if trim == "d":
                result = re.sub(r"\d", "", result)
        elif isinstance(prefix, str):
            # 如果prefix是字符串，匹配以prefix开头，以/结尾的字符串，并过滤掉prefix

            pattern = re.compile(rf"{prefix}.*?{endstr}|{prefix}.*?$")
            match = pattern.search(content)
            if match:
                result = match.group()
                result = re.sub(re.escape(prefix), "", result)
                result = re.sub(re.escape(endstr), "", result)
                if trim == "d":
                    # result = re.sub(r'\d', '', result).strip()
                    result = re.sub(r"(?<!\w)\d+(?!\w)", "", result)
            else:
                # 如果content去掉prefix后的字符串没有/，取得到字符串结尾，并过滤掉prefix
                result = re.sub(re.escape(prefix), "", content)

        if trim != "d" and trim != "IND":
            result = re.sub(re.escape(trim), '', result)
        
        return result

    def parse_rule_string(self, rule_string):
        """
        提取查询源数据的分离规则
        """
        rule_list = rule_string.split(self.RULE_SPLIT)

        if len(rule_list) == self.RULE_ITEM_CNT:
            data_type, prefix, count, sp, trim = rule_list
            if count:
                count = int(count)
            else:
                count = ""
            return {
                self.R_PRIFIX: prefix,
                self.R_COUNT: count,
                self.R_SPLIT: sp,
                self.R_TRIM: trim,
                self.R_TYPE: data_type,
            }
        else:
            return {}

    def fuzzy_match(self, src_val, dest_val, search_rule, fuz_type=2, correction_verification=True):
        """
        模糊匹配两个字符串是否相似
        高于定义值 匹配成功
        """
        src_val = self.strip_string(src_val).upper()
        dest_val = self.strip_string(dest_val).upper()
        if fuz_type == 1:
            fr = fuzz.ratio(src_val, dest_val)
            # fr = fuzz.partial_ratio(src_val, dest_val)
        elif fuz_type == 2:
            
            fr = fuzz.partial_token_sort_ratio(src_val, dest_val)
            # fr = fuzz.partial_ratio(src_val, dest_val)
            # AU数据下的尝试
            # if (self.region=="AU" and fr == 100 and (correction_verification)):
            #     dest_val = self.filter_identi_numbers(dest_val)
            #     fr1 = fuzz.ratio(src_val, dest_val)
            #     fr= fr - (100-fr1)*(100-fr1)/100
        elif fuz_type == 3:
            fr = fuzz.partial_ratio(src_val, dest_val)

        if float(fr) >= (float(search_rule) * 100):
            r_bool, r_ratio = self.has_same_word(src_val=src_val, dest_val=dest_val)
            if r_bool:
                # self.logger.debug(f'fuzzy match rate:[{fr}] . param1 [{src_val}] param2 [{dest_val}]')
                fr = fr + r_ratio
                return True, float(fr)
            else:
                return False, float(fr)
        else:
            return False, float(fr)

    def strip_string(self, str_val):
        """
        过滤空格
        """
        if str_val is not None:
            str_val = str_val.strip()
        else:
            str_val = ""
        return str_val

    def has_same_word(self, src_val, dest_val):
        """
        是否存在相同单词
        """
        src_val = src_val.replace("-", " ")
        dest_val = dest_val.replace("-", " ")
        words1 = re.split(r"[ /\t\n]+", src_val)  # 将字符串分割成单词列表并转换成集合
        words2 = re.split(r"[ /\t\n]+", dest_val)  # 同理
        if self.region =="CN":
            # same_words = self.is_mutually_contained(src_val,dest_val)
            same_words = set(words1) & set(words2)
        # elif self.region =="AU":
        #     pass
        else:
            same_words = set(words1) & set(words2)  # 求两个集合的交集
        element1 = words1[0]
        element2 = words2[0]
        r_ratio = 10
        if same_words:
            if element1 == element2:
                r_ratio = float(r_ratio) + 20
            return True, r_ratio
        return False, 0

    def is_mutually_contained(self,str1, str2):
        """
        判断相互包含
        """
        return (str1 in str2) or (str2 in str1)

    def find_vector_str(self,src_val,dest_df: pd.DataFrame,rule_item:RuleItem,multi=0):
        """
        多条件向量化查找
        """
        m_df=self.find_vector_dataframe(src_val=src_val,dest_df=dest_df,rule_item=rule_item,multi=multi)
        return m_df
    
        
    def find_vector_rule2_str(self,src_val,dest_df: pd.DataFrame,rule_item:RuleItem):
        """
        多条件向量化查找
        """
        rtrim = rule_item.rule2[self.R_TRIM]
        if rtrim == "IND":
            src_val = self.filter_words(input_string=src_val,filter_string=self.ind_filter_def)

        find_list = self.generate_edge_substrings(src_val,rule_item.dst_field2, 3)

        for find_str in find_list:
            mask = dest_df[rule_item.dst_field2].str.contains(find_str, case=False, na=False, regex=True)
            if mask.any():
                break

        rbool,drow = self.match_by_fuzz(src_val=src_val,dest_df=dest_df[mask],field=rule_item.dst_field2,
                                        rule=rule_item.rule2,search_rule=rule_item.search_rule2)
        new_df = pd.DataFrame(columns=dest_df.columns)
        if rbool:
            return drow
        else:
            return new_df

    def find_value_eq(self,src_val,dest_df:pd.DataFrame,dest_field):
        """
        查找相等值
        """
        mask = dest_df[dest_field] == src_val
        return dest_df[mask]

    def find_vector_dataframe(self,src_val,dest_df: pd.DataFrame,rule_item:RuleItem,multi=0):
        """
        向量化查找
        """
        rtrim = rule_item.rule1[self.R_TRIM]
        if rtrim == "IND":
            src_val = self.filter_words(input_string=src_val,filter_string=self.ind_filter_def)
        rbool= False
        if src_val:
            find_list = self.generate_edge_substrings(src_val,rule_item.dst_field1, 3)
            # self.logger.debug(f" src val : {src_val} . find list: {find_list}")
            for find_str in find_list:
                mask = dest_df[rule_item.dst_field1].str.contains(find_str, case=False, na=False, regex=True)
                if mask.any():
                    break
            
            if find_list:
                rbool,drow = self.match_by_fuzz(src_val=src_val,dest_df=dest_df[mask],field=rule_item.dst_field1,
                                        rule=rule_item.rule1,search_rule=rule_item.search_rule1,multi=multi)
        new_df = pd.DataFrame(columns=dest_df.columns)
        if rbool:
            return drow
        else:
            return new_df

    def match_by_fuzz(self,src_val,dest_df,field,rule,search_rule,multi=0):
        """
        fuzzy查询
        """
        hitted = False
        ret_frame = None
        hit_rows = []
        if len(dest_df)>0:
            if 'customer_id' in dest_df.columns:
                dest_df = dest_df.copy()
                # 统计 cid的个数，数量多的优先处理
                grouped_df = dest_df.groupby('customer_id').size().reset_index(name='cid_count')

                cid_sort_df = grouped_df.sort_values(by='cid_count', ascending=False)
                dest_df = pd.merge(cid_sort_df, dest_df, on='customer_id')
                # 按照narrative的长度排序。如果cid相同，那么 narrative 短少的排在前面优先处理。
                dest_df['a_length'] = dest_df[field].apply(len)
                dest_df = dest_df.sort_values(by=['cid_count','a_length'], ascending=[False, True])
                # dest_df.sort_values(by=["customer_id",field], key=lambda x: x.str.len() if x.name == 'customer_id' else None, inplace=True)

            for idx,row in dest_df.iterrows():
            
                dest_val = row[field]
                dest_val = self.trim_sales_order(dest_val, field)
                src_repeat = False
                fuz_type=3
                # 连续汉字中存在空格时，会影响匹配
                if self.region=="CN":
                    dest_val = re.sub(" ", "", dest_val)
                elif self.region=="AU":
                    dest_val = self.extract_cont_string(content=dest_val,prefix="/ORDP/")
                    fuz_type=2
                extract_val, dest_val = self.trim_search_value(
                    src_val=src_val, dest_val=dest_val, rule=rule
                )
                # 查询内容有重复的时候，不做100ratio的补偿判定
                f_bool, f_radio = self.fuzzy_match(
                        extract_val, dest_val, search_rule,fuz_type=fuz_type,correction_verification=(not src_repeat)
                )
                if f_bool:
                    if multi == 0:
                        return f_bool,row.to_frame().T
                    else:
                        hitted =True
                        hit_rows.append(row)
                        ret_frame = pd.DataFrame(hit_rows)
    
        return hitted,ret_frame
    
        # if multi == 0:
        #     return False,None
        # else:
        #     return hitted,pd.DataFrame(hit_rows)

    def filter_identi_numbers(self,text):
        """
        # 正则表达式匹配独立的数字
        # 替换独立的数字为空字符串
        6647055 L3HARRIS INTEGRA 0745242   结果   L3HARRIS INTEGRA
        """
        # pattern = r'(?<!\w)\d+|\d+(?!\w)'
        pattern = self.au_trim_d
        # pattern = r'(\d{1,}[A-Za-z]{2}\d{1,})|([A-Za-z]{1}\d{2,})|(?<![A-Za-z])(\d[A-Za-z]\d)|\d+(?!\w)|(?<!\w)\d+'
        
        filtered_text = re.sub(pattern, '', text)
        return filtered_text.strip()

    def generate_edge_substrings(self, input_string,dest_field, get_length):
        """
        取得子字符串，仅包含开头的部分
        """
        input_string = self.div_sales_order(input_string,dest_field)

        if self.region =='CN':
            result = self.add_dot_star(input_string)
        elif self.region =="AU":
            result = self.gen_au_edge_substrings(input_string, get_length)
        elif self.region == "SG":
            result = self.gen_sg_edge_substring(input_string, 4)
        else:
            result = self.gen_comm_edge_substring(input_string, get_length)

        return result

    def gen_comm_edge_substring(self, input_string, get_length):
        """
        取得子字符串，
        """
        input_string = self.trim_reg_str(input_string)
        result = self.split_sort_list(input_string, get_length)

        return result
    
    def gen_sg_edge_substring(self, input_string, get_length):
        """
        取得子字符串，
        """
        input_string = self.trim_reg_str(input_string)
        input_string = input_string.replace(" N ", " ")
        result = self.split_sort_list(input_string, get_length)
        return result
    
    def split_sort_list(self, input_string, get_length):
        """
        把字符串做成不同单词个数的list
        """
        words = input_string.split()
        length = len(words)
        result = []

            # 添加所有单词的组合
        if length >= 1:
            result.append('.*'.join(words))

        if length > 2:
            result.append('.*'.join(words[:3]))
            # 如果单词数量多于一个，添加前两个单词的组合
        if length > 1:
            result.append('.*'.join(words[:2]))

        # 添加第2，3个单词
        if length > 2:
            result.append('.*'.join(words[1:3]))

        # 唯一
        result = list(dict.fromkeys(result))
        # 根据长度排序并获取所需长度的结果
        result = sorted(result, key=len, reverse=True)[:get_length]
        return result
    
    def div_sales_order(self,sales_order,field):
        """"
        为了向量查找，给so加-分割
        """
        sso=sales_order
        if field == "sales_order" and len(sales_order)==8:
            sso = sales_order[:4] + '-' + sales_order[4:]
        return sso
            

    def all_words_longer_than(self,input_string, length=1):
        """
        检查每个单词的长度是否都大于指定长度
        """
        words = input_string.split()
        for word in words:
            if len(word) <= length:
                return False
        return True

    def find_repeated_substring(self,input_str):
        """
        查找重复出现的字符串
        如果无，返回原字符串
        """
        s_upper = input_str.upper()  # 转换为大写
        length = len(s_upper)

        # 从较长的子字符串开始逐渐减少长度进行匹配
        for sub_len in range(length // 2, 0, -1):
            for i in range(length - sub_len * 2 + 1):
                sub = s_upper[i:i + sub_len]
                # 排除数字子字符串 
                if ((not any(char.isdigit() for char in sub)) and
                (s_upper.count(sub) > 1) and
                len(sub.strip()) > 1 and
                self.all_words_longer_than(sub,1) and
                re.search(r'\b' + re.escape(sub) + r'\b', s_upper)):
                    if re.fullmatch(r'[a-zA-Z\s]*AUST', sub):
                        sub = sub.replace("AUST", "AUSTRALIA")
                    return sub, True
        return s_upper, False

    def gen_au_edge_substrings(self, input_string, get_length):
        """
        取得子字符串，仅包含开头的部分
        """
        input_string = self.trim_reg_str(input_string)
        # input_string = self.find_repeated_substring(input_string)
        sp_words = input_string.split()
        # 使用集合去重，并保持原有顺序
        seen = set()
        words = []
        for word in sp_words:
            if word not in seen:
                words.append(word)
                seen.add(word)

        length = len(words)
        result = []

        # 添加所有单词的组合
        if length >= 1:
            result.append('.*'.join(words))

        # 添加最长的
        max_word = max(words, key=len)
        result.append(max_word)

        # 如果单词数量多于一个，添加前两个单词的组合
        if length > 1:
            result.append('.*'.join(words[:2]))
        if len(words[:1][0]) > 1:
            result.append('.*'.join(words[:1]))
        
        if not words:
            return result
        # 添加最长的
        max_word = max(words, key=len)
        result.append(max_word)
        # 不需要作为检索项的内容
        values_to_remove = json.loads(self.au_trip)
        # values_to_remove = ["AUSTRALIA", "ORDP"]
        for value in values_to_remove:
            if value in result:
                result.remove(value)
        # result = sorted(result, key=len, reverse=True)

        # 唯一
        result = list(dict.fromkeys(result))
        # 根据长度排序并获取所需长度的结果
        result = sorted(result, key=len, reverse=True)[:get_length]

        return result

    def trim_reg_str(self, input_string, repstr=" "):
        """"
        trim regex key chars
        """
        # au_rstr="-,+,/,.,\\,(,),*,（,）"
        au_rstr = self.reg_str_def
        for value in au_rstr.split(
            ","
        ):
            input_string = input_string.replace(value, repstr)
        return input_string
    
    def add_dot_star(self,input_string):
        """
        将中文字符串中的每个字符之间添加'.*'
        """
        result = []
        rep_string = self.trim_reg_str(input_string=input_string,repstr=".*")
        result.append(rep_string)
        input_string = re.sub(self.ptsetc_def, "", input_string)
        chars = list(input_string)
        dot_str = '.*'.join(chars)
        result.append(dot_str)
        return result

    def create_regex_pattern(self,input_string):
        """
        组合为正则
        """
        # 按空格分割字符串
        split_strings = input_string.split()
        # 使用竖线连接分割后的字符串，形成正则表达式
        # regex_pattern = '|'.join(split_strings)
        regex_pattern = '(?:' + '|'.join(f'(?={word})' for word in split_strings) + ')'
        return regex_pattern

    def filter_words(self,input_string, filter_string):
        """
        过滤掉指定字符串
        """
        # 将过滤词转换为正则表达式，用'|'分隔
        regex_pattern = '|'.join(re.escape(word) for word in filter_string.split(','))
        # 使用正则表达式替换掉所有匹配的词
        
        filtered_string = re.sub(regex_pattern, '', input_string)
        pattern = r'[A-Z]+\/\d+@\w+'
        filtered_string = re.sub(pattern, '', filtered_string)
        return filtered_string

    def get_values_from_result_df(self, matched_df, rule_item:RuleItem):
        """
        取得结果
        """
        add_value = ""
        result_string = ""
        single_bool = False
        if not matched_df.empty:
            column_values = matched_df[rule_item.result_field]
            if not column_values.empty:
                unique_values = set(column_values)
                unique_list = list(unique_values)
                # unique_list = [item.strip() for item in unique_list]
                unique_list = [item.strip() for item in unique_list if item is not None]
                result_string = " ".join(unique_list)
                result_string = result_string[:499]
                if len(unique_list)==1:
                    is_multi, result_string = self.is_multi_values(result_string)
                    if not is_multi:
                        single_bool = True
            # unique_values = matched_df[rule_item.result_field].unique()  # 提取唯一值
            # unique_values_as_str = [str(val) for val in unique_values]  # 将唯一值转换为字符串列表
            # result_string = ' '.join(unique_values_as_str)  # 使用空格连接字符串列表中的元素
            if rule_item.add_fields and len(matched_df) == 1:
                # add_value = matched_df.iloc[0][rule_item.add_fields]
                add_value = self.get_add_values(matched_df, rule_item)
        return result_string, add_value, single_bool

    def get_add_values(self, matched_df, rule_item):
        """
        取得add_fields定义的字段值
        """
        add_value=[]
        for field in rule_item.add_fields.split(","):
            adval = ""
            if field == "sales_order" and len(str(matched_df.iloc[0][field]).strip()) > 8:
                adval = matched_df.iloc[0][field]
                pattern = r"\d{4}-\d{4}|" + r"\d{8}"
                matches = re.findall(pattern, matched_df.iloc[0][field])
                if matches:
                    matches = [match.replace("-", "") for match in matches]
                    adval = matches[0]
            else:
                adval = matched_df.iloc[0][field]
            add_value.append(adval)
        return add_value

    def check_rule_define(self,ind_s,row_s,src_df,rule_item:RuleItem):
        """
        检查定义内容
        
        特定值，例如 
        某地区 MY， payment ADV 的数据，
        sales order 列 的内容为空时，保存结果数据的ifp状态为不可发送，要确认。
        
        """
        # 取得paymenttype
        payment = row_s[rule_item.dst_field1] 

        # if is ADV  rule_item.search_rule1 is define ADV 
        if payment is not None and payment in rule_item.search_rule1:
            # rule_item.src_field1 is the field name of the src table. if the value is null, it should be user confirm.
            content = row_s[rule_item.src_field1]
            if content is None or content =="":
                ipf_sts = self.NEED_CONFIRM
                src_df = self.set_match_result(
                            src_df=src_df,
                            ind_s=ind_s,
                            post_text=self.concat_if_not_empty(rule_item.result_comment, " cfd: " ,rule_item.confidence),
                            ipf_status=ipf_sts,
                            )
        return src_df


    def concat_if_not_empty(self,base, sep, extra):
        """
        当 base 不为空时，返回 base + sep + extra 的拼接字符串；
        当 base 为空（None 或 空字符串）时，返回空字符串。
        """
        if base:
            return f"{base}{sep}{extra}"
        return ""

    def get_comm_defines(self):
        """
        取得DB定义常量配置
        """
        com_df = self.comm_util.get_comm_define(self.region)
        com_df.set_index("def_type", inplace=True)
        self.time_filter_def = self.comm_util.get_com_def_by_name(com_df,"TIMESTR")
        self.ind_filter_def = self.comm_util.get_com_def_by_name(com_df,"IND")
        self.ptsetc_def = self.comm_util.get_com_def_by_name(com_df,"PTS")
        self.reg_str_def = self.comm_util.get_com_def_by_name(com_df,"REG_STR")
        self.thrd_confidence = self.comm_util.get_com_def_by_name(com_df,"TRHD_MATCH")
        self.au_trip=self.comm_util.get_com_def_by_name(com_df,"AU_TRIP")
        self.au_trim_d=self.comm_util.get_com_def_by_name(com_df,"AU_TRIM_D")

    def set_src_df_add_item(self, src_df: pd.DataFrame, ind_s, rule_item, extract_val):
        """
        设置 src_df 指定行的指定字段值

        参数：
            src_df     : pandas.DataFrame，要更新的 DataFrame
            ind_s      : 行索引（可以是 int 或者 index label）
            rule_item  : RuleItem 对象，包含 add_fields、dst_field1 等定义
            extract_val: 要设定的值
        """
        # 解析 add_fields，可能是逗号分隔的字符串
        if rule_item.add_fields:
            if isinstance(rule_item.add_fields, str):
                fields = [f.strip() for f in rule_item.add_fields.split(",")]
            else:
                # 假设不是字符串时，直接转 list
                fields = list(rule_item.add_fields)
        else:
            fields = []

        # 校验 dst_field1 是否在 add_fields 中（或者相等）
        if rule_item.dst_field1 in fields or rule_item.dst_field1 == rule_item.add_fields:
            for field in fields:
                if field in src_df.columns:
                    src_df.at[ind_s, field] = extract_val
                    self.logger.debug(
                        f"set_src_df_add_item: row={ind_s}, field={field}, value={extract_val}"
                    )
               
        
        return src_df
