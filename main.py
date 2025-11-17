'''
启动入口
'''
from load_common import LoadAction
from utils.logger import BpodLogger
from post_common import PostAction
# from move_file_common import MoveFileAction
from allocate_common import AllocateAction
from allocate_cn import ChinaAllocateAction
from allocate_run import AllocateFactory
from output_common import OutputFileAction
from post_india import PostActionIndia
from load_control import LoadControl
from excute_common import ExecuteAction
from watch_pipeline import PipelineMonitor

import json
from datetime import datetime, timedelta
from utils.file_util import FileUtil

    # 在主应用中使用
from scheduler.scheduler import create_scheduler_api
from fastapi import FastAPI


if __name__ == "__main__":

    log_instance = BpodLogger()

    # file_util = FileUtil(state = None, logger=log_instance)
    # result = file_util.download_sftp_to_cos(region='CN', user_type='ifp')

    # # ret = loac_ctrl.check_file_can_load("MY MBB","MY")
    # # print(ret)

    # monitor = PipelineMonitor('pipeline_monitor', log_instance)

    # # 传入pipeline运行信息
    # prun = {
    #     'pipeline_uuid': 'bopd_ifp_agingload_alloc',
    #     'variables': json.dumps({'region': 'MY'}),
    #     'completed_at': datetime.now()
    # }

    # # monitor.process_pipeline(prun)

    # # monitor = PipelineMonitor('MyPipelineMonitor', logger)
    # # prun = {
    # #     'pipeline_uuid': 'bopd_ifp_agingload_alloc',
    # #     'variables': '{"region": "MY", "action_user": "wuqyue@cn.ibm.com"}',
    # #     'completed_at': '2024-11-21T13:15:17.151Z',
    # #     'execution_date': '2024-11-21T09:15:17.000Z'
    # # }
    # # result = monitor.monitor_pipeline(prun)


    # 输出文件
    # output_action = OutputFileAction("",log_instance)
    # # output_action.output_alloc_data("NZ")
    # output_action.output_post_data("CN")

    # action = PostAction('Common post action', log_instance)

    # action.excute_region_posting('IN')

    # output_action.output_post_data('TW')

    # action.execute_posting('MY','MBB','MYR')
    # action.output_post_data('MY','M2U','MYR','2023-5-24')


    # my_action = RegionMyAction('malai','HSBC','MYR',log_instance)

    # method_name = 'search_aging'

    # method_to_call = getattr(my_action, method_name)

    # df = method_to_call()

    # df = my_action.search_aging()

    # print(df)
    # for vdf in df.values():
    #     print(vdf)

    # load_action = LoadAction('malai hsbc','Invoice Pool List','CN',log_instance)
    # load_action.read_file_to_table()

    # load_action = LoadAction('malai hsbc','VAT issue list','CN',log_instance)
    # load_action.read_file_to_table()

    # # MY_AR Aging | ASW650
    # MY

    load_action = LoadAction('Malaysia','','MY',log_instance)
    # # # load_action.read_region_all_file("batch user")

    
    load_action.read_pfile_to_table('MY','BANK BOA')

    # load_action.read_pfile_to_table('MY','Invoice weekly Report')
    # load_action.read_pfile_to_table('MY','MALAYSIA')
    load_action.read_pfile_to_table('MY','Aging')
    load_action.read_pfile_to_table('MY','ASW650')
    # load_action.read_pfile_to_table('MY','BANK HSBC')
    # load_action.read_pfile_to_table('MY','BANK MBB')
    # load_action.read_pfile_to_table('MY','BANK M2U')

        
    action = PostAction('Malaysia post action', log_instance)
    
    action.execute_posting('MY','BOA','MYR')

    # action.execute_posting('MY','HSBC','MYR')
    # action.execute_posting('MY','MBB','MYR')
    # action.execute_posting('MY','M2U','MYR')
    
    

    # # # 
    # load_action.read_pfile_to_table('SG','ASW650')
    # load_action.read_pfile_to_table('IN','ASW650')
    # load_action.read_pfile_to_table('CN','ASW650')
    # load_action.read_pfile_to_table('HK','ASW650')
    # load_action.read_pfile_to_table('TW','ASW650')
    # load_action.read_pfile_to_table('AU','ASW650')
    # load_action.read_pfile_to_table('NZ','ASW650')
    
    # load_action.read_pfile_to_table('MY','MALAYSIA')
    # load_action.read_pfile_to_table('MY','MY& SG daily tracker')
    

    # # Held Order
    # # load_action.read_pfile_to_table('MY','Held Order')
    # # load_action.read_pfile_to_table('MY','Released Order')
    


    # load_action = LoadAction('malai hsbc','MALAYSIA','MY',log_instance)
    # load_action.read_file_to_table()
    # load_action = LoadAction('malai hsbc','MY& SG daily tracker','MY',log_instance)
    # load_action.read_file_to_table()
    # load_action = LoadAction('malai hsbc','MY HSBC','MY',log_instance)
    # load_action.read_file_to_table()
    # load_action = LoadAction('malai hsbc','MY MBB','MY',log_instance)
    # load_action.read_file_to_table()
    # load_action = LoadAction('malai hsbc','MY M2U','MY',log_instance)
    # load_action.read_file_to_table()
    # # action.excute_region_posting('MY')
    # action.execute_posting('MY','M2U','MYR')
    # file_action = MoveFileAction('move file action', log_instance)
    # file_action.update_file_uploaded(region= 'MY',file_action_name='load_my_hsbc_raw',filename='MY HSBC')
    # load_action = LoadAction('malai hsbc','MY HSBC','MY',log_instance)
    # load_action.read_file_to_table()
    
    # SG
    
    load_action = LoadAction('Singapore','','SG',log_instance)
    # load_action.read_region_all_file(action_user="batch_system_test")

    # load_action.read_pfile_to_table('SG','Held Order')
    # load_action.read_pfile_to_table('SG','Released Order')

    # load_action.read_pfile_to_table('SG','Invoice weekly Report')

    # load_action.read_pfile_to_table('SG','Open Day')
    # load_action.read_pfile_to_table('SG','Rate Monthly')

    # load_action.read_file_to_table()

    # load_action.read_pfile_to_table('MY','MY& SG daily tracker')

    # load_action.read_pfile_to_table('SG','ASW650')
    # load_action.read_pfile_to_table('SG','Aging')

    # load_action.read_pfile_to_table('SG','BOA TRACKER')
    # # load_action.read_pfile_to_table('SG','SG whitelist')

    # # load_action.read_pfile_to_table('SG','SG Working')

    # load_action.read_pfile_to_table('SG','BANK BOA USD')
    # load_action.read_pfile_to_table('SG','BANK BOA SGD')
    # load_action.read_pfile_to_table('SG','BANK BOA KRW')
    # load_action.read_pfile_to_table('SG','BANK HSBC USD')
    # load_action.read_pfile_to_table('SG','BANK HSBC THB')
    # load_action.read_pfile_to_table('SG','BANK HSBC SGD')

    # action = PostAction('Common post action', log_instance)
    # action.excute_region_posting('SG')
    
    # action.execute_posting('SG','BOA','USD')
    # action.execute_posting('SG','BOA','SGD')
    # action.execute_posting('SG','BOA','KRW')
    # action.execute_posting('SG','HSBC','THB')
    # action.execute_posting('SG','HSBC','SGD')
    # action.execute_posting('SG','HSBC','USD')
    

    # load_action.read_pfile_to_table('SG','SGD HSBC')
    # load_action.read_pfile_to_table('SG','SGD HSBC')
    # load_action = LoadAction('Singapore','AGING','SG',log_instance)
    # load_action = LoadAction('Singapore','SGD HSBC','SG',log_instance)
    # load_action = LoadAction('Singapore','THB HSBC','SG',log_instance)
    # load_action = LoadAction('Singapore','USD HSBC','SG',log_instance)
    # load_action = LoadAction('Singapore','KRW BOA','SG',log_instance)
    # load_action = LoadAction('Singapore','SG Working','SG',log_instance)
    # load_action = LoadAction('Singapore','BOA TRACKER','SG',log_instance)
    # load_action = LoadAction('Singapore','SG whitelist','SG',log_instance)

    # # do Load  actions
    # load_action.read_file_to_table()
    # # # load_action.read_region_all_file()

    
    
    # AU

    # load_action = LoadAction('Australia','','AU',log_instance)
