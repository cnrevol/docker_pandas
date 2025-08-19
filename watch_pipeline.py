import json
from datetime import datetime, timedelta
from typing import Dict, Any

from utils.db_util import Database
from utils.file_util import FileUtil
from utils.comm_util import CommUtil

class PipelineMonitor:
    """
    Pipeline monitor
    """
    front_eg = 35
    end_eg = 10
    ACT_FREE = "un_lock"


    def __init__(self, name: str, logger=None) -> None:
        self.name = name
        self.logger = logger
        self.db = Database(logger=logger)
        self.file_util = FileUtil(logger=logger)
        self.comm_util = CommUtil(logger=logger)

    def parse_pipeline_variables(self, variables) -> Dict[str, str]:
        """
        解析 pipeline 的变量

        :param variables: pipeline 运行信息，可能是 JSON 字符串或字典
        :return: 解析后的变量字典
        """
        try:
            # 如果是字典，直接使用；如果是字符串，解析成字典
            if isinstance(variables, dict):
                parsed_variables = variables
            elif isinstance(variables, str):
                parsed_variables = json.loads(variables)
            else:
                raise ValueError(f"Unsupported type for variables: {type(variables)}")

            # 提取需要的字段
            return {
                'region': parsed_variables.get('region', '').upper(),
                'action_user': parsed_variables.get('action_user', ''),
                'execution_partition': parsed_variables.get('execution_partition', '')
            }

        except (json.JSONDecodeError, ValueError) as e:
            if self.logger:
                self.logger.error(f"Parse parameter failed: {variables}. Error: {e}")
            return {}


    def get_timeout_action_names(self, pipeline_uuid: str, region: str) -> list:
        """
        根据pipeline和region获取需要检查超时的action names
        
        :param pipeline_uuid: pipeline名称
        :param region: 区域
        :return: action names列表
        """
        pipeline_action_map = {
            'bopd_ifp_agingload_alloc': [
                f'load_{region.lower()}_aloc_araging_raw',
                f'{region}_Allocation'
            ],
            'bpod_ifp_post_match_all_trigger': self._get_post_match_actions(region),
            'bpod_ifp_post_match_' + region.lower(): self._get_post_match_actions(region),
            'bpod_ifp_all_load_post': self._get_load_actions(region)
        }
        
        self.logger.debug(f"Got action name finished. {pipeline_uuid}")
        return pipeline_action_map.get(pipeline_uuid, [])

    def _get_post_match_actions(self, region: str) -> list:
        """
        获取特定区域的post操作action names
        
        :param region: 区域
        :return: action names列表
        """
        post_actions = {
            'MY': ['MY_HSBC_MYR_post', 'MY_MBB_MYR_post', 'MY_M2U_MYR_post'],
            'SG': ['SG_HSBC_SGD_post', 'SG_HSBC_THB_post', 'SG_HSBC_USD_post', 'SG_BOA_KRW_post'],
            'AU': ['AU_HSBC_AUD_post'],
            'NZ': ['NZ_HSBC_NZD_post', 'NZ_BOA_NZD_post'],
            'IN': ['IN_BOA_INR_post'],
            'CN': ['CN_CCB_CNY_post', 'CN_Alipay_CNY_post', 'CN_COD_CNY_post'],
            'HK': ['HK_HSBC_USD_post', 'HK_HSBC_HKD_post'],
            'TW': ['TW_HSBC_USD_post', 'TW_HSBC_TWD_post']
        }
        
        return post_actions.get(region, [])

    def _get_load_actions(self, region:str) -> list:
        """
        获取 DB中定义的 load action names

        :param region: 区域
        :return: action names列表

        """
        # 通过调用方法获取硬编码的actions
        hardcoded_actions = self._get_post_match_actions(region)

        # 构建SQL查询
        sql_query = "SELECT DISTINCT file_action_name FROM sc_raw_file_define WHERE is_post_file='1' AND otc_region = %s"
        
        try:
            # 执行数据库查询并获取结果
            load_actions = self.db.execute_query_to_pandas(sql_query, (region,))
            
            # 从查询结果中提取file_action_name列表
            db_actions = load_actions['file_action_name'].tolist() if not load_actions.empty else []
            
            # 合并并去重
            combined_actions = list(set(hardcoded_actions + db_actions))
            
            return combined_actions
        
        except Exception as e:
            # 如果数据库查询出错，返回硬编码的actions
            self.logger.error(f"Database query error for region {region}: {e}")
            return hardcoded_actions

    def check_and_update_timeout(self, prun: Dict[str, Any]) -> bool:
        """
        检查并更新pipeline的超时状态
        
        :param prun: pipeline运行信息字典
        :return: 是否有超时记录被更新
        """
        # 解析pipeline变量
        parsed_vars = self.parse_pipeline_variables(prun['variables'])
        region = parsed_vars.get('region')
        
        if not region:
            if self.logger:
                self.logger.warning(f"Can not get Region from pipeline {prun['pipeline_uuid']}")
            return False
        
        # 获取需要检查的action names
        action_names = self.get_timeout_action_names(prun['pipeline_uuid'], region)
        
        if not action_names:
            self.logger.debug(f"There is no action name be selected. on region: {region}")
            return False
        
        # 准备更新超时状态的SQL
        update_sql = """
        UPDATE sc_action_status 
        SET 
            bl_status = 'timeout', 
            update_date = %s, 
            update_time = %s, 
            action_user = 'pipe_watcher',
            bl_message = 'Monitor the pipeline for mageai execution timeout.'
        WHERE 
            action_name = %s AND 
            update_time BETWEEN %s AND %s AND 
            bl_status LIKE %s
        """
        
        # 获取系统当前时间 .strftime('%Y%m%d')
        current_time = datetime.now()
        current_date = current_time
        
        # 完成时间前后10分钟范围
        ctime = prun['completed_at']
        if prun['completed_at'] is None:
            ctime = prun['execution_date']
        # .replace('Z', '+00:00') datetime.fromisoformat(ctime)
        completed_at = ctime

        time_range_start = completed_at - timedelta(minutes=self.front_eg)
        time_range_end = completed_at + timedelta(minutes=self.end_eg)
        
        # 执行更新
        updated = False
        for action_name in action_names:
            parameters = [current_date, current_time, action_name, time_range_start, time_range_end,'%ing%']
            result = self.db.execute_update_query(update_sql, parameters)
            
            if (result is not None) and (result > 0):
                updated = True
                if self.logger:
                    self.logger.info(f"Update timeout status on action_name={action_name}")
        # 更新lock表，解锁。
        if updated:
            self.update_act_div(region,prun['pipeline_uuid'],'pipe_batchwatcher')
            
        
        self.logger.info(f"Check timeout finished")
        return updated

    def get_div_action_name(self, pipeline_uuid: str, region: str) -> str:
        """
        根据pipeline和region获取需要检查超时的action names
        
        :param pipeline_uuid: pipeline名称
        :param region: 区域
        :return: action names列表
        """
        pipeline_action_map = {
            'bopd_ifp_agingload_alloc': 
                f'{region.upper()}_AlocAction'
            ,
            'bpod_ifp_post_match_all_trigger': 
                f'{region.upper()}_PostAction'
            ,
            'bpod_ifp_post_match_' + region.lower(): 
                f'{region.upper()}_PostAction'
            ,
            'bpod_ifp_all_load_post': 
                f'{region.upper()}_PostAction'
            
        }
        
        return pipeline_action_map.get(pipeline_uuid, [])
    
    def update_act_div(self,region,pipeline_uuid,user):
        """
        更新 sc_action_divsion
        """
        act_name = self.get_div_action_name(pipeline_uuid,region)
        self.comm_util.unlock_action(region=region,action_name=act_name,ac_status=self.ACT_FREE,ac_user=user)
        self.logger.info(f"unlock divsion action_name={act_name}")

    def monitor_pipeline(self, prun: Dict[str, Any]) -> bool:
        """
        监控pipeline并处理超时
        
        :param prun: pipeline运行信息字典
        :return: 是否成功处理
        """
        # try:
        if not prun:
            if self.logger:
                self.logger.info("There is no pipeline cancel information.")
            return False
        # self.logger.info(f"check pipeline start.{prun}")
        self.logger.info(f"check pipeline params: {prun['pipeline_uuid']},{prun['completed_at']},{prun['variables']},{prun['execution_date']},{prun['status']},{prun['pipeline_schedule_id']}")
        
        # 检查并更新超时状态
        return self.check_and_update_timeout(prun)
        
        # except Exception as e:
        #     if self.logger:
        #         self.logger.error(f"Pipeline Python Monitor exception : {str(e)}")
        #     return False