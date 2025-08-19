"""
移动文件处理
从SFTP到Cloud Storage
从Mage Temp folder 到 Cloud Storage 
等等

"""

from utils.db_util import Database
from utils.file_util import FileUtil
from utils.comm_util import CommUtil


class MoveFileAction:
    """
    文件移动，传输定义
    """

    def __init__(self, name: str, logger=None) -> None:
        self.name = name
        self.logger = logger
        self.db = Database(logger=logger)
        self.file_util = FileUtil(logger=logger)
        self.comm_util = CommUtil(logger=logger)

    def move_to_mage_folder(self, region, file_action_name, filename,ac_user="system"):
        """
        copy文件从 sftp 到 Cloud storage
        并记录状态

        """
        bz_date = self.comm_util.get_daytime_string()
        self.comm_util.update_file_uploading_status(
            region=region,
            action_name=file_action_name,
            business_date=bz_date,
            status=self.comm_util.BL_STS["0"],
            bl_message=f"move file:[{filename}] to mage folder start.",
            ac_user=ac_user
        )

        # TODO
        # move files

        self.logger.info(f"Move file : {filename} Successfully. ")

        self.comm_util.update_file_uploaded_status(
            region=region,
            action_name=file_action_name,
            business_date=bz_date,
            status=self.comm_util.BL_STS["1"],
            bl_message=f"move file:[{filename}] to mage folder Successfully.",
            ac_user=ac_user
        )

    def update_file_uploaded(self, region, file_action_name, filename,ac_user="system"):
        """
        记录文件上传完成状态
        """
        bz_date = self.comm_util.get_daytime_string()
        self.comm_util.update_file_uploading_status(
            region=region,
            action_name=file_action_name,
            business_date=bz_date,
            status=self.comm_util.BL_STS["0"],
            bl_message=f"move file:[{filename}] to mage folder start.",
            ac_user=ac_user
        )

        self.comm_util.update_file_uploaded_status(
            region=region,
            action_name=file_action_name,
            business_date=bz_date,
            status=self.comm_util.BL_STS["1"],
            bl_message=f"move file:[{filename}] to mage folder Successfully.",
            ac_user=ac_user
        )
