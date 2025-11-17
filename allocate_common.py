"""
# Allocate Action
"""

import re
from decimal import Decimal, getcontext
import traceback
from itertools import combinations
from datetime import datetime,timedelta
from collections import namedtuple
import pandas as pd


from utils.db_util import Database
from utils.file_util import FileUtil
from utils.comm_util import CommUtil
from exceptions import CustomException,ConcurrencyException
from utils.combi_util import OptimizedMatchingEngine


getcontext().prec = 10

RuleItem = namedtuple(
    "RuleItem",
    [
        "rule_name",
        "rule_seq",
        "src_fields",
        "src_data_type",
        "dest_table",
        "dest_fields",
        "dest_data_type",
        "result_field",
        "result_comment",
        "src_rule_list",
        "dest_rule_list",
    ],
)


class AllocateAction:
    """
    Allocate ActionClass
    """
    COMBINATION_LIMIT = 3000
    RUL_NUMBER = "num"
    RUL_STRING = "str"
    RUL_VALUE = "val"

    R_TYPE = "type"
    R_MATCH = "match"
    R_PRIFIX = "prefix"
    R_COUNT = "count"
    R_FRONT_END = "frontend"
    R_SPLIT = "split"
    R_TRIM = "trim"

    RULE_ITEM_CNT = 7
    RULE_SPLIT = ":"
    ITEM_SPLIT = "|"

    RM_EQ = "eq"
    RM_OPP = "opp"
    RM_SUM = "sum"
    RM_PAT = "pat"
    # 相邻数据顺销
    RM_SEQ = "seq"

    # 印度adv 顺销，有钱就销的区分
    RM_INSEQ = "inseq"

    PMT_ADV = "ADV"
    PMT_TERM = "TERMS"

    ALO_SO = "SO match"
    ALO_SEQ = "sequence match"
    ALO_AMT = "amount match"

    CMT_PAR = "Partial"
    CMT_SEQ = "Sequential"
    IND_TAX = 0.01
    CMT_NOSO = "Not SO match"
    CMT_CHK="needcheck"

    ALOC_ACT = "_AlocAction"
    ACT_LOCK = "lock"
    ACT_FREE = "un_lock"

    # customer_id|c|invoice_no customer_id|sales_order
    L_CID = ["customer_id"]
    L_AMT = ["amount"]
    L_INO = ["invoice_no"]
    L_SO = ["sales_order"]

    def __init__(self, name: str, logger=None) -> None:
        self.name = name
        self.logger = logger
        self.region = ""
        self.tole = 0
        self.def_data = None
        self.db = Database(logger=logger)
        self.file_util = FileUtil(logger=logger)
        self.comm_util = CommUtil(logger=logger)
        self.engine = None
        self.his_combi_ids = set()
        

    def excute_region_allocate(self, region, action_user="system"):
        """
        执行销账处理
        指定 地区
        """
        self.logger.info(f"Allocate Start. Region: {region} ")

        action_name=f"{region}{self.ALOC_ACT}"
        if self.comm_util.check_is_lock(region,action_name,action_user):
            self.logger.info(f'Alocate Action is locking  :{region}.')
            return 
        
        self.comm_util.update_div_status(region=region,action_name=action_name,ac_status=self.ACT_LOCK,ac_user=action_user)

        try:
            bz_date = self.comm_util.get_daytime_string()
            aloc_action_name = f"{region}_Allocation"

            self.region = region

            rg_alocs = self.get_region_aloc_category(region=region)

            # 如果没有定义，退出
            if rg_alocs.empty:
                self.logger.info(
                    f"Table sc_aloc_category has no data in region: {region} "
                )
            else:
                # 取出Post处理源数据表，唯一
                src_table_name = rg_alocs.iloc[0]["src_data"]
                # 取出配置数据 查找目标表，方法名
                # 方法名
                aloc_cate = {}
                # 目标表
                dest_tables_set = set()

                for _, row in rg_alocs.iterrows():
                    dest_tables_set.update(row["dst_data"].split(","))
                    aloc_cate[row["aloc_category"]] = row["aloc_rule"]

                # 目标表
                dest_tables = list(dest_tables_set)
                src_df = self.get_src_bl_table(table_name=src_table_name, region=region)

                if not src_df.empty:
                    self.comm_util.update_allocating_status(
                        region=region,
                        action_name=aloc_action_name,
                        business_date=bz_date,
                        status=self.comm_util.BL_STS["12"],
                        bl_message=f"Allocation action on Region:{region} start.",
                        ac_user=action_user,
                    )

                    # 取得配置本地区的常量定义数据
                    self.set_cls_define_data(region)
                    self.engine = OptimizedMatchingEngine(tolerance=self.tole, generate_group_func=self.generate_group,logger=self.logger)
                    dest_dfs_dict = self.get_dest_tables_dataframes(
                        dest_tables=dest_tables,
                        src_table=src_table_name,
                        src_df=src_df,
                        region=region,
                    )

                    # 动态执行规则方法
                    src_df = self.excute_rule_methods(
                        aloc_cate, src_df, src_table_name, dest_dfs_dict
                    )
                    # 添加整体更新
                    src_df = self.update_aloc_status(src_df,region)

                    update_table = "bl_aging_allocate"
                    self.logger.info(f"Allocate data count :  {len(src_df)} ")
                    self.logger.info(f"Allocate result up to DB talbe: {update_table}.")
                    # 获取当前时间
                    # 将 update_time 列设置为当前时间
                    src_df["update_time"] = datetime.now()
                    src_df["aloc_date"] = datetime.now()
                    src_df = src_df.fillna({"amount_diff": 0})
                    self.update_talbe(table_name=update_table, table_df=src_df)
                    # self.db.upsert_table(src_df, update_table)
                self.comm_util.update_allocated_status(
                    region=region,
                    action_name=aloc_action_name,
                    business_date=bz_date,
                    status=self.comm_util.BL_STS["13"],
                    bl_message=f"Allocation action on Region:{region} Successfully .",
                    ac_user=action_user,
                )
        except (ConcurrencyException) as e:
            self.logger.info(f"Allocation Concurrency control. skiped. Region:{region}, {e}")
        except (CustomException, Exception) as e:
            self.logger.error(
                e.message if isinstance(e, CustomException) else str(e.args)
            )
            self.logger.error(traceback.format_exc())
            self.comm_util.update_allocated_status(
                region=region,
                action_name=aloc_action_name,
                business_date=bz_date,
                status=self.comm_util.BL_STS["14"],
                bl_message=f"Allocation action on Region:{region} Failed .",
                ac_user=action_user,
            )
        
        self.comm_util.unlock_action(region=region,action_name=action_name,ac_status=self.ACT_FREE,ac_user=action_user)
        self.logger.info(f"Allocate Finished. Region: {region} ")

    def set_allocate_error(self,region,action_user,bl_msg):
        """
        When error ,update status
        """
        self.logger.info(f"No aging data loaded. Region: {region} ")
        aloc_action_name = f"{region}_Allocation"
        bz_date = self.comm_util.get_daytime_string()
        # 判断allocation 是否在执行状态，如果正在执行，那么跳过，不做状态更新
        sdf= self.comm_util.get_action(
            region=region, action_name=aloc_action_name, business_date=bz_date
        )
        if not sdf.empty:
            # 判断状态 是否 doing
            db_status = sdf.loc[0, "bl_status"]
            if db_status in [self.comm_util.BL_STS["12"]]: # allocating
                self.logger.info(f"Allocate keep doing skip update status. Region: {region} ")
                return
        self.logger.info(f"Allocate set to error skip . Region: {region} ")
        self.comm_util.update_allocated_status(
                region=region,
                action_name=aloc_action_name,
                business_date=bz_date,
                status=self.comm_util.BL_STS["14"],
                # bl_message=f"Allocation action on Region:{region} Failed .",
                bl_message=bl_msg,
                ac_user=action_user,
            )
    

    def update_aloc_status(self,df: pd.DataFrame, region: str) -> pd.DataFrame:
        """
        更新 aloc_status:
        - 在 region == 'CN' 时处理
        - 条件：aloc_status = 'Not SO match' 且 doc_type != 'SIN'
        - 且 pay_date = 系统昨天 (date 类型)
        - 操作：找到这些行的 aloc_group，把对应 aloc_group 的所有行 aloc_status 改为 'SO match'
        """
        if region != "CN":
            # 非 CN 区域，不处理
            return df

        # 系统昨天
        yesterday = (datetime.now() - timedelta(days=1)).date()
        # yesterday=date(2025, 9, 2)
        # 找到符合条件的 aloc_group
        target_groups = df[
            (df["aloc_status"] == self.CMT_NOSO) &
            (df["doc_type"] != "SIN") &
            (df["pay_date"] == yesterday)
        ]["aloc_group"].unique()

        # 如果找到符合条件的 group，则批量更新
        if len(target_groups) > 0:
            # 命中的记录条数
            matched_df = df[df["aloc_group"].isin(target_groups)]
            matched_count = matched_df.shape[0]

            # 输出总信息
            self.logger.debug(
                f"update_aloc_status: hit aloc_group count={len(target_groups)}, sum={matched_count}"
            )


            # 按 group + customer_id 逐个处理
        for (group, cust_id), group_df in matched_df.groupby(["aloc_group", "customer_id"]):
            cnt = group_df.shape[0]
            amt_sum = group_df["amount"].sum()

            self.logger.debug(
                f"update_aloc_status: aloc_group={group}, customer_id={cust_id}, count={cnt}, amount_sum={amt_sum}"
            )

            # 只有在金额校验通过时才更新
            if abs(amt_sum) < Decimal(str(self.tole)):
                df.loc[df["aloc_group"] == group, "aloc_status"] = self.ALO_SO
                df.loc[df["aloc_group"] == group, "aloc_comments"] = \
                    df.loc[df["aloc_group"] == group, "aloc_comments"].fillna("").astype(str) + " today posting"
            else:
                self.logger.debug(
                    f"update_aloc_status: skip aloc_group={group}, amount_sum={amt_sum} (>= tole={self.tole})"
                )


            # # 输出逐个 group 的数量
            
            # for (group, cust_id), cnt in matched_df.groupby(["aloc_group", "customer_id"]).size().items():
            #     self.logger.debug(
            #         f"update_aloc_status: aloc_group={group}, customer_id={cust_id}, count={cnt}"
            #     )

            # df.loc[df["aloc_group"].isin(target_groups), "aloc_status"] = self.ALO_SO
            # df.loc[df["aloc_group"].isin(target_groups), "aloc_comments"] = \
            #     df.loc[df["aloc_group"].isin(target_groups), "aloc_comments"].fillna("").astype(str) + " today posting"

        return df

    def set_cls_define_data(self, region):
        """
        取得本地区的常量定义数据
        设定到类变量
        """
        self.def_data = self.comm_util.get_aloc_data_define(region=region)
        self.def_data.set_index("def_name", inplace=True)
        self.tole = self.comm_util.get_def_data_by_name(self.def_data, "tole")

    def delete_all_by_region(self, table_name, region):
        """
        删除全部数据
        """
        sql_query = f"delete from {table_name} where otc_region = %s "
        parameters = (region,)
        self.db.execute_update_query(sql_query, parameters)

    def update_talbe(self, table_name, table_df):
        """
        更新数据到表
        当配置为clean的时候，删除全部数据

        """
        self.delete_all_by_region(table_name=table_name, region=self.region)
        # table_df['update_time'] = datetime.now()
        if not self.db.upsert_table(table_df, table_name):
            self.logger.error(f"Save allocate result  {self.region} failed .")
            raise CustomException(
                f"Save allocate result {self.region} table {table_name} failed ."
            )

    def excute_rule_methods(self, aloc_rules, src_table, src_name, dest_dfs_dict):
        """
        动态执行定义的method
        执行顺序由配置决定
        """
        for func_name, aloc_rule in aloc_rules.items():
            self.logger.debug(f"DoSearch method :{func_name}  rule: {aloc_rule} ")
            rules = self.get_aloc_rule_def(aloc_rule)
            func = getattr(self, func_name)
            src_table = func(src_table, src_name, dest_dfs_dict, rules)
        return src_table

    def info_search(self, src_df, src_name, dest_dfs_dict, rules):
        """
        查找，设定销账处理的必要信息数据
        例如 cmd的客户分类
        """
        for _, row in rules.iterrows():
            src_df = self.search_define_data(src_df, src_name, dest_dfs_dict, row)
        return src_df

    def adv_match(self, src_df, src_name, dest_dfs_dict, rules):
        """
        ADV数据 销账处理
        根据表定义规则动态执行
        """
        for _, row in rules.iterrows():
            self.logger.debug(f"adv_match ,account type :{self.PMT_ADV}")
            src_df = self.search_data(
                src_df, src_name, dest_dfs_dict, row, self.PMT_ADV
            )
        return src_df

    def term_match(self, src_df, src_name, dest_dfs_dict, rules):
        """
        Term数据 销账处理
        根据表定义规则动态执行
        """
        for _, row in rules.iterrows():
            self.logger.debug(f"term_match ,account type :{self.PMT_TERM}")
            src_df = self.search_data(
                src_df, src_name, dest_dfs_dict, row, self.PMT_TERM
            )
        return src_df

    def term_match_static(self, src_df, src_name, dest_dfs_dict, rules):
        """
        Term数据 销账处理
        根据表定义规则动态执行
        """
        for _, row in rules.iterrows():
            self.logger.debug(f"term_match_static ,account type :{self.PMT_TERM}")
            src_df = self.search_amount_data(
                src_df, src_name, dest_dfs_dict, row, self.PMT_TERM
            )
        return src_df

    def adv_match_static(self, src_df, src_name, dest_dfs_dict, rules):
        """
        ADV数据 销账处理
        根据表定义规则动态执行
        """
        for _, row in rules.iterrows():
            self.logger.debug(f"adv_match_static ,account type :{self.PMT_ADV}")
            src_df = self.search_amount_data(
                src_df, src_name, dest_dfs_dict, row, self.PMT_ADV
            )
        return src_df

    def cod_match(self, src_df, src_name, dest_dfs_dict, rules):
        """
        中国的COD数据 销账定义映射方法
        """
        for _, row in rules.iterrows():
            self.logger.debug("China cod_alocation_cn ")
            src_df = self.search_cod_data(src_df, src_name, dest_dfs_dict, row)
        return src_df

    def search_define_data(self, src_df, src_name, dest_dfs_dict, row):
        """
        根据配置规则，查找匹配数据，设定到源表
        bl_customer_master 表的匹配在效率原因SQL层实现
        """
        rule_item = self.get_rule_item_value(row)
        # self.logger.debug(f'search define rule {rule_name}, seq: {rule_seq} ,df count:{len(src_df)}')
        # dst_df = dest_dfs_dict[rule_item.dest_table]
        # 根据账目数据类型分组DF，类型定义来自配置表
        mask = src_df["doc_type"].isin(rule_item.src_data_type.split(","))
        src_df_ts = src_df[mask]
        self.logger.debug(
            f"search define rule {rule_item.rule_name}, seq: {rule_item.rule_seq} ,fullcount:{len(src_df)}, srch count :{len(src_df_ts)}"
        )

        self.logger.debug(
            f"search define finished {rule_item.rule_name}, seq: {rule_item.rule_seq} ,df count:{len(src_df)}"
        )

        return src_df


    def search_data(self, src_df, src_name, dest_dfs_dict, row, payment):
        """ "
        执行查找逻辑
        """
        # 取得配置信息
        # rule_name, rule_seq, src_fields, src_data_type, dst_table, dst_fields, dest_data_type,result_field, result_comment, src_rule_list,dst_rule_list = self.get_rule_item_value(row)
        rule_item = self.get_rule_item_value(row)
        self.logger.debug(
            f"search rule {rule_item.rule_name}, seq: {rule_item.rule_seq} ,df count:{len(src_df)}"
        )

        dst_df = dest_dfs_dict[rule_item.dest_table]

        # 过滤payment类型
        src_df, opst_df = self.filter_payment(src_df=src_df, payment=payment)
        # 过滤对象外的customer_id
        src_df, ext_df = self.filter_ext_customer_id(src_df=src_df)

        # 过滤掉税金对象外的数据
        extax_df = pd.DataFrame()
        # if self.region == "IN":
        src_df, extax_df = self.filter_tax_amount(df=src_df)

        # 合并对象外数据
        opst_df = pd.concat([opst_df, ext_df,extax_df], ignore_index=True)

        # 根据账目数据类型分组DF，类型定义来自配置表
        mask = src_df["doc_type"].isin(rule_item.src_data_type.split(","))
        src_df_ts = src_df[mask]
        # 取出的行从原DF删除。Drop rows from the original DataFrame
        # 如果 src_data_type ，dest_data_type 相同的时候，用相同的 df 做匹配
        src_df = src_df[~mask]
        if rule_item.src_data_type == rule_item.dest_data_type:
            src_df_td = src_df_ts
        else:
            # 如果源df与目标df是同一个表
            if rule_item.dest_table == src_name:
                # 目标对象行取出到新的df
                mask = src_df["doc_type"].isin(rule_item.dest_data_type.split(","))
                src_df_td = src_df[mask]
                src_df = src_df[~mask]
            else:
                src_df_td = dst_df
        s_loop_cnt = 0
        self.logger.debug(
            f"src left count: {len(src_df)} . {rule_item.src_data_type} count :{len(src_df_ts)} . {rule_item.dest_data_type} count:{len(src_df_td)} ."
        )
        # 全部数据
        org_df = pd.concat([src_df_ts, src_df_td, src_df, opst_df], ignore_index=True)
        # TODO
        # 有这几类情况
        # 1.cid 和 so 匹配
        # 2.cid,so, 匹配 amount 相反
        # 3.cid,so, 匹配 amount 合计相反
        # 4.cid匹配  amount 合计相反
        # cid so amount
        if set(rule_item.src_fields) == set(
            self.L_CID + self.L_INO + self.L_AMT
        ) and set(rule_item.dest_fields) == set(self.L_CID + self.L_INO + self.L_AMT):
            hit_df = src_df_ts.apply(
                self.find_cid_so_amt_op, axis=1, dest_df=src_df_td, rule_item=rule_item
            )

        # cid so amount
        elif set(rule_item.src_fields) == set(
            self.L_CID + self.L_SO + self.L_AMT
        ) and set(rule_item.dest_fields) == set(self.L_CID + self.L_INO + self.L_AMT):
            hit_df = src_df_ts.apply(
                self.find_cid_so_amt_op, axis=1, dest_df=src_df_td, rule_item=rule_item
            )

        # cid so amount
        elif set(rule_item.src_fields) == set(
            self.L_CID + self.L_INO + self.L_AMT
        ) and set(rule_item.dest_fields) == set(self.L_CID + self.L_SO + self.L_AMT):
            hit_df = src_df_ts.apply(
                self.find_cid_so_amt_op, axis=1, dest_df=src_df_td, rule_item=rule_item
            )

        # cid so amount
        elif set(rule_item.src_fields) == set(
            self.L_CID + self.L_SO + self.L_AMT
        ) and set(rule_item.dest_fields) == set(self.L_CID + self.L_SO + self.L_AMT):
            hit_df = src_df_ts.apply(
                self.find_cid_so_amt_op, axis=1, dest_df=src_df_td, rule_item=rule_item
            )

        # cid so
        elif set(rule_item.src_fields) == set(self.L_CID + self.L_INO) and set(
            rule_item.dest_fields
        ) == set(self.L_CID + self.L_SO):
            hit_df = src_df_ts.apply(
                self.find_cid_so, axis=1, dest_df=src_df_td, rule_item=rule_item
            )

        # cid so
        elif set(rule_item.src_fields) == set(self.L_CID + self.L_SO) and set(
            rule_item.dest_fields
        ) == set(self.L_CID + self.L_INO):
            hit_df = src_df_ts.apply(
                self.find_cid_so, axis=1, dest_df=src_df_td, rule_item=rule_item
            )

        # cid so
        elif set(rule_item.src_fields) == set(self.L_CID + self.L_SO) and set(
            rule_item.dest_fields
        ) == set(self.L_CID + self.L_SO):
            hit_df = src_df_ts.apply(
                self.find_cid_so, axis=1, dest_df=src_df_td, rule_item=rule_item
            )

        # cid amount
        elif set(rule_item.src_fields) == set(self.L_CID + self.L_AMT) and set(
            rule_item.dest_fields
        ) == set(self.L_CID + self.L_AMT):
            # sequencial amount or all amount
            hit_df = src_df_ts.apply(
                self.find_cid_amt_sum, axis=1, dest_df=src_df_td, rule_item=rule_item
            )

        if hit_df.empty:
            self.logger.debug(f"there is no {rule_item.result_comment} result data.")
            return org_df
        hit_df = [df for df in hit_df if not df.empty]

        if len(hit_df) == 0:
            self.logger.debug(f"there is no {rule_item.result_comment} result data.")
            return org_df

        combined_df = pd.concat(hit_df, ignore_index=True)

        self.logger.debug(
            f"result {rule_item.result_comment} df count: {len(combined_df)}  "
        )
        # 把匹配结果设定到源DF，更新DB用
        df_c = pd.concat([combined_df])
        src_df_ts = self.update_src_df(src_df=src_df_ts, up_df=df_c)
        src_df_td = self.update_src_df(src_df=src_df_td, up_df=df_c)

        self.logger.debug(
            f"source df count: {len(src_df)} .src_df_ts:{len(src_df_ts)} .src_df_td:{len(src_df_td)} . loop count:{s_loop_cnt}"
        )
        # 合并DF 当 dfts和dftd相同的时候，虽然合并结果df中重复，但是登录数据库会去重，不过，后续如果再处理会重复。不好
        if rule_item.src_data_type == rule_item.dest_data_type:
            df_c = pd.concat([src_df_ts, src_df, opst_df], ignore_index=True)
        else:
            df_c = pd.concat([src_df_ts, src_df_td, src_df, opst_df], ignore_index=True)

        self.logger.debug(f"merge df count: {len(df_c)}  ")

        return df_c

    def find_cid_so_amt_op(self, src_row, dest_df, rule_item: RuleItem):
        """
        cid,so,金额 相等
        customer id,sales order (invoice no) 匹配, 金额相等
        """
        if self.is_done_data(src_row):
            return pd.DataFrame()

        result_comment = rule_item.result_comment
        src_so_field = rule_item.src_fields[-1]
        dest_so_field = rule_item.dest_fields[-1]
        src_rule = rule_item.src_rule_list[-1]
        dest_rule = rule_item.dest_rule_list[-1]

        hits_rows = dest_df[
            self.is_customer_eq(src_row, dest_df)
            & self.is_amount_eq(src_row, dest_df)
            & self.is_so_rule_eq(
                src_so_field, dest_so_field, src_rule, dest_rule, src_row, dest_df
            )
        ]

        # amt_diff = abs(
        #     hits_rows["amount"].apply(Decimal) + Decimal(src_row["amount"])
        # )

        hits_rows_amount_sum = Decimal(hits_rows["amount"].sum())
        amt_diff = abs(hits_rows_amount_sum + Decimal(src_row["amount"]))

        hits_rows = pd.concat([pd.DataFrame([src_row]), hits_rows]).reset_index(
            drop=True
        )
        hits_rows = self.set_apply_result_comments(hits_rows, result_comment, amt_diff)

        return hits_rows

    def find_cid_amt_sum(self, src_row, dest_df, rule_item: RuleItem):
        """
        customer id, 金额合计相等
        adv total
        """
        if self.is_done_data(src_row):
            return pd.DataFrame()

        result_comment = rule_item.result_comment

        # 查找源行的amount字段
        src_amt_field = rule_item.src_fields[-1]
        # 源amount值
        src_amt = src_row[src_amt_field]
        # 内循环的amount字段 定义在最后
        dest_amt_field = rule_item.dest_fields[-1]
        # 过滤出customer_id相同的子集
        dest_df_cid = dest_df[self.is_customer_eq(src_row, dest_df)]

        hits_rows = pd.DataFrame()

        if(len(dest_df_cid))<self.COMBINATION_LIMIT:

            amount_ind_dic = {}
            # 组合缓存不再需要，由引擎内部处理
            combi_ids = {}
            for ind_d, row_d in dest_df_cid.iterrows():
                # 收集金额
                amount_ind_dic = self.add_amount_list(
                    amount_ind_dic=amount_ind_dic,
                    ind_d=ind_d,
                    row_d=row_d,
                    field=dest_amt_field,
                )
            combi_ids = self.engine.hold_combination_sums_smart(
                amount_ind_dic=amount_ind_dic,
                sum_amount=src_amt,
            )
            
            if combi_ids:
                if isinstance(combi_ids[0], list):
                    combi_ids = [item for sublist in combi_ids for item in sublist]
                row_index = src_row.name
                self.logger.debug(f'combi_ids count:[{len(combi_ids)}], content:[{combi_ids}] , srcrow index:{row_index}  amt {src_amt}')

                if len(combi_ids) > 0:
                    first_amount_dif = combi_ids[0][1]
                    all_indids = [inid for inid, _ in combi_ids]

                    # 确保 his_combi_ids 已初始化为 set（如果外层未初始化，也在这里初始化）
                    if not hasattr(self, "his_combi_ids") or self.his_combi_ids is None:
                        self.his_combi_ids = set()

                    # 检查新 combi_ids 是否与历史已处理集合有交集
                    overlap = set(all_indids) & self.his_combi_ids
                    if overlap:
                        # 如果存在交集则跳过处理（不追加也不处理）
                        self.logger.debug(
                            f"find_cid_amt_sum: skip src_row index={row_index} because some ids already processed: {overlap}"
                        )
                        return pd.DataFrame()   # 返回空表示跳过

                    # 否则把这些 id 加入 his_combi_ids 并继续处理
                    self.his_combi_ids.update(all_indids)
                    self.logger.debug(
                        f"find_cid_amt_sum: processing src_row index={row_index}, add ids to his_combi_ids: {all_indids}"
                    )
                    
                    hits_rows = dest_df_cid.loc[all_indids]
                    hits_rows = pd.concat([pd.DataFrame([src_row]), hits_rows]).reset_index(
                        drop=True
                    )


                    hits_rows = self.set_apply_result_comments(hits_rows, result_comment, first_amount_dif)
                    return hits_rows
            else:
                return hits_rows
        else:
            return hits_rows

    def is_done_data(self, src_row):
        """
        判断是否已经被执行
        """
        return src_row["aloc_comments"] is not None

    def find_cid_amt_op(self, src_row, dest_df, rule_item: RuleItem):
        """
        customer id, 金额单条数据相等(相反)
        adv total
        """
        if self.is_done_data(src_row):
            return pd.DataFrame()
        result_comment = rule_item.result_comment

        hits_rows = dest_df[
            self.is_customer_eq(src_row, dest_df) & self.is_amount_eq(src_row, dest_df)
        ]
        # 检查金额总和是否等于目标金额,并考虑容差
        # amt_diff = abs(
        #     dest_df["amount"].apply(Decimal) + Decimal(src_row["amount"])
        # )

        hits_rows_amount_sum = Decimal(hits_rows["amount"].sum())
        amt_diff = abs(hits_rows_amount_sum + Decimal(src_row["amount"]))

        hits_rows = pd.concat([pd.DataFrame([src_row]), hits_rows]).reset_index(
            drop=True
        )
        hits_rows = self.set_apply_result_comments(hits_rows, result_comment, amt_diff)
        return hits_rows

    def find_cid_so(self, src_row, dest_df, rule_item: RuleItem):
        """
        cid,so 匹配

        customer id,sales order (invoice no) 匹配
        """
        if self.is_done_data(src_row):
            return pd.DataFrame()

        result_comment = rule_item.result_comment
        src_so_field = rule_item.src_fields[-1]
        dest_so_field = rule_item.dest_fields[-1]
        src_rule = rule_item.src_rule_list[-1]
        dest_rule = rule_item.dest_rule_list[-1]
        hits_rows = dest_df[
            self.is_customer_eq(src_row, dest_df)
            & self.is_so_rule_eq(
                src_so_field, dest_so_field, src_rule, dest_rule, src_row, dest_df
            )
        ]

        hits_rows_amount_sum = Decimal(hits_rows["amount"].sum())
        amt_diff = abs(hits_rows_amount_sum + Decimal(src_row["amount"]))
        hits_rows = pd.concat([pd.DataFrame([src_row]), hits_rows]).reset_index(
            drop=True
        )
        hits_rows = self.set_apply_result_comments(hits_rows, result_comment, amt_diff)
        return hits_rows


    def set_aloc_status(self, r_comment):
        """
        Alocate 状态
        当匹配规则是 部分匹配，顺销匹配时，
        以外时 判定为so match
        """
        # CN 只有sequencial时 需要 确认
        # 其他地区要确认 self.CMT_PAR, 
        if any(keyword in r_comment for keyword in [self.CMT_SEQ,self.CMT_CHK]):
            aloc_field = self.CMT_NOSO
        else:
            aloc_field = self.ALO_SO
        # self.logger.debug(f"r_comment: {r_comment} .aloc_field: {aloc_field}")
        return aloc_field

    last_number = None

    def generate_group(self):
        """
        分组编号初始化

        """
        # 初始情况下，如果没有上一次的数字，则设置为100000
        global last_number
        if "last_number" not in globals():
            last_number = 100000
        # 生成下一个比上一次大的6位数字
        last_number += 1
        # 确保生成的数字不超过999999
        last_number %= 1000000
        return str(last_number)

    def search_cod_data(self, src_df, src_name, dest_dfs_dict, row):
        """
        CN子类实现
        """
        return src_df

    def search_amount_data(self, src_df, src_name, dest_dfs_dict, row, payment):
        """
        Term固定查找
        """
        # 取得配置信息
        rule_item = self.get_rule_item_value(row)

        self.logger.debug(
            f"search rule {rule_item.rule_name}, seq: {rule_item.rule_seq} ,df count:{len(src_df)}"
        )
        # dst_df = dest_dfs_dict[rule_item.dest_table]

        # 过滤掉税金对象外的数据
        extax_df = pd.DataFrame()
        # if self.region == "IN":
        src_df, extax_df = self.filter_tax_amount(df=src_df)
        # 过滤掉已经处理过的数据
        src_df, exdone_df = self.filter_done_data(df=src_df)
        # 过滤payment类型
        src_df, opst_df = self.filter_payment(src_df=src_df, payment=payment)
        # 过滤对象外的customer_id
        src_df, extcid_df = self.filter_ext_customer_id(src_df=src_df)
        # 合并对象外数据
        ext_df = pd.concat([extax_df, exdone_df, opst_df, extcid_df], ignore_index=True)

        # 根据账目数据类型分组DF，类型定义来自配置表 源表类型分组
        mask = src_df["doc_type"].isin(rule_item.src_data_type.split(","))
        src_df_ts = src_df[mask]
        # 取出的行从原DF删除。Drop rows from the original DataFrame
        # 如果 src_data_type ，dest_data_type 相同的时候，用相同的 df 做匹配
        src_df = src_df[~mask]
        # 目标对象行取出到新的df 目标表类型分组
        mask = src_df["doc_type"].isin(rule_item.dest_data_type.split(","))
        src_df_td = src_df[mask]
        src_df = src_df[~mask]
        self.logger.debug(
            f""" all count: {rule_item.src_data_type} count :{len(src_df_ts)}.
                          {rule_item.dest_data_type} count:{len(src_df_td)} .
                          other: {len(src_df)} .ext_tax:{len(extax_df)} . extdone:{len(exdone_df)}"""
        )
        # 按照customerid 分组 amount df索引
        df1 = self.summary_df_by_customer_id(src_df_ts)
        # 按照customerid 分组 amount df索引
        df2 = self.summary_df_by_customer_id(src_df_td)
        self.logger.debug(
            f""" customer id group: {rule_item.src_data_type} count :{len(df1)}.
                           {rule_item.dest_data_type} count:{len(df2)} ."""
        )
        # 计算比较金额分组的合计
        

        # equal_combinations = self.find_equal_combinations(df1, df2)

        equal_combinations = self.engine.find_equal_combinations(df1, df2)

        for (
            cid,
            combo1,
            indices1,
            combo2,
            indices2,
            amt_dif,
            g_id,
        ) in equal_combinations:
            for idx in indices1:
                self.set_multi_group_row(
                    rule_item.result_comment, src_df_ts, amt_dif, g_id, idx
                )
            for idx in indices2:

                self.set_multi_group_row(
                    rule_item.result_comment, src_df_td, amt_dif, g_id, idx
                )
        self.logger.debug(
            f"search_amount_data source df count: {len(src_df)} .src_df_ts:{len(src_df_ts)} .src_df_td:{len(src_df_td)} opst: {len(opst_df)} .ext_tax:{len(extax_df)}. extdone:{len(exdone_df)}"
        )
        # 合并DF 当 dfts和dftd相同的时候，虽然合并结果df中重复，但是登录数据库会去重，不过，后续如果再处理会重复。不好
        df_c = pd.concat([src_df_ts, src_df_td, src_df, ext_df], ignore_index=True)
        self.logger.debug(f"merge df count: {len(df_c)}  ")

        return df_c

    def set_multi_group_row(self, result_comment, src_df_ts, amt_dif, g_id, idx):
        """
        多行结果设值
        """
        if "aloc_group" not in src_df_ts.columns:
            src_df_ts["aloc_group"] = "multi"
        src_df_ts.loc[idx, "aloc_comments"] = result_comment
        src_df_ts.loc[idx, "aloc_status"] = self.set_aloc_status(result_comment)
        src_df_ts.loc[idx, "amount_diff"] = amt_dif
        if (
            src_df_ts.loc[idx, "aloc_group"] == "multi"
            or str(src_df_ts.loc[idx, "aloc_group"]) == "nan"
            or str(src_df_ts.loc[idx, "aloc_group"]) == "None"
        ):
            src_df_ts.loc[idx, "aloc_group"] = str(g_id)
        else:
            src_df_ts.loc[idx, "aloc_group"] = (
                str(src_df_ts.loc[idx, "aloc_group"]) + "/" + str(g_id)
            )
        aloc_group = str(src_df_ts.loc[idx, "aloc_group"])
        src_df_ts.loc[idx, "aloc_group"] = aloc_group[:500]

    def summary_df_by_customer_id(self, df):
        """
        按照 customer_id 对df的金额分组，同时保存对应的df 的索引
        返回这个分组的df
        """
        rdf = (
            df.groupby("customer_id")
            .agg(
                amount=("amount", list), Indices=("amount", lambda x: x.index.tolist())
            )
            .reset_index()
        )
        return rdf


    # def find_equal_combinations(self, src_df, dst_df):
    #     """
    #     查找匹配组合
    #     """
    #     equal_combinations = []
    #     loop_cnt = 0
    #     pay_range = 2
    #     up_rg = 2
    #     low_rg = 4
    #     data_edge = 30
    #     for cid1, amounts1, indices1 in src_df[
    #         ["customer_id", "amount", "Indices"]
    #     ].values:
    #         loop_cnt = loop_cnt + 1
    #         if len(amounts1) < data_edge:
    #             # self.logger.debug(f'combinations compare customer id: {cid1} loop:{loop_cnt} amt cnts: {len(amounts1)}')
    #             for cid2, amounts2, indices2 in dst_df[
    #                 ["customer_id", "amount", "Indices"]
    #             ].values:
    #                 # 这里做匹配率与执行时间的平衡
    #                 # 数据量大的发票数据还是做匹配，但是，不做过多的合计匹配，只做单条，两条匹配
    #                 if len(amounts2) < data_edge:
    #                     up_rg = 2
    #                     low_rg = 8
    #                 else:
    #                     up_rg = 0
    #                     low_rg = 2
    #                 if cid1 == cid2:
    #                     equal_combinations = self.caculate_combinations(
    #                         equal_combinations,
    #                         up_rg,
    #                         low_rg,
    #                         pay_range,
    #                         cid1,
    #                         amounts1,
    #                         indices1,
    #                         amounts2,
    #                         indices2,
    #                     )

    #     return equal_combinations

    # def caculate_combinations(
    #     self,
    #     equal_combinations,
    #     up_rg,
    #     low_rg,
    #     pay_range,
    #     cid1,
    #     amounts1,
    #     indices1,
    #     amounts2,
    #     indices2,
    # ):
    #     """
    #     Calculate combinations of amounts for a given customer ID.

    #     Parameters:
    #     - equal_combinations (list): A list to store equal combinations.
    #     - up_rg (int): Upper range limit.
    #     - low_rg (int): Lower range limit.
    #     - pay_range (int): Range for payment data.
    #     - cid1 (int): Customer ID.
    #     - amounts1 (list): List of amounts for the first set of data.
    #     - indices1 (list): List of indices corresponding to amounts1.
    #     - amounts2 (list): List of amounts for the second set of data.
    #     - indices2 (list): List of indices corresponding to amounts2.
    #     Returns:
    #     - equal_combinations (list): List containing equal combinations for the given customer ID.
    #     """
    #     # self.logger.debug(f'combinations start customer id: {cid1} .amt1 cnts: {len(amounts1)} amt2 cnts: {len(amounts2)}.lower range {low_rg} . upper range {up_rg} . pay_range {pay_range} .')
    #     combos1 = []
    #     # 计算所有id组合的金额合计，保存
    #     for r in range(1, len(amounts1) + 1):
    #         # if r <= low_rg or up_rg > len(amounts1) - r:
    #         # 付款数据 最多两条合计做匹配
    #         if r <= pay_range:
    #             combos1.extend(
    #                 [
    #                     (
    #                         sum([amounts1[i] for i in combo]),
    #                         [indices1[i] for i in combo],
    #                     )
    #                     for combo in combinations(range(len(amounts1)), r)
    #                 ]
    #             )
    #     combos2 = []
    #     # 计算所有id组合的金额合计，保存
    #     for r in range(1, len(amounts2) + 1):
    #         if r <= low_rg or up_rg > len(amounts2) - r:
    #             combos2.extend(
    #                 [
    #                     (
    #                         sum([amounts2[i] for i in combo]),
    #                         [indices2[i] for i in combo],
    #                     )
    #                     for combo in combinations(range(len(amounts2)), r)
    #                 ]
    #             )
    #             # 取得合计小于阈值的金额对应的索引，保存返回
    #     for combo1, indices1 in combos1:
    #         for combo2, indices2 in combos2:
    #             if abs(Decimal(str(combo1)) + Decimal(str(combo2))) <= Decimal(
    #                 str(self.tole)
    #             ):
    #                 group_id = self.generate_group()
    #                 amount_diff = abs(Decimal(str(combo1)) + Decimal(str(combo2)))
    #                 equal_combinations.append(
    #                     (
    #                         cid1,
    #                         combo1,
    #                         indices1,
    #                         combo2,
    #                         indices2,
    #                         amount_diff,
    #                         group_id,
    #                     )
    #                 )
    #                 # self.logger.debug(f'combinations matched customer id: {cid1} . amount sum : {combo1} , {combo2}, group {group_id}')
    #                 break

    #     return equal_combinations

    # def filter_tax_amount(self, df):
    #     # """
    #     # 印度部分入账数据是税
    #     # 与原金额分开，不需要销账，
    #     # 需要过滤掉，提高效率
    #     # """

    #     # sin_df = df[df["doc_type"] == "SIN"]
    #     # no_sin_df = df[df["doc_type"] != "SIN"]
    #     # sin_df["tax_percent"] = sin_df["amount"] / sin_df["amount_oa"]
    #     # t_df = sin_df[sin_df["tax_percent"] > self.IND_TAX]
    #     # ex_df = sin_df[sin_df["tax_percent"] <= self.IND_TAX]
    #     # t_df = pd.concat([t_df, no_sin_df], ignore_index=True)

    #     # return t_df, ex_df
    #     # """
    #     # 过滤对象外/对象内数据：
    #     # - 对象外：doc_type=SBT 且 amount != amount_oa
    #     # - 对象内：其他数据
    #     # """
    #     # # 对象外数据
    #     ex_df = pd.DataFrame()
