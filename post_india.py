"""
# Cash Posting Action India
"""
import re
import pandas as pd
from post_common import PostAction, RuleItem

from decimal import Decimal, getcontext

getcontext().prec = 10





class PostActionIndia(PostAction):
    """
    印度定制化处理
    """

    CMT_1 = ""

    def search_str(
        self,
        ind_s,
        src_content,
        src_df,
        dst_df,
        rule_item: RuleItem,
        result_set_flg=True,
        fuz_type=2,
    ):
        """
        查找 str 的定义
        type:prefix:count:split:trim
        str:22:::
        """
        extract_val, vl = self.extract_src_value(src_content, rule_item.rule1)
        if extract_val:
            self.set_srcdf_tempfield(src_df, ind_s, rule_item.temp_fields, extract_val)
            # 调用向量查找 TODO
            matched_df = self.find_vector_dataframe(
                src_val=extract_val,
                dest_df=dst_df,
                rule_item=rule_item,
            )
            # historytracker的Remitter Account No，查找到 customer id
            # historytracker的 customer名，查找到 customer id
            # bankstatment account_no_customer bl_history_tracker customer_account
            # 当需要处理附加aging amount的情况
            if (
                rule_item.dst_table1 == "bl_history_tracker"
                and (rule_item.dst_field1 == "customer_account" or rule_item.dst_field1 == "customer_name")
                and (rule_item.src_field1 == "account_no_customer" or rule_item.src_field1 == "customer_name")
                and rule_item.div_rule2 == "agingamount"
            ):
                
                #
                if len(matched_df) >= 1:
                    # historytracker 匹配结果的 cid
                    amount = src_df.iloc[ind_s][rule_item.dst_field2]
                    aging_df = self.dest_dfs_dict[rule_item.dst_table2]
                    for ind_crst, row_rst in matched_df.iterrows():
                        customer_id = row_rst[rule_item.src_field2]
                        comments, amount_match = self.check_aging_amount_by_id(dest_df=aging_df,customer_id=customer_id,
                                                                            amount=amount,rule_item=rule_item)
                        if amount_match:
                            break
                    if amount_match:
                        self.set_amount_match_field(
                            src_df,
                            ind_s,
                            customer_id,
                            rule_item,
                            comments,
                        )
                        self.logger.debug(
                            f"""AccountNo Aging amount match [{amount_match}] :[{src_content}] extract value: [{extract_val}]
                                            cid [{customer_id}], amount: [{amount}], [{comments}]."""
                        )
                    # elif(len(matched_df)==1):
                    #     self.set_rows_field(
                    #     src_df,
                    #     ind_s,
                    #     matched_df,
                    #     rule_item,
                    #     result_set_flg,
                    #     )
                    #     self.logger.debug(
                    #         f"""history_tracker mactch value src content :[{src_content}]  
                    #                         extract value: [{extract_val}]
                    #                         rule:[{rule_item.rule1}] [{rule_item.search_rule1}]."""
                    #     )
            else:
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

    def set_amount_match_field(
        self,
        src_df,
        ind_s,
        result_cid,
        rule_item:RuleItem,
        comments,
    ):
        """
        amount match 的结果设定
        """
        # result_cid = ""
        # result_cid,add_values,single_bool = self.get_values_from_result_df(matched_df,rule_item=rule_item)
        # 保存结果的结果df的目标字段 self.remove_duplicates(result_cid)
        src_df.loc[ind_s, rule_item.result_field] = result_cid
        # if rule_item.add_fields:
        #     self.set_add_fields(src_df, ind_s, row_d, rule_item.add_fields)
        # ipf_sts= self.MULTI_MATCHED
        # if single_bool:
        # ipf_sts= self.SINGLE_MATCHED
        ipf_sts = self.set_confidence(rule_confidence=rule_item.confidence)
        src_df = self.set_match_result(
            src_df=src_df,
            ind_s=ind_s,
            post_text=rule_item.result_comment + comments+ " cfd: " + rule_item.confidence,
            ipf_status=ipf_sts,
        )
        return src_df
    
    def check_aging_amount_by_id(
        self, dest_df, customer_id, amount, rule_item: RuleItem
    ):
        """
        通过customerid，查找Aging数据中的发票金额，
        这个 cid 从historytracker得到
            1.Remitter Account No 得到cid
            2.customer name 得到cid
        计算金额与银行入账数据的关系
        """
        self.set_cls_define_data(self.region)
        div = "Remitter Account No"
        # 过滤出SIN数据 cid 对象数据
        sin_cid_mask = (dest_df["doc_type"] == "SIN") & (
            dest_df["customer_id"].str.strip() == customer_id
        )
        sin_cid_df = dest_df[sin_cid_mask]

        # 计算金额是否可以匹配
        comments, amount_match = self.caculate_sin_df_amount(
            sin_df=sin_cid_df, amount=amount, id_name_div=div
        )

        return comments, amount_match

    def check_aging_amount_by_name(
        self, dest_df, customer_name, amount, rule_item: RuleItem
    ):
        """
        通过custome name 查找aging中发票金额
        计算金额与银行入账数据的关系
        """
        self.set_cls_define_data(self.region)
        div = "Customer name "
        # 过滤出SIN数据 cutomername 对象数据
        sin_mask = dest_df["doc_type"] == "SIN"
        sin_df = dest_df[sin_mask]
        find_list = self.generate_edge_substrings(customer_name,rule_item.dst_field1, 1)

        # 根据客户名称，查找aging的数据
        for find_str in find_list:
            mask = dest_df["customer_name"].str.contains(
                find_str, case=False, na=False, regex=True
            )
            if mask.any():
                break

        #  & (dest_df["customer_id"].strip() == customer_name)

    def caculate_sin_df_amount(self, sin_df, amount, id_name_div):
        """
        计算金额并比较
        """
        amount_match = False
        comments = (
            "Historical Data>Remitter Account No & Aging 1V Multiple amount match"
        )
        if len(sin_df) == 1:
            sin_amount = sin_df.iloc[0]["amount"]
            if abs(Decimal(str(amount)) - Decimal(str(sin_amount))) <= Decimal(
                str(self.tole)
            ):
                comments = "Historical Data>Customer name & Aging 1V1 amount match"
                amount_match = True
        elif len(sin_df) > 1:
            for ind, s_row in sin_df.iterrows():
                sin_ramount = s_row["amount"]
                if abs(Decimal(str(amount)) - Decimal(str(sin_ramount))) <= Decimal(
                        str(self.tole)
                    ):
                    comments = "Historical Data>Customer name & Aging 1V1 amount match"
                    amount_match = True
                    break
            if not amount_match:
                comments, amount_match = self.sum_amount(
                    df=sin_df, amount_sum=amount, id_name_div=id_name_div
                )

        return comments, amount_match

    def sum_amount(self, df, amount_sum, id_name_div):
        """
        计算判断合计
        """
        total = Decimal(str(0)) 
        amount_match = False
        comments = f"Historical Data>{id_name_div} & Aging no find invoice"
        for idx, row in df.iterrows():
            total = Decimal(str(total)) + Decimal(str(row["amount"]))
            # if total == amount_sum
            if abs(Decimal(str(total)) - Decimal(str(amount_sum))) <= Decimal(
                        str(self.tole)
                    ):
                if idx == df.index[-1]:
                    comments = (
                        f"Historical Data>{id_name_div} & Aging all invoice match"
                    )
                else:
                    comments = f"Historical Data>{id_name_div} & Aging 1V Multiple amount match"
                amount_match = True
                return comments, amount_match
            elif total > amount_sum:
                return comments, amount_match
        return comments, amount_match

    def set_cls_define_data(self, region):
        """
        取得本地区的常量定义数据
        设定到类变量
        """
        self.def_data = self.comm_util.get_aloc_data_define(region=region)
        self.def_data.set_index("def_name", inplace=True)
        self.tole = self.comm_util.get_def_data_by_name(self.def_data, "tole")

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
        src_df.loc[ind_s, rule_item.result_field] = self.remove_duplicates(result_cid)
        if result_set_flg:
            ipf_sts= self.MULTI_MATCHED
            if single_bool:
                # ipf_sts= self.SINGLE_MATCHED
                ipf_sts = self.set_confidence(rule_confidence=rule_item.confidence)
            src_df = self.set_match_result(
                src_df=src_df,
                ind_s=ind_s,
                post_text=rule_item.result_comment+ " cfd: " + rule_item.confidence,
                ipf_status=ipf_sts,
            )
        return src_df

    def match_by_fuzz(self,src_val,dest_df,field,rule,search_rule,multi=0):
        """
        fuzzy查询
        """
        rows=[]
        for idx,row in dest_df.iterrows():
            dest_val = row[field]
            dest_val = self.trim_sales_order(dest_val, field)
            # 连续汉字中存在空格时，会影响匹配
            if self.region=="CN":
                dest_val = re.sub(" ", "", dest_val)

            extract_val, dest_val = self.trim_search_value(
                src_val=src_val, dest_val=dest_val, rule=rule
            )
            f_bool, f_radio = self.fuzzy_match(
                    extract_val, dest_val, search_rule
            )
            if f_bool:
                rows.append(row)
                # return f_bool,row.to_frame().T
        if len(rows)>0:
            return True,pd.concat([pd.DataFrame(rows)]).reset_index( drop=True)
        else:
            return False,None