# 

    # load_action.read_pfile_to_table('AU','BANK BOA')

    # load_action.read_pfile_to_table('AU','Invoice weekly Report')

    # load_action.read_pfile_to_table('AU','ANZ Cash Application Tracker')
    
    # load_action.read_pfile_to_table('AU','BANK HSBC')
    # load_action.read_pfile_to_table('AU','Book2')
    # load_action.read_pfile_to_table('AU','AU Customer Master Data')
    # load_action.read_pfile_to_table('AU','ASW650')
    # load_action.read_pfile_to_table('AU','output_AU_')
    
    # # # # # # load_action = LoadAction('Australia','AU Customer Master Data','AU',log_instance)
    # # # # # # load_action.read_file_to_table()
    # # # # # # load_action = LoadAction('Australia','AU HSBC','AU',log_instance)
    # # # # # # load_action.read_pfile_to_table('AU','AU HSBC')
    # # # # # # # # # ANZ Order Release Daily Tracker
    # # # # # # # load_action.read_file_to_table()
    # # # # # # # # load_action.read_region_all_file()

    # action = PostAction('Common post action', log_instance)
    # action.execute_posting('AU','HSBC','AUD')

    # NZ

    # load_action = LoadAction('Australia','','NZ',log_instance)
    # load_action.read_pfile_to_table('NZ','Invoice weekly Report')
    
    # load_action.read_pfile_to_table('NZ','NZ HSBC')
    # load_action.read_pfile_to_table('NZ','NZ ASB')
    # load_action.read_pfile_to_table('NZ','Book3')
    # # load_action.read_pfile_to_table('NZ','NZ Customer Master Data')
    # load_action.read_pfile_to_table('NZ','Aging')
    # load_action.read_pfile_to_table('NZ','ASW650')
    # load_action.read_pfile_to_table('NZ','ANZ Cash Application Tracker')

    # # load_action.read_pfile_to_table('NZ','NZREC')
    
    # # # # load_action.read_pfile_to_table('NZ','ANZ FY23')
    # # # # # NZ HSBC   
    
    # action = PostAction('Common post action', log_instance)
    # action.execute_posting('NZ','HSBC','NZD')
    # action.execute_posting('NZ','BOA','NZD')

    # IN ===============

    # load_action = LoadAction('India','','IN',log_instance)
    # load_action.read_pfile_to_table('IN','BANK BOA','loaduser')

    # # # # # # # # load_action.read_region_all_file()
    # # load_action.read_pfile_to_table('IN','open item',action_user="batchuser")
    # # load_action.read_pfile_to_table('IN','ASW650')
    # # BANK BOA
    
    # # load_action.read_pfile_to_table('IN','History Tracker','ind load user')
    # # load_action.read_pfile_to_table('IN','Receivable')
    # # # # # # action = PostAction('Common post action', log_instance)

    # action = PostActionIndia('Common post action', log_instance)
    # action.execute_posting('IN','BOA','INR','postuser')

    # load_action.read_region_all_file()
    # load_action.read_pfile_to_table('IN','Aging',action_user="batch")
    # load_action.read_pfile_to_table('IN','ASW650')
    # load_action.read_pfile_to_table('IN','INR BOA New Account')
    # load_action.read_pfile_to_table('IN','History Tracker')
    # # load_action.read_pfile_to_table('IN','Receivable')



    # CN
    # load_action = LoadAction('PRC','','CN',log_instance)


    # # load_action.read_pfile_to_table('CN','Aging')
    
    # load_action.read_pfile_to_table('CN','BANK ALIPAY')
    # # load_action.read_pfile_to_table('CN','ADV-未解单')
    # # load_action.read_pfile_to_table('CN','ASW650')

    # load_action.read_pfile_to_table('CN','BANK CCB')
    # # load_action.read_pfile_to_table('CN','Sales code')
    # load_action.read_pfile_to_table('CN','BANK COD')
    # load_action.read_pfile_to_table('CN','Open Customer Back Orders')

    # load_action.read_pfile_to_table('CN','ADV-当天Release')
    # # Invoice Pool List

    # load_action.read_pfile_to_table('CN','Invoice Pool List')

    # load_action.read_pfile_to_table('CN','VAT issue list')
    # # # # # Sales code
    # # # load_action.read_pfile_to_table('CN','Sales code')

    # # # 

    # # # post
    # action = PostAction('Common post action', log_instance)

    # action.execute_posting('CN','CCB','CNY')

    # action.execute_posting('CN','Alipay','CNY')

    # HK

    # load_action = LoadAction('HongKong','','HK',log_instance)
    # # Hkaging
    
    # load_action.read_pfile_to_table('HK','overdue')
    # load_action.read_pfile_to_table('HK','Aging_Report')

    # # load_action.read_pfile_to_table('HK','ASW650')

    # load_action.read_pfile_to_table('HK','HKB HKD_USD Bank Details')

    # load_action.read_pfile_to_table('HK','BANK BOA')
    # load_action.read_pfile_to_table('HK','BANK HSBC HKD')

    # load_action.read_pfile_to_table('HK','Aging')
    # action = PostAction('Common post action', log_instance)

    # action.excute_region_posting('HK',action_user="webuser")
    # action.execute_posting('HK','HSBC','USD')
    


    # TW

    # load_action = LoadAction('TaiWan','','TW',log_instance)

    # load_action.read_pfile_to_table('TW','BANK HSBC USD')
    # load_action.read_pfile_to_table('TW','BANK HSBC TWD')
    
    # load_action.read_pfile_to_table('TW','TW TWD tracker')

    # load_action.read_pfile_to_table('TW','TW USD tracker')

    # load_action.read_region_all_file()

    # action = PostAction('Common post action', log_instance)

    # action.execute_posting('TW','HSBC','TWD')



    # load_action = LoadAction('PRC','','CN',log_instance)

    # load_action.read_pfile_to_table('CN','Open Customer Back Orders')

    # load_action.read_pfile_to_table('CN','COD')

    # load_action.read_pfile_to_table('CN','AR Outstanding')

    # load_action = LoadAction('Singapore','ASW650','SG',log_instance)
    # load_action.read_pfile_to_table('SG','ASW650')

    # Allocate

    # alloc_action = AllocateAction('XX',log_instance)

    # alloc_action.excute_region_allocate('HK')

    # alloc_action.excute_region_allocate('AU')

    # alloc_action.excute_region_allocate('NZ')

    # alloc_action.excute_region_allocate('SG')

    # alloc_action.excute_region_allocate('CN')

    # alloc_action.excute_region_allocate('MY')

    # alloc_action.excute_region_allocate('IN')

    # cn_alc= ChinaAllocateAction('CC',log_instance)
    # cn_alc.excute_region_allocate('CN')


    # alloc_factory = AllocateFactory()
    # alloc_factory.register("AllocateAction", AllocateAction)
    # alloc_factory.register("ChinaAllocateAction", ChinaAllocateAction)


    # # action = alloc_factory.allocate_get("ChinaAllocateAction", "ChinaAction", log_instance)
    # # action.excute_region_allocate('CN',action_user='batch')
    # action = alloc_factory.allocate_get("AllocateAction", "commonAction", log_instance)
    # action.excute_region_allocate('AU',action_user='batch')




    # eact = ExecuteAction(log_instance)
    # eact.exec_load_aging_allocate("MY","Aging","execuser")
    # app = FastAPI()
    # create_scheduler_api(app)




