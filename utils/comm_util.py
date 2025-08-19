"""
通用工具
"""

from datetime import datetime, timedelta
from .db_util import Database

from exceptions import ConcurrencyException


class CommUtil:
    """
    通用日志管理
    程序动作更新到数据表
    """

    BL_STS = {
        "0": "file_uploading",  # form ftp to magefolder , front end upload to magefolder.
        "1": "to_load",  # file_ready copy done
        "2": "loading",
        "3": "load_done",
        "4": "matching",
        "5": "match_done",
        "6": "fileposting",
        "7": "filepost_done",
        "8": "file_upload_error",
        "9": "data_load_error",
        "10": "match_error",
        "11": "file_post_error",
        "12": "allocating",
        "13": "allocation_done",
        "14": "allocation_error",
        "15": "collect_done",
        "16": "allocation_file_outputing",
        "17": "allocation_file_output_done",
        "18": "collect_doing",
        "19": "waiting",
        "20": "allocation_file_output_error",
        "21": "match_skip",
        "22": "page_loading",
        "23": "page_matching",
        "24": "page_fileposting",
        "25": "page_allocating",
        "26": "timeout",
    }

    def __init__(self, logger=None):
        self.logger = logger
        self.db = Database(logger=logger)

    def get_daytime_string(self, days=0):
        """
        # 获取当前日期和时间
        """
        today = datetime.now()

        # 计算昨天的日期
        yesterday = today - timedelta(days=days)

        # 将日期格式化为 'YYYY-MM-DD' 形式的字符串
        formatted_date = yesterday.strftime("%Y-%m-%d")

        return formatted_date

    def update_doing_status(
        self,
        rdf,
        done_status,
        region,
        action_name,
        step_level,
        business_date,
        status,
        bl_message,
        ac_user,
    ):
        """
        更新状态表状态记录
        更新为 doing 执行中 状态

        """
        # 如果存在 更新处理
        if not rdf.empty:
            # 如果更新的状态与DB现存状态不同，则更新
            db_status = rdf.loc[0, "bl_status"]
            # 已存在记录时done，则 seq+1 增加一条记录
            if (
                db_status == done_status
                or db_status == self.BL_STS["3"]
                or db_status == self.BL_STS["9"]
                or db_status == self.BL_STS["10"]
                or db_status == self.BL_STS["11"]
                or db_status == self.BL_STS["14"]
                or db_status == self.BL_STS["17"]
                or db_status == self.BL_STS["26"]
            ):
                seq = rdf.loc[0, "action_seq"]
                a_seq = int(seq) + 1
                self.insert_action_status(
                    region=region,
                    action_seq=a_seq,
                    action_name=action_name,
                    step_level=step_level,
                    parent_step=0,
                    action_description="",
                    business_date=business_date,
                    status=status,
                    bl_message=bl_message,
                    ac_user=ac_user,
                )
           
            # 页面触发的doing状态时，更新到后端doing状态
            elif ((db_status == self.BL_STS["1"]) or (db_status == self.BL_STS["22"]) or
             (db_status == self.BL_STS["23"]) or (db_status == self.BL_STS["24"])
             or (db_status == self.BL_STS["25"])):
                # 保留seq，仅更新状态 status
                seq = int(rdf.loc[0, "action_seq"])
                # 从上传文件 到 load文件 的层级
                 # 文件上传完成状态  更新至  文件loading to DB
                if (db_status == self.BL_STS["1"]):
                    step_level = 1

                self.update_action_status(
                    region=region,
                    action_name=action_name,
                    business_date=business_date,
                    status=status,
                    bl_message=bl_message,
                    action_seq=seq,
                    step_level=step_level,
                    ac_user=ac_user,
                )
            # 已存在记录是 Allocate match doing ，跳过不处理
            elif (db_status == self.BL_STS['12']
                  or db_status == self.BL_STS['4'] or db_status == self.BL_STS['2']) :
                raise ConcurrencyException(f" This action is on precessing . Region : {region}, Action: {action_name}, Status: {db_status}")

        # 如果不存在 insert doing record
        else:
            self.insert_action_status(
                region=region,
                action_seq=0,
                action_name=action_name,
                step_level=step_level,
                parent_step=0,
                action_description="",
                business_date=business_date,
                status=status,
                bl_message=bl_message,
                ac_user=ac_user,
            )

    def update_done_status(
        self, rdf, doing_status, region, action_name, business_date, status, bl_message, ac_user
    ):
        """
        更新状态表状态记录
        更新为 done 完成 状态

        """
        # 如果存在 更新处理
        if not rdf.empty:
            # 如果更新的状态与DB现存状态不同，则更新
            db_status = rdf.loc[0, "bl_status"]
            action_seq = int(rdf.loc[0, "action_seq"])
            step_level = int(rdf.loc[0, "step_level"])
            # 已存在doing记录时,更新为done
            if (db_status == doing_status) or ((doing_status in db_status) and ("ing" in doing_status)):
                self.update_action_status(
                    region=region,
                    action_name=action_name,
                    business_date=business_date,
                    status=status,
                    bl_message=bl_message,
                    action_seq=action_seq,
                    step_level=step_level,
                    ac_user=ac_user,
                )


    def update_file_uploading_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        文件准备动作状态
        1. 前端页面文件上传
        2. 云端文件移动copy
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )

        self.update_doing_status(
            rdf,
            done_status=self.BL_STS["1"],
            region=region,
            action_name=action_name,
            step_level=0,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def update_file_uploaded_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        文件准备动作状态
        1. 前端页面文件上传
        2. 云端文件移动copy
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_done_status(
            rdf=rdf,
            region=region,
            doing_status=self.BL_STS["0"],
            action_name=action_name,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def update_loading_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        读文件到数据表状态设定 doing
        执行状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )

        self.update_doing_status(
            rdf,
            done_status=self.BL_STS["3"],
            region=region,
            action_name=action_name,
            step_level=1,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )
        

    def update_loaded_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        读文件到数据表状态设定 done
        完成状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_done_status(
            rdf=rdf,
            region=region,
            doing_status=self.BL_STS["2"],
            action_name=action_name,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def update_posting_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        数据Match Action 状态设定 doing
        执行状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_doing_status(
            rdf,
            done_status=self.BL_STS["5"],
            region=region,
            action_name=action_name,
            step_level=2,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def update_posted_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        数据Match Action 状态设定 done
        完成状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_done_status(
            rdf=rdf,
            doing_status=self.BL_STS["4"],
            region=region,
            action_name=action_name,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def update_file_outputing_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        Post 文件生成 Action 状态设定 doing
        执行状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_doing_status(
            rdf,
            done_status=self.BL_STS["7"],
            region=region,
            action_name=action_name,
            step_level=3,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def update_file_outputed_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        Post 文件生成 Action 状态设定 done
        完成状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_done_status(
            rdf=rdf,
            doing_status=self.BL_STS["6"],
            region=region,
            action_name=action_name,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def update_allocating_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        数据Allocate Action 状态设定 doing
        执行状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_doing_status(
            rdf,
            done_status=self.BL_STS["13"],
            region=region,
            action_name=action_name,
            step_level=4,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )
        self.logger.debug(f"action status update: {region} ,{action_name} , {status} , {ac_user} ")

    def update_allocated_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        数据Allocate Action 状态设定 done
        完成状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_done_status(
            rdf=rdf,
            doing_status=self.BL_STS["12"],
            region=region,
            action_name=action_name,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def update_alocfile_outputing_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        Post 文件生成 Action 状态设定 doing
        执行状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_doing_status(
            rdf,
            done_status=self.BL_STS["17"],
            region=region,
            action_name=action_name,
            step_level=5,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def update_alocfile_outputed_status(
        self, region, action_name, business_date, status, bl_message, ac_user="system"
    ):
        """
        Post 文件生成 Action 状态设定 done
        完成状态
        """
        rdf = self.get_action(
            region=region, action_name=action_name, business_date=business_date
        )
        self.update_done_status(
            rdf=rdf,
            doing_status=self.BL_STS["16"],
            region=region,
            action_name=action_name,
            business_date=business_date,
            status=status,
            bl_message=bl_message,
            ac_user=ac_user,
        )

    def check_data_load(self,region,status):
        """
        检查load to DB 是否全部处理成功
        """
        sql_query = """SELECT a.action_name, a.bl_status, a.bl_message, a.update_date, a.parent_step,a.update_time
                FROM sc_action_status a
                INNER JOIN (
                    SELECT action_name, MAX(update_time) as max_update_date
                    FROM sc_action_status
                    WHERE action_name IN (
                        SELECT file_action_name 
                        FROM sc_raw_file_define 
                        WHERE otc_region = %s and is_post_file='1'
                    )
                    GROUP BY action_name
                ) b ON a.action_name = b.action_name AND a.update_time = b.max_update_date AND a.update_date=CURRENT_DATE
                
                """
        if status =='done':
            sql_query = sql_query + " and (a.bl_status like %s) "
            sts_pattern="%done%"
            parameters = (
                region,
                sts_pattern,
            )
        elif status =='error':
            sql_query = sql_query + " and (a.bl_status like %s or a.bl_status like %s) "
            sts_pattern="%error%"
            sts_pattern2="%ing%"
            parameters = (
                region,
                sts_pattern,
                sts_pattern2,
            )

        return self.db.execute_query_col_name(sql_query, parameters)
        

    def check_data_load_err(self,region):
        """
        错误状态
        """
        rdf = self.check_data_load(region=region,status="error")
        if rdf.empty:
            return False
        return True

    def check_data_load_done(self,region):
        """
        完成状态
        """
        rdf = self.check_data_load(region=region,status="done")
        if rdf.empty:
            return False
        return True

    def update_action_status(
        self,
        region,
        action_name,
        business_date,
        status,
        bl_message,
        action_seq,
        step_level,
        ac_user
    ):
        """
        更新Action状态

        """
        sql_query = """ update sc_action_status 
            set bl_status= %s ,step_level = %s, 
            bl_message = %s, update_time = CURRENT_TIMESTAMP, action_user =%s 
            WHERE otc_region = %s and action_name = %s and 
                update_date = %s and action_seq = %s ; """
        # parameters = ("MY HSBC","MY",)
        parameters = (
            status,
            step_level,
            bl_message,
            ac_user,
            region,
            action_name,
            business_date,
            action_seq,
        )

        self.db.execute_update_query(sql_query, parameters)

    def get_action(self, region, action_name, business_date):
        """
        根据Aciton名，查询状态数据记录

        """
        sql_query = """ SELECT * FROM sc_action_status 
                WHERE otc_region = %s 
                and action_name = %s 
                and update_date = %s 
                order by action_seq desc; """
        # parameters = ("MY HSBC","MY",)
        parameters = (
            region,
            action_name,
            business_date,
        )

        rdf = self.db.execute_query_col_name(sql_query, parameters)

        # if not rdf.empty:
        return rdf
        # bl_status = rdf.loc[0, 'bl_status']

    def insert_action_status(
        self,
        region,
        action_seq,
        action_name,
        step_level,
        parent_step,
        action_description,
        business_date,
        status,
        bl_message,
        ac_user,
    ):
        """
        添加记录到
        状态表sc_action_status

        """
        sql_query = """
                    INSERT 
            INTO sc_action_status( 
                otc_region
                , action_seq
                , action_name
                , step_level
                , parent_step
                , action_description
                , update_date
                , bl_status
                , bl_message
                , update_time
                , action_user
            ) 
            VALUES ( 
                %s
                , %s
                , %s
                , %s
                , %s
                , %s
                , %s
                , %s
                , %s
                , CURRENT_TIMESTAMP
                , %s

            )

        """
        parameters = (
            region,
            action_seq,
            action_name,
            step_level,
            parent_step,
            action_description,
            business_date,
            status,
            bl_message,
            ac_user,
        )

        self.db.execute_insert_query(sql_query, parameters)

    def get_aloc_data_define(self, region):
        """
        取得配置数据
        """
        sql_query = "SELECT def_name,def_value FROM sc_aloc_data_def WHERE otc_region = %s order by def_type, def_id ;"
        parameters = (region,)
        rst = self.db.execute_query_to_pandas(sql_query, parameters)
        return rst
    
    def get_def_data_by_name(self, def_data, def_name):
        """
        从配置数据表DF中取得配置项名字对应的value
        """
        try:
            def_value = def_data.loc[def_name, "def_value"]
            return def_value
        except KeyError:
            return ""
        
    def update_file_ctl_status(self,ac_status,prefix,region,ac_user):
        """
        更新文件允许load管理状态
        """
        sql_query = """ update sc_action_control 
            set ac_status= %s ,update_time = CURRENT_TIMESTAMP ,update_user= %s
            WHERE otc_region = %s and file_prefix = %s ; """
        parameters = (
            ac_status,
            ac_user,
            region,
            prefix,
        )
        self.db.execute_update_query(sql_query, parameters)

    def get_comm_define(self,region):
        """
        取得外部公共定义
        """
        sql_query = "SELECT * FROM sc_com_define WHERE (otc_region = 'WW' or otc_region = %s) and del_flg = '0';"
        parameters = (
            region,
        )

        rst = self.db.execute_query_to_pandas(sql_query, parameters)
        return rst
    
    def get_com_def_by_name(self, def_data, def_type):
        """
        从配置数据表DF中取得配置项名字对应的value
        """
        try:
            def_value = def_data.loc[def_type,"def_context"]
            return def_value
        except KeyError:
            return ""
    
    def get_division_status(self,region,action_name):
        """
        取得Action状态区分表信息

        """
        sql_query = "SELECT * FROM sc_action_division WHERE otc_region = %s and action_name = %s ;"
        parameters = (
            region,
            action_name,
        )
        rst = self.db.execute_query_to_pandas(sql_query, parameters)
        return rst
    
    def check_is_lock(self,region,action_name,action_user,kicker="comm"):
        """
        检查是否正在锁定

        webuser lock，web触发，同user时，不skip
				batch触发	skip	
        batchuser lock，web触发，skip			
                        batch触发	skip
        ==> lock and same webuser not skip
        """
        ret = False
        rdf = self.get_division_status(region,action_name)
        if not rdf.empty:
            ac_status = rdf.loc[0, "ac_status"]
            ac_user = rdf.loc[0, "action_user"]
            if ac_status =="lock":
                # 当前锁定的user与新user是同一个，并且是webuser时，不进行锁定
                if (action_user.strip()==ac_user.strip()) and ("batch" not in ac_user):
                    ret = False
                else:
                    ret = True
        return ret
    
    def unlock_action(self,region,action_name,ac_status,ac_user):
        """
        web batch 互斥控制解锁处理
        判断调用来源 webapi，batch，									
            当user为webuser时，
                执行处理							
                不解锁							
            当user为batchuser时， 								
                当状态锁定时，退出执行。							
                当没有锁定状态时，							
                    登录锁定状态						
                        执行处理					
                                            
                    解开锁定状态

        """
        # batch user
        if ("batch" in ac_user) and ("@" not in ac_user):
            self.update_div_status(region=region,action_name=action_name,ac_status=ac_status,ac_user=ac_user)
        # web user
        # elif("@" in ac_user):
        #     pass



    def update_div_status(self,region,action_name,ac_status,ac_user):
        """
        更新Action锁定状态
        """
        self.logger.debug(f"action division status update: {region} ,{action_name} , {ac_status} , {ac_user} ")
        sql_query = """ update sc_action_division 
            set ac_status= %s ,update_time = CURRENT_TIMESTAMP ,action_user= %s
            WHERE otc_region = %s and action_name = %s ; """
        parameters = (
            ac_status,
            ac_user,
            region,
            action_name,
        )
        self.db.execute_update_query(sql_query, parameters)