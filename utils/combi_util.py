from itertools import combinations
from decimal import Decimal
import random
from collections import defaultdict
import pandas as pd
from typing import List, Tuple, Dict

class OptimizedMatchingEngine:
    def __init__(self, tolerance=0.01, generate_group_func=None, logger=None):
        self.tolerance = Decimal(str(tolerance))
        # 配置常量
        self.DATA_EDGE_THRESHOLD = 30
        self.PAYMENT_COMBO_LIMIT = 2
        self.SMALL_DATA_UPPER_LIMIT = 2
        self.SMALL_DATA_LOWER_LIMIT = 8
        self.LARGE_DATA_UPPER_LIMIT = 0
        self.LARGE_DATA_LOWER_LIMIT = 2
        
        # 注入外部的 generate_group 方法
        self._generate_group_func = generate_group_func
        self.logger = logger
    
    def hold_combination_sums_smart(self, amount_ind_dic, sum_amount):
        """
        智能选择最优策略的主函数
        基于数据规模选择不同策略，并按 pay_date 优先级和金额绝对值进行排序
        """
        data_size = len(amount_ind_dic)
        target = Decimal(str(-sum_amount))
        tolerance = self.tolerance
        
        # 根据数据规模选择最优策略
        if data_size <= 20:
            # 小数据集：使用原始方法（轻微优化）
            return self._optimized_original_method(amount_ind_dic, sum_amount)
        elif data_size <= 100:
            # 中等数据集：使用启发式搜索
            return self._heuristic_search(amount_ind_dic, target, tolerance)
        else:
            # 大数据集：使用随机采样
            return self._random_sampling_search(amount_ind_dic, target, tolerance)

    def _optimized_original_method(self, amount_ind_dic, sum_amount):
        """
        轻微优化的原始方法：增加更多剪枝，按 pay_date 升序、金额绝对值升序优先
        返回格式：当匹配成功时，返回 [(cid, amount_diff)] 或 [ [(cid, amount_diff)], ... ]
        """
        target = Decimal(str(-sum_amount))
        tolerance = self.tolerance
        
        # 先按 pay_date 升序，再按金额绝对值升序
        items = sorted(
            amount_ind_dic.items(),
            key=lambda x: (
                (x[1]['pay_date'] if isinstance(x[1], dict) else pd.Timestamp.max),
                abs(x[1]['amount']) if isinstance(x[1], dict) else abs(x[1])
            )
        )
        items_count = len(items)
        max_combo_size = min(6, len(items))
        
        results = []

        for combo_size in range(1, max_combo_size + 1):
            for combo in combinations(items, combo_size):
                combo_sum = sum((v['amount'] if isinstance(v, dict) else v) for _, v in combo)
                
                # 早停条件：和已经太大
                if combo_sum > target + tolerance:
                    continue
                    
                if abs(combo_sum - target) <= tolerance:
                    amount_dif = abs(combo_sum - target)
                    return [(cid, amount_dif) for cid, _ in combo]
                    # if combo_size == 1:
                    #     if items_count == 1:
                    #         return [(cid, amount_dif) for cid, _ in combo]
                    #     results.append([(cid, amount_dif) for cid, _ in combo])
                    #     if len(results) > 1:
                    #         return results
                    # else:
                    #     return [(cid, amount_dif) for cid, _ in combo]
        
        return None

    def _heuristic_search(self, amount_ind_dic, target, tolerance):
        """
        启发式搜索：基于贪心 + 回溯
        优先选择 pay_date 更早，且金额接近目标的记录
        返回 [(cid, amount_diff)] 或 None
        """
        amounts = list(amount_ind_dic.items())
        amounts.sort(key=lambda x: (
            (x[1]['pay_date'] if isinstance(x[1], dict) else pd.Timestamp.max),
            abs((x[1]['amount'] if isinstance(x[1], dict) else x[1]) - target)
        ))
        
        def backtrack(index, current_sum, current_path, max_depth=6):
            if len(current_path) > max_depth:
                return None
            
            if abs(current_sum - target) <= tolerance:
                amount_dif = abs(current_sum - target)
                return [(cid, amount_dif) for cid in current_path]
            
            if index >= len(amounts) or current_sum > target + tolerance:
                return None
            
            remaining_positive = sum(
                max(0, (v['amount'] if isinstance(v, dict) else v))
                for _, v in amounts[index:]
            )
            if current_sum + remaining_positive < target - tolerance:
                return None
            
            # 选择当前金额
            item_id, value = amounts[index]
            amount = value['amount'] if isinstance(value, dict) else value
            result = backtrack(index + 1, current_sum + amount, current_path + [item_id], max_depth)
            if result:
                return result
            
            # 不选择当前金额
            return backtrack(index + 1, current_sum, current_path, max_depth)
        
        return backtrack(0, Decimal('0'), [])

    def _random_sampling_search(self, amount_ind_dic, target, tolerance, max_samples=10000, max_combination_size=8):
        """
        随机采样搜索：对大数据集进行随机采样
        返回 [(cid, amount_diff)] 或 None
        """
        amounts = list(amount_ind_dic.items())
        
        best_match = None
        best_diff = float('inf')
        
        for _ in range(max_samples):
            combo_size = random.randint(1, min(max_combination_size, len(amounts)))
            selected = random.sample(amounts, combo_size)
            combo_sum = sum((v['amount'] if isinstance(v, dict) else v) for _, v in selected)
            diff = abs(combo_sum - target)
            
            if diff <= tolerance:
                return [(cid, diff) for cid, _ in selected]
            
            if diff < best_diff:
                best_diff = diff
                best_match = selected
        
        if best_match and best_diff <= tolerance * 2:
            return [(cid, best_diff) for cid, _ in best_match]
        
        return None
        
    def preprocess_data_with_date_priority(self, df: pd.DataFrame, date_column: str = 'pay_date') -> pd.DataFrame:
        """
        预处理数据，按日期排序，优先处理古老数据
        
        Args:
            df: 输入数据框
            date_column: 日期列名
            
        Returns:
            按日期排序后的数据框
        """
        df_copy = df.copy()
        # 确保日期列是datetime类型
        df_copy[date_column] = pd.to_datetime(df_copy[date_column])
        # 按日期升序排序，古老数据在前
        df_copy = df_copy.sort_values(by=[date_column, 'customer_id'], ascending=[True, True])
        return df_copy.reset_index(drop=True)
    
    def group_data_by_customer(self, df: pd.DataFrame) -> Dict:
        """
        按客户ID分组数据，提高查找效率
        
        Args:
            df: 输入数据框
            
        Returns:
            按customer_id分组的字典
        """
        customer_groups = defaultdict(lambda: {'amounts': [], 'indices': []})
        
        for idx, row in df.iterrows():
            cid = row['customer_id']
            amounts = row['amount'] if isinstance(row['amount'], list) else [row['amount']]
            indices = row['Indices'] if isinstance(row['Indices'], list) else [row['Indices']]
            
            customer_groups[cid]['amounts'].extend(amounts)
            customer_groups[cid]['indices'].extend(indices)
            
        return customer_groups
    
    def generate_combinations_with_cache(self, amounts: List, indices: List, 
                                       combo_limits: Tuple[int, int]) -> List[Tuple]:
        """
        生成组合并缓存结果
        
        Args:
            amounts: 金额列表
            indices: 索引列表
            combo_limits: (下限, 上限) 或 None表示使用默认逻辑
            
        Returns:
            组合列表 [(sum, indices), ...]
        """
        combos = []
        upper_limit, lower_limit = combo_limits
        
        for r in range(1, len(amounts) + 1):
            # 优化组合生成逻辑
            if r <= lower_limit or (upper_limit > 0 and upper_limit > len(amounts) - r):
                combos.extend([
                    (
                        sum([amounts[i] for i in combo]),
                        [indices[i] for i in combo]
                    )
                    for combo in combinations(range(len(amounts)), r)
                ])
                
        return combos
    
    def find_matching_combinations(self, src_amounts: List, src_indices: List,
                                 dst_amounts: List, dst_indices: List,
                                 customer_id: int) -> List[Tuple]:
        """
        查找匹配的组合
        
        Args:
            src_amounts: 源金额列表
            src_indices: 源索引列表
            dst_amounts: 目标金额列表
            dst_indices: 目标索引列表
            customer_id: 客户ID
            
        Returns:
            匹配结果列表
        """
        # 确定组合限制
        if len(dst_amounts) < self.DATA_EDGE_THRESHOLD:
            dst_limits = (self.SMALL_DATA_UPPER_LIMIT, self.SMALL_DATA_LOWER_LIMIT)
        else:
            dst_limits = (self.LARGE_DATA_UPPER_LIMIT, self.LARGE_DATA_LOWER_LIMIT)
            
        src_limits = (0, self.PAYMENT_COMBO_LIMIT)
        
        # 生成组合
        src_combos = self.generate_combinations_with_cache(src_amounts, src_indices, src_limits)
        dst_combos = self.generate_combinations_with_cache(dst_amounts, dst_indices, dst_limits)
        
        # 查找匹配
        matches = []
        for src_sum, src_idx in src_combos:
            for dst_sum, dst_idx in dst_combos:
                amount_diff = abs(Decimal(str(src_sum)) + Decimal(str(dst_sum)))
                if amount_diff <= self.tolerance:
                    group_id = self.generate_group()
                    matches.append((
                        customer_id,
                        src_sum,
                        src_idx,
                        dst_sum,
                        dst_idx,
                        amount_diff,
                        group_id
                    ))
                    # 移除break，允许找到多个匹配
                    
        return matches
    
    def find_equal_combinations(self, src_df, dst_df):
        """
        优化后的主匹配方法 - 保持原接口不变
        
        Args:
            src_df: 源数据框，包含 customer_id, amount, Indices 列
            dst_df: 目标数据框，包含 customer_id, amount, Indices 列
            
        Returns:
            equal_combinations: 匹配结果列表，格式与原方法相同
        """
        equal_combinations = []
        loop_cnt = 0
        pay_range = self.PAYMENT_COMBO_LIMIT
        data_edge = self.DATA_EDGE_THRESHOLD
        
        # 1. 预处理：如果数据中有日期列，按日期排序（优先处理古老数据）
        src_df_processed = self._sort_by_date_if_exists(src_df)
        dst_df_processed = self._sort_by_date_if_exists(dst_df)
        
        # 2. 按客户分组优化查找
        dst_customer_dict = self._create_customer_lookup(dst_df_processed)
        
        # 3. 遍历源数据
        for cid1, amounts1, indices1 in src_df_processed[
            ["customer_id", "amount", "Indices"]
        ].values:
            loop_cnt += 1
            
            if len(amounts1) < data_edge:
                # 只查找匹配的客户，避免全遍历
                if cid1 in dst_customer_dict:
                    for amounts2, indices2 in dst_customer_dict[cid1]:
                        # 动态设置组合范围
                        if len(amounts2) < data_edge:
                            up_rg = self.SMALL_DATA_UPPER_LIMIT
                            low_rg = self.SMALL_DATA_LOWER_LIMIT
                        else:
                            up_rg = self.LARGE_DATA_UPPER_LIMIT
                            low_rg = self.LARGE_DATA_LOWER_LIMIT
                        
                        # 调用优化后的计算方法
                        equal_combinations = self.caculate_combinations(
                            equal_combinations,
                            up_rg,
                            low_rg,
                            pay_range,
                            cid1,
                            amounts1,
                            indices1,
                            amounts2,
                            indices2,
                        )
        
        return equal_combinations

    def caculate_combinations(
        self,
        equal_combinations,
        up_rg,
        low_rg,
        pay_range,
        cid1,
        amounts1,
        indices1,
        amounts2,
        indices2,
    ):
        """
        Calculate combinations of amounts for a given customer ID.
        与 allocate_common.caculate_combinations 兼容，但使用引擎的容差与分组生成。
        """
        combos1 = []
        for r in range(1, len(amounts1) + 1):
            if r <= pay_range:
                combos1.extend(
                    [
                        (
                            sum([amounts1[i] for i in combo]),
                            [indices1[i] for i in combo],
                        )
                        for combo in combinations(range(len(amounts1)), r)
                    ]
                )
        combos2 = []
        for r in range(1, len(amounts2) + 1):
            if r <= low_rg or up_rg > len(amounts2) - r:
                combos2.extend(
                    [
                        (
                            sum([amounts2[i] for i in combo]),
                            [indices2[i] for i in combo],
                        )
                        for combo in combinations(range(len(amounts2)), r)
                    ]
                )
        for combo1, indices1_sel in combos1:
            for combo2, indices2_sel in combos2:
                if abs(Decimal(str(combo1)) + Decimal(str(combo2))) <= self.tolerance:
                    group_id = self.generate_group()
                    amount_diff = abs(Decimal(str(combo1)) + Decimal(str(combo2)))
                    equal_combinations.append(
                        (
                            cid1,
                            combo1,
                            indices1_sel,
                            combo2,
                            indices2_sel,
                            amount_diff,
                            group_id,
                        )
                    )
                    break
        return equal_combinations
    
    def _sort_by_date_if_exists(self, df):
        """
        如果数据中存在日期列，按日期排序，优先处理古老数据
        """
        df_copy = df.copy()
        
        # 检查是否有常见的日期列
        date_columns = ['pay_date', 'date', 'transaction_date', 'create_date']
        date_col = None
        
        for col in date_columns:
            if col in df_copy.columns:
                date_col = col
                break
        
        if date_col:
            try:
                df_copy[date_col] = pd.to_datetime(df_copy[date_col])
                # 按日期升序排序，古老数据在前，然后按customer_id排序
                df_copy = df_copy.sort_values(by=[date_col, 'customer_id'], ascending=[True, True])
                df_copy = df_copy.reset_index(drop=True)
            except Exception:
                # 如果日期转换失败，使用原数据
                pass
                
        return df_copy
    
    def _create_customer_lookup(self, df):
        """
        创建客户查找字典，提高查找效率
        """
        customer_dict = defaultdict(list)
        
        for _, row in df.iterrows():
            cid = row['customer_id']
            amounts = row['amount']
            indices = row['Indices']
            customer_dict[cid].append((amounts, indices))
            
        return customer_dict
    
    def generate_group(self):
        """
        调用外部注入的 generate_group 方法
        如果没有注入，使用默认实现
        """
        if self._generate_group_func:
            return self._generate_group_func()
        else:
            # 默认实现，避免没有注入方法时出错
            import uuid
            return str(uuid.uuid4())[:8]


