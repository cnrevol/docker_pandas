"""
启动通用方法
"""

from load_common import LoadAction
from allocate_common import AllocateAction
from allocate_cn import ChinaAllocateAction
from allocate_run import AllocateFactory

class ExecuteAction:
    """
    启动通用方法
    """
    

    def  __init__(self,logger) -> None:
        self.logger = logger
        alloc_factory = AllocateFactory()
        alloc_factory.register("AllocateAction", AllocateAction)
        alloc_factory.register("ChinaAllocateAction", ChinaAllocateAction)
        # here could dynamic init action.
        self.alloc_action_cn = alloc_factory.allocate_get(
            "ChinaAllocateAction", "ChinaAction", self.logger
        )
        self.alloc_action = alloc_factory.allocate_get(
            "AllocateAction", "commonAction", self.logger
        )

        self.logger.info('Excute action flows .' )

    def exec_load_aging_allocate(self,region,file_prefix,action_user):
        """
        执行load aging数据文件
        执行allocate 处理
        """
        
        load_action = LoadAction('commonload','',region,self.logger)
        
        self.logger.debug(f"AgingLoadAllocate file load Start. region : {region}. file: {file_prefix}. user : {action_user}")
        # load 数据
        ret = load_action.read_pfile_to_table(region,file_prefix,action_user=action_user,kicker="aging")
        self.logger.info(f"AgingLoadAllocate file load Finish. region : {region}. file: {file_prefix}. user : {action_user}")
        # 执行 alocate
        if ret:
            self.excute_allocate_action(region, action_user)
            self.logger.info(f"AgingLoadAllocate allocate done. region : {region}. file: {file_prefix}.user : {action_user}")
        else:
            self.set_allocate_error(region,action_user,"no data loaded, Allocation skip.")
            self.logger.info(f"AgingLoadAllocate no aging data loaded, allocate skiped. region : {region}.file: {file_prefix}. user : {action_user}")

    

    def excute_allocate_action(self,region, action_user):
        """
        执行Allocate方法
        """
        if region == "CN":
            self.alloc_action_cn.excute_region_allocate(region, action_user)
        else:
            self.alloc_action.excute_region_allocate(region, action_user)

    def set_allocate_error(self,region,action_user,bl_msg="Allocation action Failed ."):
        """
        When error ,update status
        """
        self.alloc_action.set_allocate_error(region, action_user,bl_msg)