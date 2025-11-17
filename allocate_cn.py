"""
高效化 中国区处理

"""

from decimal import Decimal, getcontext
import pandas as pd

from allocate_common import AllocateAction

getcontext().prec = 10


class ChinaAllocateAction(AllocateAction):
    """
    中国定制化处理
    """



    method_adv_map = {
        "1": "find_adv_match",
        "2": None,
        "3": "find_adv_partial_match",
        "4": "find_asiapay_match",
        "5": "find_asiapay_partial_match",
        "6": "find_sequence_match",
    }

    method_term_map = {"1": "find_asiapay_match", 
                       "2": "find_asiapay_partial_match",
                       "3": "find_sequence_match",
                       "4": "find_adv_match",
                       "5": None,
                       "6": "find_adv_partial_match",}

    def adv_match(self, src_df, src_name, dest_dfs_dict, rules):
        """
        ADV数据 销账处理
        根据表定义规则动态执行
        """
        for r_ind, row in rules.iterrows():
            self.logger.debug(f"adv_match ,account type :{self.PMT_ADV}")
            src_df = self.cn_search_data(src_df, row, self.PMT_ADV)
        # self.logger.debug(f'CN adv_match ,account type :{self.PMT_ADV}')
        # src_df = self.search_data(src_df,src_name, dest_dfs_dict, row, self.PMT_ADV)
        return src_df

    def term_match(self, src_df, src_name, dest_dfs_dict, rules):
        """
        Term数据 销账处理
        根据表定义规则动态执行
        """
        for r_ind, row in rules.iterrows():
            self.logger.debug(f"term_match ,account type :{self.PMT_TERM}")
            src_df = self.cn_search_data(src_df, row, self.PMT_TERM)
        #     src_df = self.search_data(src_df,src_name, dest_dfs_dict, row, self.PMT_TERM)
        # self.logger.debug(f'CN term_match ,account type :{self.PMT_TERM}')
        # src_df = self.search_data(src_df,src_name, dest_dfs_dict, row, self.PMT_ADV)
        return src_df

    def cn_search_data(self, src_df, row, payment):
        """ "
        执行查找逻辑
        """
        # 取得配置信息
        rule_item = self.get_rule_item_value(row)

        self.logger.debug(
            f"search rule {rule_item.rule_name}, seq: {rule_item.rule_seq} ,df count:{len(src_df)}"
        )

        # 过滤掉已经处理过的数据
        src_df, exdone_df = self.filter_done_data(df=src_df)
        self.logger.debug(f" need to do {len(src_df)} . done data :{len(exdone_df)}")
        # 过滤payment类型
        src_df, opst_df = self.filter_payment(src_df=src_df, payment=payment)
        # 过滤对象外的customer_id
        src_df, ext_df = self.filter_ext_customer_id(src_df=src_df)
        # 合并对象外数据
        opst_df = pd.concat([opst_df, ext_df, exdone_df], ignore_index=True)
        # 根据账目数据类型分组DF，类型定义来自配置表
        mask = src_df["doc_type"].isin(rule_item.src_data_type.split(","))
        src_nosin_df = src_df[mask]
        # 取出的行从原DF删除。Drop rows from the original DataFrame
        # 如果 src_data_type ，dest_data_type 相同的时候，用相同的 df 做匹配
        src_df = src_df[~mask]
        # 目标对象行取出到新的df
        mask = src_df["doc_type"].isin(rule_item.dest_data_type.split(","))
        dest_sin_df = src_df[mask]
        src_df = src_df[~mask]

        self.logger.debug(
            f"""src left count: {len(src_df)} .
                           {rule_item.src_data_type} count :{len(src_nosin_df)} .
                             {rule_item.dest_data_type} count:{len(dest_sin_df)} ."""
        )

        org_df = pd.concat(
            [src_nosin_df, dest_sin_df, src_df, opst_df], ignore_index=True
        )
        if self.get_dynamic_method(ridx=rule_item.rule_seq, payment=payment) is None:
            return org_df

        # adv match
        adv_amount_df = src_nosin_df.apply(
            self.dynamic_match,
            axis=1,
            dest_sin_df=dest_sin_df,
            ridx=rule_item.rule_seq,
            payment=payment,
            result_comment=rule_item.result_comment,
            rule_item=rule_item
        )

        if adv_amount_df.empty:
            self.logger.debug(f"there is no {rule_item.result_comment} result data.")
            return org_df
        adv_amount_df = [df for df in adv_amount_df if not df.empty]

        if len(adv_amount_df) == 0:
            self.logger.debug(f"there is no {rule_item.result_comment} result data.")
            return org_df

        combined_df = pd.concat(adv_amount_df, ignore_index=True)

        self.logger.debug(
            f"result {rule_item.result_comment} df count: {len(combined_df)}  "
        )
        # 把匹配结果设定到源DF，更新DB用
        df_c = pd.concat([combined_df])
        dest_sin_df = self.update_src_df(src_df=dest_sin_df, up_df=df_c)
        src_nosin_df = self.update_src_df(src_df=src_nosin_df, up_df=df_c)

        df_c = pd.concat(
            [src_nosin_df, dest_sin_df, src_df, opst_df], ignore_index=True
        )

        self.logger.debug(
            f"""left count: {len(src_df)} .nosin :{len(src_nosin_df)} .
                          sin:{len(dest_sin_df)} """
        )

        self.logger.debug(f"merge df count: {len(df_c)}  ")

        return df_c

    def dynamic_match(self, row, dest_sin_df, ridx, payment, result_comment, rule_item):
        """
        动态启动匹配方法
        """
        func_name = self.get_dynamic_method(ridx, payment)
        method = getattr(self, func_name)
        return method(row, dest_sin_df, result_comment, rule_item)

    def get_dynamic_method(self, ridx, payment):
        """
        动态启动匹配方法
        """
        if payment == self.PMT_ADV:
            return self.method_adv_map.get(str(ridx), None)
        else:
            return self.method_term_map.get(str(ridx), None)

    def search_cod_data(self, src_df, src_name, dest_dfs_dict, row):
        """
        中国COD销账数据查询专属方法

        """
        rule_item = self.get_rule_item_value(row)
        self.logger.debug(
            f"search rule {rule_item.rule_name}, seq: {rule_item.rule_seq} ,df count:{len(src_df)}"
        )
        # 过滤cod对象数据
        # TODO checknumber
        # 取得shunfeng发票数据
        cod_sin_df = pd.DataFrame()
        if self.region == "CN":
            # 存在trans_type ='shunfeng'的数据是cod的发票SIN数据
            cod_mask = src_df["trans_type"] == "shunfeng"
            cod_sin_df = src_df[cod_mask]
            ext_cod_df = src_df[~cod_mask]

        self.logger.debug(f"COD count {len(cod_sin_df)}")

        # 取得aging中与发票数据匹配的收款数据 合并为新的df src_sin_row, cod_nosin_df)
        cod_match_df = cod_sin_df.apply(
            self.find_cod_match, axis=1, cod_nosin_df=ext_cod_df
        )
        # 在添加到 f_df 列表之前检查 DataFrame 是否为空
        if cod_match_df.empty:
            self.logger.debug("there is no cod match data.")
            return src_df
        cod_match_df = [df for df in cod_match_df if not df.empty]
        # 然后再执行 concat 操作
        cod_match_df = pd.concat(cod_match_df)

        self.logger.debug(
            f"result {rule_item.result_comment} df count: {len(cod_match_df)}  "
        )

        cod_sin_df = self.update_src_df(src_df=cod_sin_df, up_df=cod_match_df)
        ext_cod_df = self.update_src_df(src_df=ext_cod_df, up_df=cod_match_df)

        df_c = pd.concat([cod_sin_df, ext_cod_df], ignore_index=True)

        self.logger.debug(f"cod records df count:{len(cod_match_df)}")

        self.logger.debug(
            f"""All count: {len(df_c)} .no cod :{len(ext_cod_df)} .
                          cod sin:{len(cod_sin_df)} """
        )

        return df_c

    def find_neg_amount(self, row, df):
        """
        # 定义条件函数，接收 src_df 作为参数
        """
        # 查找相同 customer_id，amount 是负数且相反的行
        neg_rows = df[
            (df["customer_id"] == row["customer_id"])
            & (
                abs(df["amount"].apply(Decimal) + Decimal(row["amount"]))
                <= Decimal(self.tole)
            )
        ]

        # 检查是否找到相应的行
        if not neg_rows.empty:
            return neg_rows
        else:
            return pd.DataFrame()  # 返回空 DataFrame，表示未找到匹配的行

    def find_cod_match(self, src_sin_row, cod_nosin_df):
        """
        # 定义条件函数，接收 src_df 作为参数
        """

        result_comment = "COD Match "
        # ckeck_no_field = 'sales_order'
        # & self.is_check_no_eq(ckeck_no_field,src_sin_row,cod_nosin_df)

        hits_rows = cod_nosin_df[
            self.is_customer_eq(src_sin_row, cod_nosin_df)
            & self.is_amount_eq(src_sin_row, cod_nosin_df)
        ]
        # 计算同一客户的所有金额总和

        # 检查金额总和是否等于目标金额,并考虑容差
     
        decimal_amount_sum = sum(hits_rows.iloc[0:]["amount"].apply(Decimal))
        amt_diff = abs(decimal_amount_sum + Decimal(src_sin_row["amount"]))

        hits_rows = pd.concat([pd.DataFrame([src_sin_row]), hits_rows]).reset_index(
            drop=True
        )
        self.set_apply_result_comments(hits_rows, result_comment, amt_diff)
        return hits_rows

    def is_amount_eq(self, src_sin_row, cod_nosin_df):
        """
        金额是否OK
        """
        return abs(
            cod_nosin_df["amount"].apply(Decimal) + Decimal(src_sin_row["amount"])
        ) <= Decimal(self.tole)

    def set_cod_match_row(self, row, df):
        """
        # 定义条件函数，接收 src_df 作为参数
        """
        src_index = []
        # 查找相同 customer_id，amount 是负数且相反的行 abs(str(df['amount'] + row['amount']) <= self.tole
        eq_row = df[
            (df["customer_id"] == row["customer_id"]) & (df["amount"] == row["amount"])
        ]
        neg_row = df[
            (df["customer_id"] == row["customer_id"]) & (df["amount"] == -row["amount"])
        ]
        # 检查是否找到相应的行
        if not eq_row.empty:
            src_index.append(eq_row.index)
        if not neg_row.empty:
            src_index.append(neg_row.index)

    # 1.
    # ADV cid 一对so匹配 checknomber amount合计0
    # SIN sales_order列， 2342-1624/01 - QUO#2342-1432
    # 非SIN comments_from_customer列 23344776 一个

    # 2.
    # ADV multi cid相同 多个so匹配 checknomber， amount合计0
    # SIN sales_order列， 2342-1624/01 - QUO#2342-1432
    # 非SIN comments_from_customer列 23344776/23419811 多个

    # 3.
    # ADV Partial cid相同 so相同
    # SIN 同上 一个
    # 非SIN 同上多个

    # 4.
    # AsiaPay cid so  amount合计0 配对
    # SIN sales_order列 2343-6322/01 - 5/03/2024  17:4
    # 非SIN sales_order列 23436322 5/03/2024  17:44:16
    #

    # 5. AsiaPay cid so 配对 amount不看
    # 同上
    #

    def find_adv_match(self, src_nosin_row, dest_sin_df, result_comment, rule_item):
        """
        查找 ADV类型的匹配
        # 1.
        # ADV cid 一对so匹配 checknomber amount合计0
        # SIN sales_order列， 2342-1624/01 - QUO#2342-1432
        # 非SIN comments_from_customer列 23344776 一个
        # 2.
        # ADV multi cid相同 多个so匹配 checknomber， amount合计0
        # SIN sales_order列， 2342-1624/01 - QUO#2342-1432
        # 非SIN comments_from_customer列 23344776/23419811 多个
        """
        # rule_item.src_fields[-1]
        so_field = "comments_from_customer"
        # result_comment = 'ADV Match '
        
        return self.so_amount_match(
            src_nosin_row, dest_sin_df, so_field, result_comment
        )


    def find_adv_partial_match(self, src_nosin_row, dest_sin_df, result_comment, rule_item):
        """
        查找 ADV类型的 部分匹配
        # ADV Partial cid相同 so相同
        # SIN 同上 一个
        # 非SIN 同上多个
        """
        # # rule_item.src_fields[-1]
        so_field = "comments_from_customer"
        # result_comment = 'ADV Partial'
        return self.partial_match(src_nosin_row, dest_sin_df, result_comment, so_field)

    def find_asiapay_match(self, src_nosin_row, dest_sin_df, result_comment, rule_item):
        """
        查找 ADV类型的匹配
        # 4.
        # AsiaPay cid so  amount合计0 配对
        # SIN sales_order列 2343-6322/01 - 5/03/2024  17:4
        # 非SIN sales_order列 23436322 5/03/2024  17:44:16
        #

        # 5. AsiaPay cid so 配对 amount不看
        # 同上
        #
        """
        # # rule_item.src_fields[-1]
        so_field = "sales_order"
        # result_comment = 'Asiapay Match'

        return self.so_amount_match(
            src_nosin_row, dest_sin_df, so_field, result_comment
        )

    def so_amount_match(self, src_nosin_row, dest_sin_df, so_field, result_comment):
        """
        salesorder and amount match
        """
        ret = pd.DataFrame()
        target_amount = Decimal(src_nosin_row["amount"])
        hits_rows = dest_sin_df[
            self.is_customer_eq(src_nosin_row, dest_sin_df)
            & self.is_so_eq(so_field, src_nosin_row, dest_sin_df)
        ]
        # 计算同一客户的所有金额总和
        total_amount = sum(map(Decimal, hits_rows["amount"]))

        # 检查金额总和是否等于目标金额,并考虑容差
        amt_diff = abs(total_amount + target_amount)
        if amt_diff <= Decimal(str(self.tole)):
            hits_rows = pd.concat(
                [pd.DataFrame([src_nosin_row]), hits_rows]
            ).reset_index(drop=True)
            self.set_apply_result_comments(hits_rows, result_comment, amt_diff)
            ret = hits_rows
        return ret

    def find_asiapay_partial_match(self, src_nosin_row, dest_sin_df, result_comment, rule_item):
        """
        查找 ADV类型的匹配
        # 4.
        # AsiaPay cid so  amount合计0 配对
        # SIN sales_order列 2343-6322/01 - 5/03/2024  17:4
        # 非SIN sales_order列 23436322 5/03/2024  17:44:16
        #

        # 5. AsiaPay Partial cid so 配对 amount不看
        # 同上
        #
        """
        # result_comment = 'Asiapay Partial Match'
        # # rule_item.src_fields[-1]
        so_field = "sales_order"
        return self.partial_match(src_nosin_row, dest_sin_df, result_comment, so_field)

    
    def partial_match(self, src_nosin_row, dest_sin_df, result_comment, so_field):
        """
        so match only
        """
        hits_rows = dest_sin_df[
            self.is_customer_eq(src_nosin_row, dest_sin_df)
            & self.is_so_eq(so_field, src_nosin_row, dest_sin_df)
        ]
        hits_rows = pd.concat([pd.DataFrame([src_nosin_row]), hits_rows]).reset_index(
            drop=True
        )
        self.set_apply_result_comments(hits_rows, result_comment, 0)
        return hits_rows

    def find_sequence_match(self, src_nosin_row, dest_sin_df, result_comment, rule_item):
        """
        顺序销账
        
        """
        # result_comment = "Term Sequential match"
        return self.find_seq_match(src_nosin_row, dest_sin_df, result_comment)

    def find_seq_match(self, src_nosin_row, dest_sin_df, result_comment):
        """
        顺序销账的实现（兼容旧接口）：
        - 会收集所有可能的匹配（不在第一次匹配时直接 break）
        - 返回值 **始终** 是 pandas.DataFrame：
            - 无匹配 -> 返回空 DataFrame()
            - 只有一个匹配 -> 返回包含 src 行 + 命中行 的 DataFrame（兼容旧逻辑）
            - 多个匹配 -> 返回把每个匹配（每个匹配中都包含 src 行 + 命中行）按行 concat 后的 DataFrame
        """
        sum_list = []
        dest_sin_df_cid = dest_sin_df[dest_sin_df["customer_id"] == src_nosin_row["customer_id"]]
        pan_amt = Decimal(str(src_nosin_row["amount"]))
        sin_amt = Decimal("0")
        amount_diff = Decimal("0")

        results1 = []  # 存放每个匹配（每个元素是一个 DataFrame）
        results2 = []
        for ind_d, row_d in dest_sin_df_cid.iterrows():
            sin_r_amt = Decimal(str(row_d["amount"]))
            sin_amt = sin_amt + sin_r_amt
            sum_list.append(ind_d)

            # 单行命中（当前行就可配平）
            if abs(pan_amt + sin_r_amt) <= Decimal(str(self.tole)):
                hits_rows = dest_sin_df_cid.loc[[ind_d]]
                hits_rows = pd.concat([pd.DataFrame([src_nosin_row]), hits_rows]).reset_index(drop=True)
                # 设置结果注释（保持原行为）
                # self.set_apply_result_comments(hits_rows, result_comment, amount_diff)
                results1.append(hits_rows)
                # 不再 break，继续查找可能的其它匹配

            # 累积多行命中
            elif abs(pan_amt + sin_amt) <= Decimal(str(self.tole)):
                amount_diff = abs(pan_amt + sin_amt)
                hits_rows = dest_sin_df_cid.loc[sum_list]
                hits_rows = pd.concat([pd.DataFrame([src_nosin_row]), hits_rows]).reset_index(drop=True)
                self.set_apply_result_comments(hits_rows, result_comment, amount_diff)
                results2.append(hits_rows)
                break

            # 如果累积超过目标，则清空索引列表（保持原逻辑：只清空 sum_list）
            if sin_amt > Decimal(str(-pan_amt)):
                sum_list = []
                # 保持 sin_amt 不变（与原代码一致），避免改变逻辑行为

        df1 = pd.DataFrame()
        if results1:
            df1 = pd.concat(results1, ignore_index=True)
            self.set_apply_result_comments(df1, result_comment, amount_diff)
        df2 = pd.DataFrame()
        if results2:
            df2 = pd.concat(results2, ignore_index=True)

        if df1.empty and df2.empty:
            return pd.DataFrame()
        elif df1.empty:
            return df2
        elif df2.empty:
            return df1
        else:
            return pd.concat([df1, df2], ignore_index=True)


    def find_sum_match(self, row, df):
        """
        查找
        """

        neg_rows = df[self.is_customer_eq(row, df) & self.is_amount_opps(row, df)]

        # 检查是否找到相应的行
        if not neg_rows.empty:
            return neg_rows
        else:
            return pd.DataFrame()  # 返回空 DataFrame，表示未找到匹配的行

    def find_amount_sum_equal(self, row, df):
        """
        查找同一客户下,DataFrame中所有金额合计与给定行金额相等的情况
        """
        customer_id = row["customer_id"]
        target_amount = Decimal(row["amount"])

        # 筛选同一客户的行
        customer_rows = df[df["customer_id"] == customer_id]

        # 计算同一客户的所有金额总和
        total_amount = sum(map(Decimal, customer_rows["amount"]))

        # 检查金额总和是否等于目标金额,并考虑容差
        if abs(total_amount + target_amount) <= Decimal(str(self.tole)):
            return customer_rows
        else:
            return pd.DataFrame()

    def is_check_no_eq(self, ck_filed, src_nosin_row, dest_sin_df):
        """
        check_no
        row 来自 src
        df 是 dest sin
        """
        # return True
        # aging中入账数据的 checkno 保存在 sales_order
        in_check_no = src_nosin_row[ck_filed]
        if in_check_no is None:
            return True

        # 比较so匹配到的银行数据的checkno与aging数据的checkno是否相同
        def check_no_match(bk_check_no):
            if bk_check_no is None:
                return True
            if bk_check_no == in_check_no:
                return True
            return False

        # 来自bankstatment的出账时登录的 check no
        return dest_sin_df["check_no_bt"].apply(check_no_match)

    def is_so_eq(self, so_filed, src_nosin_row, dest_sin_df):
        """
        sales order
        row 来自 src
        df 是 dest sin
        """
        # SLI,ACB,ARR,TCR,AHB,AHR,AAB,STF,A60,SBD,SLC,
        # comments_from_customer列 付款数据 是 8 位 so，或者/分割多个8位so

        # SIN
        # sales_order列 是类似 2341-5619/01 - 27/02/2024  15: 这种格式，开头是so，有分割符等等

        so = src_nosin_row[so_filed]
        if so is None:
            return False
        so1list = self.extract_so(so)

        def check_sales_order(sales_order):
            so2list = self.extract_so(sales_order)
            return self.is_equal(so1list, so2list)

        return dest_sin_df["sales_order"].apply(check_sales_order)

    def extract_so(self, content):
        """
        过滤出并格式化SO
        """
        _, so1list = self.extract_cont_number(
            content, prefix="", count=8, frontend="", split="", trim=""
        )

        if so1list:
            return self.ITEM_SPLIT.join(so1list)
        return None
    
    # def __init__(self, name: str, logger=None) -> None:
    #     """
    #     构造方法
    #     """
    #     super().__init__(name, logger)


    # def extract_row_value(self,d_row,field):
    #     """
    #     提取出对象数据行中，所有项目的对象内容。
    #     按照顺序，保存在列表中
    #     num:eq::8:::
    #     str:eq::8:front:/:-
    #     str:eq::8:front: :
    #     num:pat::8:::
    #     """
    #     rule_dict = 'str:eq::8:front:/:-'
    #     ext_val,val_list = self.extract_value_by_rule(d_row[field],rule_dict)

    
    # def set_apply_result_comments(self, hits_rows, result_comments, amount_diff):
    #     """
    #     结果标记
    #     """
    #     g_id = self.generate_group()
    #     # 配对，或者多个
    #     if len(hits_rows) == 2:
    #         hits_rows["aloc_comments"] = result_comments
    #     elif len(hits_rows) > 2:
    #         hits_rows["aloc_comments"] = result_comments + " Multi"
    #     hits_rows["aloc_group"] = g_id
    #     hits_rows["amount_diff"] = amount_diff
    #     hits_rows["aloc_status"] = self.set_aloc_status(result_comments)


    
    # def is_customer_eq(self, row, df):
    #     """
    #     customer id 相同的数据
    #     """
    #     return df["customer_id"] == row["customer_id"]

    # def is_amount_opps(self, row, df):
    #     """
    #     金额和为零的数据
    #     """
    #     return abs(df["amount"].apply(Decimal) + Decimal(row["amount"])) <= Decimal(
    #         self.tole
    #     )

    # def update_src_df(self, src_df, up_df):
    #     """
    #     更新df
    #     """
    #     if "key_col" not in src_df.columns:
    #         # 为原始DataFrame添加组合键列
    #         src_df = src_df.copy()
    #         src_df.loc[:, "key_col"] = self.generate_key(src_df)

    #         # 为含有新值的DataFrame添加组合键列
    #         up_df = up_df.copy()
    #         up_df.loc[:, "key_col"] = self.generate_key(up_df)

    #         # # 找出重复的key_col值
    #         # duplicates_src = src_df[src_df['key_col'].duplicated(keep=False)]

    #         # # 输出重复的key_col值
    #         # self.logger.debug(f"在src_df中重复的key_col值：\n{duplicates_src}")

    #         # # 对up_df执行相同的操作
    #         # duplicates_up = up_df[up_df['key_col'].duplicated(keep=False)]

    #         # # 输出重复的key_col值
    #         # self.logger.debug("在up_df中重复的key_col值：\n{duplicates_up}")

    #         # # 检查是否有重复的key_col
    #         # if src_df['key_col'].duplicated().any() or up_df['key_col'].duplicated().any():
    #         #     raise ValueError("存在重复的key_col，无法更新")

    #         # 删除key_col列中的重复值
    #         src_df = src_df.drop_duplicates(subset="key_col", keep="first")
    #         up_df = up_df.drop_duplicates(subset="key_col", keep="first")

    #         # 重置索引
    #         src_df = src_df.reset_index(drop=True)
    #         up_df = up_df.reset_index(drop=True)

    #         # 使用组合键列作为索引
    #         src_df.set_index("key_col", inplace=True)
    #         up_df.set_index("key_col", inplace=True)

    #     # 更新数据
    #     src_df.update(up_df)

    #     return src_df

    # def generate_key(self, df):
    #     """
    #     初始化key列
    #     """
    #     return (
    #         df["otc_region"].astype(str)
    #         + "_"
    #         + df["customer_id"].astype(str)
    #         + "_"
    #         + df["amount"].astype(str)
    #         + "_"
    #         + df["sales_order"].astype(str)
    #         + "_"
    #         + df["invoice_no"].astype(str)
    #     )
