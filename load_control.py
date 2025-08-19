"""
# Data Loading Control
"""

from utils.db_util import Database
from utils.file_util import FileUtil
from utils.comm_util import CommUtil


class LoadControl:
    """
    # Data Loading Control
    控制 mage 不要并发相同的文件 多个load处理
    """
    # 开始执行load 2 DB 的处理
    LOAD_ON = 1
    # load 完毕状态
    LOAD_OFF = 0

    def  __init__(self,logger) -> None:
        self.logger = logger
        self.db = Database(logger=logger)
        self.file_util = FileUtil(logger=logger)
        self.comm_util = CommUtil(logger=logger)

        self.logger.info('Check whether file could be load.' )

    # 当文件存在，并且 文件被允许load时，返回 True
    # 否则，返回False
    # 在load处理开始后，将允许load标识改为 不允许
    
    def check_file_can_load(self,prefix,region):
        """
        检查是否存在文件，文件是否可用
        """
        target_file = self.file_util.check_cos_file(sub_dir=region,prefix=prefix)
        if target_file:
            if self.check_file_status(prefix=prefix,region=region):
                self.logger.info(f'File control check file could load : {prefix}')
                return True
        else:
            self.logger.info(f'File not exist can not load : {prefix}')
        return False
    
    def check_file_status(self,prefix,region):
        """
        检查DB管理的文件允许load状态
        """
        df = self.get_file_load(prefix=prefix,region=region)
        if df.empty:
            self.logger.info(f'File : {prefix}  not found in sc_action_control table.')
            return False
        else:
            sts = df.loc[0, "ac_status"]
            if sts == self.LOAD_ON: # 1
                return True
            else:
                self.logger.info(f'File : {prefix}  status is :{sts}. forbiden to load')
                return False

    def get_file_load(self,prefix,region):
        """
        取得文件允许load状态
        """
        sql_query = "SELECT * FROM sc_action_control WHERE otc_region = %s and file_prefix = %s and del_flg = '0';"
        parameters = (region,prefix,)

        rst = self.db.execute_query_to_pandas(sql_query, parameters)
        return rst
    