#         ex_df = df[(df["doc_type"] == "SIN") & (df["amount"] != df["amount_oa"])]

    #     # 对象内数据（其余部分）
    #     in_df = df.drop(ex_df.index)

        # return in_df, ex_df
    def filter_tax_amount(self, df):
        """
        过滤对象外/对象内数据：
        - 对象外：doc_type=SIN 且 差额比例 > gap_rate
        - 对象内：其他数据
        - 如果 gap_rate 未定义（空），则不做处理，ex_df 为空
        """

        # 从配置表里取 gap_rate
        gap_rate_str = self.comm_util.get_def_data_by_name(self.def_data, "excu_tax")

        # gap_rate 未定义 → 不处理，直接返回
        if gap_rate_str == "":
            return df, pd.DataFrame()

        # 转换 gap_rate
        try:
            gap_rate = float(gap_rate_str)
        except ValueError:
            gap_rate = 0.0

        # 复制 df，避免直接改原始
        df = df.copy()

        # 计算差额比例（以 amount_oa 为基准）
        df["gap_ratio"] = df.apply(
            lambda row: abs(row["amount"] - row["amount_oa"]) / row["amount_oa"]
            if row["amount_oa"] != 0 else float("inf"),
            axis=1
        )

        # 对象外数据：差额比例 > gap_rate
        ex_df = df[(df["doc_type"] == "SIN") & (df["gap_ratio"] > gap_rate)]

        # 对象内数据（其余部分）
        in_df = df.drop(ex_df.index)

        return in_df, ex_df


    def filter_done_data(self, df):
        """
        过滤已经处理过的数据
        """
        tgt_df = df[(df["aloc_comments"].isna()) | (df["aloc_comments"] == "")]
        processed_df = df[(~df["aloc_comments"].isna()) & (df["aloc_comments"] != "")]
        return tgt_df, processed_df

    def skip_row(self, row):
        """
        跳过已经处理的行
        """
        if (row["aloc_comments"] is None or row["aloc_comments"] == "") and not (
            row["cid_used"] == "used"
        ):
            return True
        return False

    def get_rule_item_value(self, row):
        """
        取得配置定义到结构变量
        """
        src_fields = row["src_fields"]
        dest_fields = row["dest_fields"]
        src_rule_list = self.parse_rule_string(row["src_match_rules"])
        dest_rule_list = self.parse_rule_string(row["dst_match_rules"])

        return RuleItem(
            rule_name=row["aloc_rule"],
            rule_seq=row["rule_seq"],
            src_fields=(
                [field.strip() for field in src_fields.split(self.ITEM_SPLIT)]
                if src_fields
                else []
            ),
            src_data_type=row["src_data_type"],
            dest_table=row["dest_data"],
            dest_fields=(
                [field.strip() for field in dest_fields.split(self.ITEM_SPLIT)]
                if dest_fields
                else []
            ),
            dest_data_type=row["dest_data_type"],
            result_field=row["result_field"],
            result_comment=row["result_comment_field"],
            src_rule_list=src_rule_list,
            dest_rule_list=dest_rule_list,
        )


    def is_equal(self, src_value, dest_value):
        """
        比较|分割的字符串是否相等，或者包含
        """
        if (src_value is None) or (dest_value is None):
            return False
        src_value = "".join(src_value)
        dest_value = "".join(dest_value)
        if self.ITEM_SPLIT not in src_value and self.ITEM_SPLIT not in dest_value:
            return src_value == dest_value
        else:
            src_list = (
                src_value.split(self.ITEM_SPLIT)
                if self.ITEM_SPLIT in src_value
                else [src_value]
            )
            dest_list = (
                dest_value.split(self.ITEM_SPLIT)
                if self.ITEM_SPLIT in dest_value
                else [dest_value]
            )
            src_set = set(src_list)
            dest_set = set(dest_list)
            same_words = src_set & dest_set
            return bool(same_words)


    def add_amount_list(self, amount_ind_dic, ind_d, row_d, field):
        """
        收集金额计算对象数据
        """
        # amount_list.append({ind_d,row_d[field]})
        # return amount_list
        try:
            amount_value = Decimal(str(row_d[field]))
        except Exception:
            amount_value = Decimal('0')

        # 提取并标准化 pay_date，用于排序优先级（越早越优先）
        # 如果不存在 pay_date 列或为空，使用一个不会影响计算但排序靠后的默认值
        # 这里采用极大日期，确保无 pay_date 的记录排在最后
        if isinstance(row_d, dict):
            pay_date_val = row_d.get('pay_date', None)
        else:
            pay_date_val = row_d['pay_date'] if 'pay_date' in row_d else None

        try:
            pay_date_parsed = pd.to_datetime(pay_date_val) if pay_date_val is not None else pd.Timestamp.max
        except Exception:
            pay_date_parsed = pd.Timestamp.max

        amount_ind_dic[ind_d] = {
            'amount': amount_value,
            'pay_date': pay_date_parsed,
            'index': ind_d,
        }
        return amount_ind_dic

    def add_so_list(self, amount_ind_dic, ind_d, row_d, field):
        """
        在匹配cid，so，时，保存行索引
        """
        amount_ind_dic[ind_d] = str(row_d[field])
        return amount_ind_dic

    def hold_combination_sums(self, amount_ind_dic, sum_amount, combination_sums):
        """
        计算金额组合是否与合计相等
        返回相等的组合
        金额List中的金额组合合计，
        是否与入账金额匹配
        可以匹配的(SIN)金额组，可以销账

        """
        sum_range = 3
        ids = list(amount_ind_dic.keys())
        id_len=len(ids)

        # 由于随机组合会产生爆炸，设定在不同范围的组合数。
        # 下限，上限，组合数-
        ranges = [
                    (0, 10, 5),
                    (10, 20, 10),
                    (20, 50, 6),
                    (50, 300, 5),
                    (300, float('inf'), 3)
                ]
        for low, high, value in ranges:
            if low <= id_len < high:
                sum_range = value
                break
        # self.logger.debug(f"id length:{id_len}. range:{sum_range}")

        for combination_length in range(1, len(ids) + 1):
            if (
                (combination_length <= sum_range)
                # or (sum_range > len(ids) - combination_length)
                or ( combination_length > len(ids) - sum_range)
            ):
                # self.logger.debug(f"combination length:{combination_length}.")
                comb = combinations(ids, combination_length)
                for combination_ids in comb:
                    combination_sum = sum(
                        (amount_ind_dic[id]['amount'] if isinstance(amount_ind_dic[id], dict) else amount_ind_dic[id])
                        for id in combination_ids
                    )
                    # combination_sums[tuple(combination_ids)] = combination_sum
                    if combination_sum > Decimal(str(-sum_amount)):
                        break
                    if abs(combination_sum + Decimal(str(sum_amount))) <= Decimal(
                        str(self.tole)
                    ):
                        amount_dif = abs(combination_sum + Decimal(str(sum_amount)))
                        self.logger.debug(
                            f"Found combination {combination_ids} with sum {sum_amount}"
                        )
                        result_list = [(cid, amount_dif) for cid in combination_ids]
                        return result_list
                    
        return None


    def hold_in_adv_sequential_sums(self, amount_ind_dic, sum_amount, ind_s):
        """
        印度 ADV 顺销的控制
        Customerid相同时，账上有钱就可以
        """
        idx_list = list(amount_ind_dic.keys())
        # 如果连续
        if idx_list == list(range(idx_list[0], idx_list[-1] + 1)):
            # 如果连续，对金额进行求和
            total_amount = sum(
                (amount_ind_dic[idx]['amount'] if isinstance(amount_ind_dic[idx], dict) else amount_ind_dic[idx])
                for idx in idx_list
            )

            if total_amount > Decimal(str(-sum_amount)):
                return None
            if abs(Decimal(str(sum_amount)) + total_amount) <= Decimal(str(self.tole)):
                amount_dif = abs(Decimal(str(sum_amount)) + total_amount)
                if self.is_adjoin(idx_list=idx_list, ind_s=ind_s):
                    result_list = [(cid, amount_dif) for cid in idx_list]
                    return result_list
                    # return idx_list
        # 如果不连续 中断
        else:
            amount_ind_dic.clear()
        # 如果不连续，返回False
        return None

    def is_adjoin(self, idx_list, ind_s):
        """
        判断aging数据是否相邻
        SIN数据与付款数据是否相邻
        """
        if (int(idx_list[0]) - 1 == ind_s) or (int(idx_list[-1]) + 1 == ind_s):
            return True
        return False

    def extract_rule_value_by_index(self, d_row, fields, rule_list, indx):
        """
        提取出对象数据行中，指定位置项目的对象内容。
        """
        field = fields[indx]
        rule_dict = rule_list[indx]
        # 提取源字段值中配置的对象数据
        ext_val, val_list = self.extract_value_by_rule(d_row[field], rule_dict)
        return ext_val

    def extract_rule_values(self, d_row, fields, rule_list):
        """
        提取出对象数据行中，所有项目的对象内容。
        按照顺序，保存在列表中
        """
        src_values = []
        for index, rule_dict in enumerate(rule_list):
            if rule_dict:
                field = fields[index]
                # 提取源字段值中配置的对象数据
                ext_val, val_list = self.extract_value_by_rule(d_row[field], rule_dict)
                if val_list:
                    ext_val = self.ITEM_SPLIT.join(val_list)
                src_values.append(ext_val)
        return src_values

    def extract_value_by_rule(self, content, rule):
        """
        按照规则，提取查询源数据
        type : match : prefix : count : frontend : split : trim
        """
        data_type = rule[self.R_TYPE]
        prefix = rule[self.R_PRIFIX]
        count = rule[self.R_COUNT]
        split = rule[self.R_SPLIT]
        trim = rule[self.R_TRIM]
        fe = rule[self.R_FRONT_END]

        extract_val = ""
        ext_vallist = None
        if data_type == self.RUL_NUMBER:
            if count == "":
                count = 0
            extract_val, ext_vallist = self.extract_cont_number(
                content=content,
                prefix=prefix,
                count=count,
                frontend=fe,
                split=split,
                trim=trim,
            )
        elif data_type == self.RUL_STRING:
            extract_val = self.extract_cont_string(
                content=content,
                prefix=prefix,
                frontend=fe,
                split=split,
                trim=trim,
                count=count,
            )
        elif data_type == self.RUL_VALUE:
            if isinstance(content, str):
                content = str(content).strip()
            extract_val = content

        return extract_val, ext_vallist

    def extract_cont_string(
        self, content, prefix, frontend="front", split="", trim="", count=0
    ):
        """
        提取字符串
        type : match : prefix : count : frontend : split : trim
        例
        str:eq::7:end:/:-
        2334-1849/01 - SK250124-ELE
        3341849
        """
        if split == "":
            split = " "

        if content is None:
            # 处理 content 为 None 的情况
            return None  # 或者根据需要返回一个默认值
        if isinstance(content, str):
            content = str(content).strip()
        # 任意定义字符串开头的情况
        result = ""
        if prefix == "*":
            # 如果 prefix 是 *，则取得全部非数字的字符
            result = re.sub(r"\d", "", content)
            if trim == "d":
                result = re.sub(r"\d", "", result)
        elif isinstance(prefix, str):
            # 如果prefix是字符串，匹配以prefix开头，以/结尾的字符串，并过滤掉prefix

            pattern = re.compile(rf"{prefix}.*?{split}|{prefix}.*?$")
            match = pattern.search(content)
            if match:
                result = match.group()
                result = re.sub(re.escape(prefix), "", result)
                result = re.sub(re.escape(split), "", result)
                if trim == "d":
                    # result = re.sub(r'\d', '', result).strip()
                    result = re.sub(r"(?<!\w)\d+(?!\w)", "", result)
            else:
                # 如果content去掉prefix后的字符串没有/，取得到字符串结尾，并过滤掉prefix
                result = re.sub(re.escape(prefix), "", content)
        # trim
        result = re.sub(re.escape(trim), "", result)

        # cut need length
        if count:
            if len(result) > count:
                if frontend == "end":
                    result = result[(-count):]
                elif frontend == "front":
                    result = result[count:]

        return result

    def extract_cont_number(self, content, prefix, count, frontend, split, trim=""):
        """
        提取数字
        从 content 中提取 prefix开头的数字
        如果 count 是 0 ,那么取得prefix开头的全部数字
        如果 count 大于 0 ,那么取得prefix开头,长度count的数字
        type : match : prefix : count : frontend : split : trim
        """
        # content = content.replace(trim,'')
        content = str(content)
        if count == 999:
            return content, 0
        else:
            if count > 0:
                # 如果 count 为 8，需要匹配连续 8 位数字或 xxxx-xxxx 格式的数字
                if count == 8:
                    if prefix == "":
                        pattern = prefix + r"\d{4}-\d{4}|" + prefix + r"\d{8}"
                    else:
                        pattern = prefix + r"\d{3}-\d{4}|" + prefix + r"\d{7}"
                else:
                    count = count - len(prefix)
                    # 可以匹配 指定开头，位数的数字 例如 AC 765431，787866，712322/ AC713989
                    pattern = prefix + r"\d{" + str(count) + r"}(?:\s?|/?)\b"
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

    def filter_payment(self, src_df, payment):
        """
        根据payment类型，过滤df的内容
        """
        if payment == self.PMT_ADV:
            payment = self.comm_util.get_def_data_by_name(
                self.def_data, "payment_adv"
            ).split(",")
            mask = src_df["payment"].isin(payment)
            obj_df = src_df[mask]
            opst_df = src_df[~mask]
        elif payment == self.PMT_TERM:
            payment = self.comm_util.get_def_data_by_name(
                self.def_data, "payment_terms"
            )
            prefix, separator, suffix = payment.partition("|")
            if prefix == "NOT":
                mask = src_df["payment"].isin(suffix.split(","))
                obj_df = src_df[~mask]
                opst_df = src_df[mask]
            else:
                mask = src_df["payment"].isin(suffix.split(","))
                obj_df = src_df[mask]
                opst_df = src_df[~mask]
        return obj_df, opst_df

    def filter_ext_customer_id(self, src_df):
        """
        过滤掉处理对象外的customer id

        """
        ext_cids = self.comm_util.get_def_data_by_name(self.def_data, "excu_cid").split(
            "|"
        )
        mask = src_df["customer_id"].isin(ext_cids)
        obj_df = src_df[~mask]
        ext_df = src_df[mask]
        return obj_df, ext_df

    def is_adv_row(self, row_d):
        """
        判断某条aging数据是否ADV类型
        """
        payment = self.comm_util.get_def_data_by_name(
            self.def_data, "payment_adv"
        ).split(",")
        return str(row_d["payment"]) in str(payment)

    def parse_rule_string(self, match_rules):
        """
        解析定义内容
        type:match:prefix:count:frontend:split:trim|type:match:prefix:count:frontend:split:trim|...
        """
        # 定义字符串 用 | 分割为list
        match_rule_list = str(match_rules).split(self.ITEM_SPLIT)
        ret_rule_list = []
        # 定义内容 转存到 Dict
        for match_rule in match_rule_list:
            rule_list = match_rule.split(self.RULE_SPLIT)

            if len(rule_list) == self.RULE_ITEM_CNT:
                data_type, d_match, prefix, count, frontend, d_split, d_trim = rule_list
                if count:
                    count = int(count)
                else:
                    count = ""
                ret_rule_list.append(
                    {
                        self.R_PRIFIX: prefix,
                        self.R_COUNT: count,
                        self.R_SPLIT: d_split,
                        self.R_MATCH: d_match,
                        self.R_FRONT_END: frontend,
                        self.R_TRIM: d_trim,
                        self.R_TYPE: data_type,
                    }
                )
            else:
                ret_rule_list.append({})

        return ret_rule_list

    def get_dest_tables_dataframes(self, dest_tables, src_table, src_df, region):
        """
        Get table data frame to dict .
        {tablename,talbe dataframe}
        """
        dataframes_dict = {}
        for dest_table in dest_tables:
            if dest_table == src_table:
                dataframes_dict[dest_table] = src_df
            else:
                df = self.get_bl_table(dest_table, region)
                dataframes_dict[dest_table] = df

        return dataframes_dict

    def get_aloc_rule_def(self, rule_name):
        """
        取得Aloc规则表定义
        """
        sql_query = "SELECT * FROM sc_aloc_rule WHERE aloc_rule = %s and is_live = '1' order by group_order, rule_seq ;"
        parameters = (rule_name,)

        rst = self.db.execute_query_to_pandas(sql_query, parameters)

        return rst

    def get_all_region_aloc_category(self, region):
        """
        取得全部Allocate定义地区
        """
        sql_query = (
            "SELECT distinct otc_region FROM sc_aloc_category WHERE otc_region = %s "
        )
        parameters = (region,)
        df_rg = self.db.execute_query_to_pandas(sql_query, parameters)
        return df_rg

    def get_region_aloc_category(self, region):
        """
        取得sc_aloc_category表 数据
        """
        sql_query = "SELECT * FROM sc_aloc_category WHERE otc_region = %s order by category_order;"
        parameters = (region,)
        rst = self.db.execute_query_to_pandas(sql_query, parameters)
        return rst

    def get_bl_table(self, table_name, region):
        """
        取得参数指定表 数据 bl_aging
        """
        if table_name.lower() == "bl_customer_master":
            sql_query = """SELECT customer_id   ,
                            customer_name   , otc_region   ,
                            c_status   , c_country   ,
                            payment   , currency   ,
                            customer_name_cn   , sales_code   ,
                            sales_name  
                            FROM bl_customer_master WHERE otc_region = %s and c_status != 'CLOSED' """
            parameters = (region,)
        elif table_name.lower() == "raw_cn_released":
            sql_query = """SELECT * FROM raw_cn_released
                            WHERE rl_date >= 
                                CASE 
                                    WHEN EXTRACT(DOW FROM CURRENT_DATE) = 1 THEN CURRENT_DATE - INTERVAL '5 years'
                                    ELSE CURRENT_DATE - INTERVAL '6 months'
                                END;
                            """
            parameters = ()
        else:
            sql_query = f"SELECT * FROM {table_name} WHERE otc_region = %s "
            parameters = (region,)

        rst = self.db.execute_query_to_pandas(sql_query, parameters)
        return rst

    def get_src_bl_table(self, table_name, region):
        """
        取得参数指定 源表数据
        """
        if table_name.lower() == "bl_aging_history":
            if region == "CN":
                sql_query = self.init_src_table_cn_query()
            elif region == "HK":
                sql_query = self.init_src_table_query(region)
            else:
                sql_query = self.init_src_table_query(region)
        else:
            sql_query = f"""SELECT * FROM {table_name} WHERE otc_region = %s """

        parameters = (region,)
        rst = self.db.execute_query_to_pandas(sql_query, parameters)
        return rst

    def init_src_table_cn_query(self):
        """
        初始化查询字符串
        """
        sql_query = """SELECT
                            trim(ag.customer_id) AS customer_id
                            , ag.otc_region
                            , ag.sales_order
                            , ag.doc_type
                            , ag.amount
                            , ag.invoice_no
                            , ag.customer_name
                            , ag.currency
                            , ag.pay_date
                            , ag.doc_date
                            , ag.so_standard
                            , ag.aloc_comments
                            , ag.amount_oa
                            , ag.cn_index
                            , ag.ag_txt
                            , cm.payment
                            , rt.check_no
                            , rt.comments_from_customer 
                            , bt.trans_type
                            , bt.check_no as check_no_bt
                            , null as aloc_group
                            , null as aloc_status
                            , 0 as amount_diff
                        FROM
                            bl_aging_history ag 
                            LEFT OUTER JOIN bl_customer_master cm 
                                ON trim(ag.customer_id) = trim(cm.customer_id) 
                                AND trim(ag.otc_region) = trim(cm.otc_region) 
                                AND trim(ag.currency) = trim(cm.currency) 
                            LEFT OUTER JOIN raw_cn_released rt 
                                ON trim(ag.customer_id) = trim(rt.customer_id) 
                                AND 
                            RIGHT (trim(ag.sales_order) ::text, 10) = rt.check_no 
                            LEFT OUTER JOIN bl_bank_statement bt
                                ON regexp_replace(split_part(ag.sales_order, '/', 1), '-', '') = LEFT(bt.sales_order,8)
                                 AND trim(bt.customer_id) = trim(ag.customer_id) AND bt.trans_type ='shunfeng'        
                        WHERE
                            (cm.c_status != 'CLOSED' or cm.c_status is null)
                            AND ag.otc_region =  %s
                        order by cn_index
                        """
        return sql_query

    def init_src_table_query(self, region):
        """
        查询字符串
        """
        sql_query = """select trim(ag.customer_id) as customer_id,
                                ag.otc_region,
                                CASE 
                                    WHEN ag.otc_region = 'HK' THEN ag.sales_order || ' - ' || COALESCE(ar.sales_order,'')
                                    ELSE ag.sales_order 
                                END AS sales_order,
                                ag.doc_type,
                                ag.amount,
                                ag.invoice_no,
                                ag.customer_name,
                                ag.currency,
                                ag.pay_date,
                                ag.doc_date,
                                ag.so_standard,
                                ag.aloc_comments,
                                ag.amount_oa,
                                ag.asw_seq,
                                ag.ag_txt,
                                cm.payment,
                                null as aloc_group,
                                null as aloc_status,
                                0 as amount_diff
                                from bl_aging_history ag left outer join bl_customer_master cm 
                                on trim(ag.customer_id) = trim(cm.customer_id) 
                                    and trim(ag.currency) = trim(cm.currency) 
                                left outer join raw_aging_report ar on  trim(ag.invoice_no) = trim(ar.invoice_no) """
        if region == "HK":
            sql_query = sql_query + " where ag.otc_region = %s "
        elif region == "SG":
            sql_query = sql_query + " where ag.otc_region = %s "
        else:
            sql_query = (
                sql_query
                + " and trim(ag.otc_region) = trim(cm.otc_region) where ag.otc_region = %s "
            )
        sql_query = sql_query + " order by ag.asw_seq "
        return sql_query

    def is_customer_eq(self, row, df):
        """
        customer id 相同的数据
        """
        return df["customer_id"] == row["customer_id"]

    def is_amount_opps(self, row, df):
        """
        金额和为零的数据
        """
        return abs(df["amount"].apply(Decimal) + Decimal(row["amount"])) <= Decimal(
            self.tole
        )

    def is_amount_eq(self, row, df):
        """
        金额是否OK
        """
        return abs(df["amount"].apply(Decimal) + Decimal(row["amount"])) <= Decimal(
            self.tole
        )

    def is_so_rule_eq(
        self, src_so_field, dest_so_field, src_rule, dest_rule, src_row, dest_df
    ):
        """
        sales order
        row 来自 src
        df 是 dest sin
        """
        so = src_row[src_so_field]
        if so is None:
            return False
        so1list = self.extract_so(so, src_rule)

        def check_sales_order(sales_order):
            so2list = self.extract_so(sales_order, dest_rule)
            return self.is_equal(so1list, so2list)

        return dest_df[dest_so_field].apply(check_sales_order)

    def extract_so(self, content, rule):
        """
        过滤出并格式化SO
        """
        ret_values = []
        so1, so1list = self.extract_value_by_rule(content, rule)
        if so1list:
            so1 = self.ITEM_SPLIT.join(so1list)
        ret_values.append(str(so1))
        # if so1list:
        #     return self.ITEM_SPLIT.join(so1list)
        return ret_values

    def set_apply_result_comments(self, hits_rows, result_comments, amount_diff):
        """
        结果标记
        """
        g_id = self.generate_group()
        # 配对，或者多个
        if len(hits_rows) == 2:
            hits_rows["aloc_comments"] = result_comments
            hits_rows = self.set_apply_sub_result(hits_rows, result_comments, amount_diff, g_id)
        elif len(hits_rows) > 2:
            hits_rows["aloc_comments"] = result_comments + " Multi"
            hits_rows = self.set_apply_sub_result(hits_rows, result_comments, amount_diff, g_id)
        return hits_rows

    def set_apply_sub_result(self, hits_rows, result_comments, amount_diff, g_id):
        """
        结果标记
        """
        # apgid = ' '.join(hits_rows["aloc_group"].astype(str).unique())
        # hits_rows["aloc_group"] = g_id
        hits_rows["aloc_group"] = hits_rows["aloc_group"].fillna("").astype(str)
        hits_rows["aloc_group"] = hits_rows["aloc_group"].apply(
            lambda x: str(g_id) if x == "" else f"{x}/{g_id}"
        )


        hits_rows["amount_diff"] = amount_diff
        # hits_rows["aloc_status"] = result_comments
        hits_rows["aloc_status"] = self.set_aloc_status(result_comments)
        return hits_rows

    def update_src_df(self, src_df, up_df):
        """
        更新df
        """
        if "key_col" not in src_df.columns:
            # 为原始DataFrame添加组合键列
            src_df = src_df.copy()
            src_df.loc[:, "key_col"] = self.generate_key(src_df)

            # 为含有新值的DataFrame添加组合键列
            up_df = up_df.copy()
            up_df.loc[:, "key_col"] = self.generate_key(up_df)

            # 删除key_col列中的重复值
            src_df = src_df.drop_duplicates(subset="key_col", keep="first")
            up_df = up_df.drop_duplicates(subset="key_col", keep="first")

            # 重置索引
            src_df = src_df.reset_index(drop=True)
            up_df = up_df.reset_index(drop=True)

            # 使用组合键列作为索引
            src_df.set_index("key_col", inplace=True)
            up_df.set_index("key_col", inplace=True)

        # 更新数据
        src_df.update(up_df)

        return src_df

    def generate_key(self, df):
        """
        初始化key列
        """
        return (
            df["otc_region"].astype(str)
            + "_"
            + df["customer_id"].astype(str)
            + "_"
            + df["amount"].astype(str)
            + "_"
            + df["sales_order"].astype(str)
            + "_"
            + df["invoice_no"].astype(str)
        )