# 使用示例
def example_usage():
    """使用示例 - 展示如何注入外部方法"""
    
    # 定义外部的 generate_group 方法
    def external_generate_group():
        """
        分组编号初始化
        """
        # 使用局部静态变量模拟递增
        if not hasattr(external_generate_group, "_last_number"):
            external_generate_group._last_number = 100000
        external_generate_group._last_number += 1
        external_generate_group._last_number %= 1000000
        return str(external_generate_group._last_number)
    
    # 创建匹配引擎时注入方法
    engine = OptimizedMatchingEngine(tolerance=0.01, generate_group_func=external_generate_group)
    
    # 模拟数据
    src_data = pd.DataFrame({
        'customer_id': [1, 1, 2],
        'amount': [[100.0, 200.0], [300.0], [150.0]],
        'Indices': [[0, 1], [2], [3]],
        'pay_date': ['2020-01-01', '2021-01-01', '2019-01-01']
    })
    
    dst_data = pd.DataFrame({
        'customer_id': [1, 2, 2],
        'amount': [[-100.0], [-150.0], [-50.0, -100.0]],
        'Indices': [[10], [11], [12, 13]],
        'pay_date': ['2020-01-01', '2019-01-01', '2021-01-01']
    })
    
    # 执行匹配
    results = engine.find_equal_combinations(src_data, dst_data)
    
    # 打印结果
    for result in results:
        print(f"客户: {result[0]}, 源金额: {result[1]}, 目标金额: {result[3]}, "
              f"差额: {result[5]}, 组ID: {result[6]}")

if __name__ == "__main__":
    # 为示例中的 external_generate_group 提供初始值，避免 linter 报错
    last_number = 100000
    example_usage()