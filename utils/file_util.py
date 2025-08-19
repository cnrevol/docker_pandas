"""
文件处理工具类
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import yaml
import pandas as pd
import ibm_boto3
from ibm_botocore.client import Config, ClientError
import paramiko
import time
from typing import Dict, Tuple
import random

from exceptions import CustomException
from global_state import GlobalState


class FileUtil:
    """
    文件处理
    """
    POST_TEMPLATE = "Posting output.xlsx"
    ALOC_TEMPLATE = "Allocation output.xlsx"
    # when to server change to 0
    is_local = 1

    def __init__(self,state:GlobalState=None,logger=None):
        self.ccos,_ = self.create_cos()
        self.state = state
        self.logger = logger

    def run_path(self, subdir):
        """
        取得路径
        """
        script_path = os.path.abspath(sys.argv[0])
        script_directory = os.path.dirname(script_path)
        script_directory = os.path.join(script_directory, "files", subdir)

        return script_directory

    def create_cos(self):
        """
        云认证
        TODO 生产环境需要修改
        """
        
        # COS_ENDPOINT = "https://s3.us-south.cloud-object-storage.appdomain.cloud"  #
        # COS_API_KEY_ID = "DdD5ls76wr-2N6z0OebdZLs30UrlaSDvT-pHsiHrAoHI"  #
        # COS_INSTANCE_CRN = "crn:v1:bluemix:public:cloud-object-storage:global:a/46e65f4bce7bae919c46ea6c6c04d886:0e8d7c2d-1ab2-475b-af17-d04cf59f0eb6::"  #
        cos_param = self.load_app_config_from_yaml()
        # COS_API_KEY_ID = cos_param['cos_api_key_id']
        # COS_INSTANCE_CRN = cos_param['cos_instance_crn']
        # COS_ENDPOINT = cos_param['cos_endpoint']

        bucket = "bpod-otc-storage"
        cos = ibm_boto3.resource(
            "s3",
            ibm_api_key_id=cos_param['COS_API_KEY_ID'],
            ibm_service_instance_id=cos_param['COS_INSTANCE_CRN'],
            config=Config(signature_version="oauth"),
            endpoint_url=cos_param['COS_ENDPOINT'],
        )
        return cos, bucket
    
    
    def load_app_config_from_yaml(self,config_path="app_config.yml",def_cont="cos"):
        """
        参数取得方法
        """
        config_file_path = Path(__file__).resolve().parent.parent / "config" / config_path
        with open(config_file_path, "r",encoding="utf-8") as config_file:
            config_data = yaml.safe_load(config_file)
        return config_data[def_cont]  # Assuming "db_params" is the key in your YAML
    
    # def find_file_by_prefix(self, directory, file_prefix):
    #     """
    #     根据文件名前缀
    #     查找指定路径的文件
    #     返回
    #     如果多个，抛出异常。
    #     """
    #     # 获取目录下所有文件
    #     # TODO
    #     # all_files = os.listdir(directory)
    #     path = self.run_path(directory)
    #     all_files = os.listdir(path)

    #     # 在所有文件中找到匹配前缀的文件
    #     matching_files = [file for file in all_files if file.startswith(file_prefix)]
    #     if matching_files:
    #         if len(matching_files) > 1:
    #             raise CustomException(f"More than 1 {file_prefix} files.")

    #     return os.path.join(path, matching_files[0])

    # def backup_file(self, src_file):
    #     """
    #     备份文件
    #     """
    #     # 获取文件名和目录
    #     file_dir, file_name = os.path.split(src_file)
    #     # 获取文件夹名称
    #     dir_name = os.path.basename(os.path.normpath(file_dir))

    #     # 构建 backup 目录路径
    #     backup_dir = os.path.join(file_dir, "..", "backup", dir_name)

    #     # 检查 backup 目录是否存在，不存在则创建
    #     if not os.path.exists(backup_dir):
    #         os.makedirs(backup_dir)

    #     # 添加时间戳
    #     timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    #     backup_file_name = f"{timestamp}_{file_name}"

    #     # 构建备份文件的路径
    #     backup_path = os.path.join(backup_dir, backup_file_name)

    #     try:
    #         # 拷贝文件到 backup 目录
    #         shutil.copy2(src_file, backup_path)

    #         # 删除源文件
    #         # TODO 生产环境下 删除
    #         # os.remove(src_file)

    #         self.logger.info(f"Backup successful: {src_file} -> {backup_path}")

    #     except Exception as e:
    #         self.logger.error(f"Backup failed: {e}")

    def open_template(self, region, temp_name,filename=""):
        """
        取得模板
        """
        path = self.run_path("template")

        template_file = os.path.join(path,temp_name)

        out_path = os.path.join(self.run_path("post_file"), region)

        if not os.path.exists(out_path):
            os.makedirs(out_path)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        out_post_file = f"{region}_{filename}_{timestamp}.xlsx"

        out_file = os.path.join(out_path, out_post_file)

        shutil.copyfile(template_file, out_file)

        # , engine='openpyxl', mode='a'
        # book = load_workbook(out_file)
        writer = pd.ExcelWriter(out_file, engine='openpyxl') # pylint: disable=abstract-class-instantiated
        # writer.book = book

        return writer, out_file, out_post_file
    

    def upload_file_2_bucket(self,region, item_name, file_path):
        """
        upload magefolder file 2 cloud storage
        """
        bucket_name = self.get_bucket_name_by_region(region)
        self.multi_part_upload(bucket_name,item_name,file_path,self.ccos)

    def get_bucket_file(self, bucket_name, item_name, file_path, cos):
        """
        取得云存储数据
        """
        # self.logger.info("Retrieving item from bucket: {0}, key: {1}".format(bucket_name, item_name))
        try:
            file = cos.Object(bucket_name, item_name).get()
            file_content = file["Body"].read()
            file_path = os.path.join(file_path, item_name)
            with open(file_path, "wb") as local_file:
                local_file.write(file_content)
            self.logger.info(f"get bucket: {bucket_name} done. local path: {file_path}")
        except ClientError as be:
            self.logger.error(f"get_bucket_file CLIENT ERROR: {be}\n")
        except Exception as e:
            self.logger.error(f"Unable to retrieve file contents: {e}")

    def multi_part_upload(self, bucket_name, item_name, file_path, cos):
        """
        上传到云存储
        """
        try:
            self.logger.info(
                f"Starting file transfer for {item_name} to bucket: {bucket_name}\n"
            )
            # set 5 MB chunks
            part_size = 1024 * 1024 * 5

            # set threadhold to 15 MB
            file_threshold = 1024 * 1024 * 15

            # set the transfer threshold and chunk size
            transfer_config = ibm_boto3.s3.transfer.TransferConfig(
                multipart_threshold=file_threshold, multipart_chunksize=part_size
            )

            # the upload_fileobj method will automatically execute a multi-part upload
            # in 5 MB chunks for all files over 15 MB
            with open(file_path, "rb") as file_data:
                cos.Object(bucket_name, item_name).upload_fileobj(
                    Fileobj=file_data, Config=transfer_config
                )

            self.logger.info(f"Transfer for {item_name} Complete!\n")
        except ClientError as be:
            self.logger.error(f"multi_part_upload CLIENT ERROR: {be}\n")
        except Exception as e:
            self.logger.error(f"Unable to complete multi-part upload: {e}")

    def get_bucket_contents(self, bucket_name, cos):
        """ 
        下载数据
        """
        self.logger.debug(f"Retrieving bucket contents from: {bucket_name}")
        file_list = []
        try:
            files = cos.Bucket(bucket_name).objects.all()
            for file in files:
                file_list.append(file.key)
                self.logger.debug(f"Item: {file.key} ({file.size} bytes) (create time: {file.last_modified}).")
            return file_list
        except ClientError as be:
            self.logger.error(f"get_bucket_contents CLIENT ERROR: {be}\n")
        except Exception as e:
            self.logger.error(f"Unable to retrieve bucket contents: {e}")

    def rename_cloud_file(self, file_name, rename_file_name, bucket_name, cos):
        """ 
        修改云端存储文件名
        """
        try:
            file = cos.Object(bucket_name, file_name).get()
            file_content = file["Body"].read()
            self.logger.debug(f"{file_name} get file content success\n")
            cos.Object(bucket_name, rename_file_name).put(Body=file_content)
            self.logger.debug(f"{rename_file_name} rename success\n")
            # cos.delete_objects(Bucket=bucket_name, Key=file_name)
            cos.Object(bucket_name, file_name).delete()
            self.logger.debug(f"Item: {file_name} deleted!\n")
        except ClientError as be:
            self.logger.error(f"rename_cloud_file CLIENT ERROR: {be}\n")
        except Exception as e:
            self.logger.error(f"Unable to rename cloud file: {e}")

    def backup_cloud_file(self, file_name, bucket_name, cos, bucket=1,back_name=""):
        """
        备份云端文件  
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        if bucket == 1:
            backup_file_name = f"{timestamp}_{file_name}"
        else:
            backup_file_name=f"{back_name}{timestamp}_{file_name}"
        try:
            file = cos.Object(bucket_name, file_name).get()
            file_content = file["Body"].read()
            self.logger.debug(f"{file_name} get file content success\n")
            if bucket == 1:
                self.logger.debug(f"backup to bucket: {bucket_name}-bk\n")
                cos.Object(bucket_name + "-bk", backup_file_name).put(Body=file_content)
            else:
                self.logger.debug(f"backup to bucket: {bucket_name} \n")
                cos.Object(bucket_name, backup_file_name).put(Body=file_content)
            self.logger.debug(f"{backup_file_name} rename success\n")
            # cos.delete_objects(Bucket=bucket_name, Key=file_name)
            cos.Object(bucket_name, file_name).delete()
            self.logger.debug(f"Item: {file_name} deleted!\n")
        except ClientError as be:
            self.logger.error(f"backup_cloud_file CLIENT ERROR: {be}\n")
        except Exception as e:
            self.logger.error(f"Unable to backup cloud file: {e}")



    def download_file(self, sub_dir, prefix, download_path):
        """
        下载文件
        """
        result = {}
        
        bucket_name = self.get_bucket_name_by_region(sub_dir)
        result['bucket_name'] = bucket_name
        # cos,_ = self.create_cos()
        # 获取storage所有文件名
        cloud_file_list = self.get_bucket_contents(bucket_name,self.ccos)
        
        if len(cloud_file_list) != 0:
            # 用目标文件前缀匹配
            cloud_matching_files = [file for file in cloud_file_list if (file.startswith(prefix))]
            if cloud_matching_files:
                if len(cloud_matching_files) > 1:
                    self.logger.error(f"More than 1 {prefix} files On cloud: {cloud_matching_files}.")
                    for cfile in cloud_matching_files[1:]:
                        self.logger.debug(f"move file to bucket :{bucket_name}, filename:{cfile}")
                        self.backup_cloud_file(cfile, bucket_name, self.ccos)
                    # 当多个文件的时候仅仅输入日志，处理不停止
                    # raise CustomException(f"More than 1 {prefix} file in cos, please check the backup to confrim the file contents.")
                # rename
                # self.rename_cloud_file(cloud_matching_files[0],'doing_'+cloud_matching_files[0], bucket_name, self.ccos)
                # 下载文件 多个sheet避免重复下载
                if self.state.is_1st_part():
                    self.get_bucket_file(bucket_name, cloud_matching_files[0], download_path, self.ccos)
                # 云端备份文件 改为 load 结束后 备份
                # self.backup_cloud_file(cloud_matching_files[0], bucket_name, self.ccos)
                result['download_file_name'] = cloud_matching_files[0]
            else:
                self.logger.info(f"There is no file to load file name: {prefix}")
                result['download_file_name'] = None
                # raise CustomException(f"There is no file to load file name {prefix}")
        else:
            result['download_file_name'] = None
        return result

    def get_bucket_name_by_region(self, sub_dir):
        """
        根据Region 取得 Cos bucket
        """
        bucket_names = {
            'MY': 'ifp-malaysia',
            'SG': 'ifp-singapore',
            'AU': 'ifp-australia',
            'NZ': 'ifp-newzealand',
            'IN': 'ifp-india',
            'CN': 'ifp-china',
            'TW': 'ifp-taiwan',
            'HK': 'ifp-hongkong',
            'ifp-post': 'ifp-post'
        }

        bucket_name = bucket_names.get(sub_dir, None)
        return bucket_name
    
    def check_cos_file(self,sub_dir, prefix):
        """
        检查是否存在
        """
        bucket_name = self.get_bucket_name_by_region(sub_dir)
        
        cos,_ = self.create_cos()
        # 获取storage所有文件名
        cloud_file_list = self.get_bucket_contents(bucket_name,cos)
        if len(cloud_file_list) != 0:
            # 用目标文件前缀匹配
            cloud_matching_files = [file for file in cloud_file_list if (file.startswith(prefix))]
            if cloud_matching_files:
                return True
        self.logger.debug(f"There is no file on COS to load file name {prefix}")
        return False

    def find_file_by_prefix(self,directory, file_prefix):
        '''
        根据文件名前缀
        查找指定路径的文件
        返回
        如果多个，抛出异常。

        '''
        # 文件路径，运行环境存储
        path = self.run_path(directory)

        # cloud storage
        if self.is_local == 0 :
            # all_files = os.listdir(directory)
            # ibm cloud storage
            result = self.download_file(directory, file_prefix, path)
            all_files = os.listdir(path)
            # --------------cloud storage-------------
            if len(all_files) != 0 and result['download_file_name'] in all_files:
                result['target_file'] = os.path.join(path,result['download_file_name'])
            else:
                result['target_file'] = None
            return result['target_file'], result['bucket_name']
        else:
            all_files = os.listdir(path)
            # ----------本地测试用------------------
            # 在所有文件中找到匹配前缀的文件
            matching_files = [file for file in all_files if file.startswith(file_prefix)]
            # matching_files = [file for file in all_files if (file.startswith(file_prefix) or file_prefix in file)]
            if matching_files:
                if len(matching_files) > 1:
                    self.logger.error(f"More than 1 {file_prefix} files. {matching_files}")
                    raise CustomException(f"More than 1 {file_prefix} files.")
                else:
                    self.logger.info(f"Found and To load file name {file_prefix}, {matching_files[0]}")
                return os.path.join(path,matching_files[0]),None
            else:
                self.logger.info(f"There is no file to load file name {file_prefix}")
                return None,None
                # raise CustomException(f"There is no file to load file name {file_prefix}")
            
    # def backup_file(self,src_file,bucket_name):
    #     '''
    #     备份文件
    #     '''       
    #     # 获取文件名和目录
    #     file_dir, file_name = os.path.split(src_file)
    #     # 获取文件夹名称
    #     dir_name = os.path.basename(os.path.normpath(file_dir))

    #     # 构建 backup 目录路径
    #     backup_dir = os.path.join(file_dir, '..', 'backup', dir_name)

    #     # 检查 backup 目录是否存在，不存在则创建
    #     if not os.path.exists(backup_dir):
    #         os.makedirs(backup_dir)

    #     # 添加时间戳
    #     timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    #     backup_file_name = f"{timestamp}_{file_name}"

    #     # 构建备份文件的路径
    #     backup_path = os.path.join(backup_dir, backup_file_name)

    #     try:
    #         # 拷贝文件到 backup 目录
    #         shutil.copy2(src_file, backup_path)
    #         if self.is_local == 0:
    #             # 删除源文件
    #             # TODO 生产环境下 删除
    #             os.remove(src_file)
    #             # cos,_ = self.create_cos()
    #             self.backup_cloud_file('doing_'+file_name, backup_file_name, bucket_name, self.ccos)

    #         self.logger.info(f"Backup successful: {src_file} -> {backup_path}")

    #     except Exception as e:
    #         self.logger.error(f"Backup failed: {e}")
        

    def backup_file(self,src_file,bucket_name):
        '''
        备份文件
        '''       
        # 获取文件名和目录
        file_dir, file_name = os.path.split(src_file)
        # 添加时间戳
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_file_name = f"{timestamp}_{file_name}"
        self.state.done_read()

        if self.is_local == 1:
            # 获取文件夹名称
            if self.state.get_left_count()==0:
                self.backup_local_file(src_file, file_dir, backup_file_name)
        elif self.is_local == 0:
            # 一个文件多个sheet需要load时，判断是否全部sheetload完毕，备份文件
            if self.state.get_left_count()==0:
                self.backup_cloud_file(file_name, bucket_name, self.ccos)
                os.remove(src_file)
        #     # 删除源文件
        #     # TODO 生产环境下 删除
            # os.remove(src_file)
        #     # cos,_ = self.create_cos()
        #     self.backup_cloud_file(file_name, bucket_name, self.ccos)
    def rename_live_file(self,src_file,bucket_name,back_name):
        """
        rename the file
        """
        # 获取文件名和目录
        file_dir, file_name = os.path.split(src_file)
        # 添加时间戳
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_file_name = f"{timestamp}_{file_name}"
        self.state.done_read()
        self.logger.debug(f"filename:{backup_file_name},sf:{src_file}. flg:{self.is_local}. left count:{self.state.get_left_count()}")
        if self.is_local == 1:
            # 获取文件夹名称
            if self.state.get_left_count()==0:
                self.backup_local_file(src_file, file_dir, backup_file_name)
        elif self.is_local == 0:
            if self.state.get_left_count()==0:
                self.backup_cloud_file(file_name, bucket_name, self.ccos,bucket=0,back_name=back_name)
                os.remove(src_file)

    def backup_local_file(self, src_file, file_dir, backup_file_name):
        """
        备份本地文件
        """
        dir_name = os.path.basename(os.path.normpath(file_dir))
            # 构建 backup 目录路径
        backup_dir = os.path.join(file_dir, '..', 'backup', dir_name)
            # 检查 backup 目录是否存在，不存在则创建
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            # 构建备份文件的路径
        backup_path = os.path.join(backup_dir, backup_file_name)
        try:
                # 拷贝文件到 backup 目录
            shutil.copy2(src_file, backup_path)
            self.logger.info(f"Backup successful: {src_file} -> {backup_path}")
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
    
    def del_cos_files_before_days(self,region,days):
        """
        删除指定天数之前的bucket对象
        """
        self.del_bucket_obj_before_days(region,days,self.ccos)
        
    def del_bucket_obj_before_days(self,region,days,cos):
        """
        删除指定天数之前的bucket对象
        """
        now = datetime.now()
        before_days = now - timedelta(days=days)
        # cos= self.ccos
        bucket_name = self.get_bucket_name_by_region(region)
        files = cos.Bucket(bucket_name).objects.all()
        for file in files:
            self.logger.debug(f"Check obj to delete: {file.key} ({file.size} bytes) (create time: {file.last_modified}).")
            if file.last_modified.date() <= before_days.date():
                self.logger.debug(f"delete: {file.key} .")
                cos.Object(bucket_name, file.key).delete()

    def create_sftp(self, user_type: str = 'ifp') -> tuple:
        """
        创建SFTP连接
        Args:
            user_type: 'ifp' 或 'vdi' 用户类型
        Returns:
            tuple: (sftp_client, transport)
        """
        sftp_param = self.load_app_config_from_yaml(def_cont="SFTP")
        
        if user_type == 'ifp':
            username = sftp_param['SFTP_IFP_ID']
            password = sftp_param['SFTP_IFP_PASS']
        else:
            username = sftp_param['SFTP_VDI_ID']
            password = sftp_param['SFTP_VDI_PASS']
            
        host = sftp_param['SFTP_HOST']
        sftp_path = sftp_param['SFTP_PATH']
        
        try:
            transport = paramiko.Transport((host, 22))
            transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            self.logger.info(f"SFTP connection established for {user_type} user")
            return sftp, transport, sftp_path
        except Exception as e:
            self.logger.error(f"Failed to establish SFTP connection: {str(e)}")
            raise CustomException(f"SFTP connection failed: {str(e)}")

    def get_sftp_path(self, region: str, path_type: str = 'source') -> str:
        """
        根据地区获取SFTP路径
        Args:
            region: 地区代码 (AU, NZ, CN, MY, SG, IN, TW, HK)
            path_type: 'source' 或 'output'
        Returns:
            str: SFTP完整路径
        """
        valid_regions = ['AU', 'NZ', 'CN', 'MY', 'SG', 'IN', 'TW', 'HK','ifp-post']
        if region not in valid_regions:
            raise CustomException(f"Invalid region: {region}")
            
        sftp_param = self.load_app_config_from_yaml(def_cont="SFTP")
        base_path = sftp_param['SFTP_PATH']
        
        if path_type == 'source':
            return f"/{base_path}/source_data/{region}"
        else:
            return f"/{base_path}/output_data/{region}"

    def check_file_stable(self, sftp: paramiko.SFTPClient, remote_path: str, 
                         check_interval: int = 10, max_attempts: int = 6) -> bool:
        """
        检查SFTP文件大小是否稳定
        Args:
            sftp: SFTP客户端
            remote_path: 远程文件路径
            check_interval: 检查间隔(秒)
            max_attempts: 最大检查次数
        Returns:
            bool: 文件是否稳定
        """
        try:
            initial_size = sftp.stat(remote_path).st_size
            self.logger.info(f"Initial file size for {remote_path}: {initial_size} bytes")
            
            for _ in range(max_attempts):
                time.sleep(check_interval)
                current_size = sftp.stat(remote_path).st_size
                self.logger.debug(f"Current file size: {current_size} bytes")
                
                if current_size != initial_size:
                    initial_size = current_size
                    continue
                return True
                
            return False
        except Exception as e:
            self.logger.error(f"Error checking file stability: {str(e)}")
            return False

    def download_sftp_to_cos(self, region: str, user_type: str = 'ifp', max_retries: int = 3, retry_delay: float = 1.0) -> Dict[str, list]:
        """
        从SFTP下载文件到COS，成功后删除SFTP上的源文件
        Args:
            region: 地区代码
            user_type: SFTP用户类型
            max_retries: 最大重试次数
            retry_delay: 重试间隔时间（秒）
        Returns:
            Dict: 包含下载文件信息的字典
        """
        result = {'success': [], 'failed': []}
        
        # 带重试的SFTP连接
        sftp, transport, sftp_path = self._create_sftp_with_retry(user_type, max_retries, retry_delay)
        
        try:
            source_path = self.get_sftp_path(region, 'source')
            bucket_name = self.get_bucket_name_by_region(region)
            
            try:
                # 获取源目录下的所有文件
                files = sftp.listdir(source_path)
                
                for filename in files:
                    remote_path = f"{source_path}/{filename}"
                    temp_path = None
                    
                    try:
                        # 检查文件大小是否稳定
                        if not self.check_file_stable(sftp, remote_path):
                            self.logger.warning(f"File {filename} size not stable, skipping")
                            result['failed'].append({
                                'filename': filename,
                                'reason': 'File size not stable'
                            })
                            continue
                            
                        # 获取文件大小
                        file_size = sftp.stat(remote_path).st_size
                        self.logger.info(f"Downloading {filename} ({file_size} bytes)")
                        
                        # 创建临时文件
                        temp_path = os.path.join(self.run_path("sftptemp"), filename)
                        
                        # 带重试的文件下载
                        success = self._download_file_with_retry(sftp, remote_path, temp_path, filename, max_retries, retry_delay)
                        if not success:
                            result['failed'].append({
                                'filename': filename,
                                'reason': 'Download failed after retries'
                            })
                            continue
                        
                        self.logger.info(f"Downloaded {filename} to local temp path")
                        
                        # 上传到COS
                        self.multi_part_upload(bucket_name, filename, temp_path, self.ccos)
                        self.logger.info(f"Uploaded {filename} to COS successfully")
                        
                        # 上传成功后删除SFTP上的源文件
                        self._delete_remote_file_with_retry(sftp, remote_path, filename, max_retries, retry_delay)
                        
                        # 删除临时文件
                        if temp_path and os.path.exists(temp_path):
                            os.remove(temp_path)
                            self.logger.debug(f"Removed temp file {temp_path}")
                        
                        result['success'].append({
                            'filename': filename,
                            'size': file_size
                        })
                        
                    except Exception as e:
                        self.logger.error(f"Error processing file {filename}: {str(e)}")
                        
                        # 清理临时文件
                        if temp_path and os.path.exists(temp_path):
                            try:
                                os.remove(temp_path)
                                self.logger.debug(f"Cleaned up temp file {temp_path} after error")
                            except Exception as cleanup_error:
                                self.logger.error(f"Failed to cleanup temp file {temp_path}: {str(cleanup_error)}")
                        
                        result['failed'].append({
                            'filename': filename,
                            'reason': str(e)
                        })
                        
            finally:
                sftp.close()
                transport.close()
                
        except Exception as e:
            self.logger.error(f"SFTP to COS download failed: {str(e)}")
            raise CustomException(f"SFTP to COS download failed: {str(e)}")
            
        return result
    
    def _create_sftp_with_retry(self, user_type: str, max_retries: int = 3, retry_delay: float = 1.0) -> Tuple:
        """
        带重试机制的SFTP连接创建
        Args:
            user_type: SFTP用户类型
            max_retries: 最大重试次数
            retry_delay: 重试间隔时间（秒）
        Returns:
            Tuple: (sftp, transport, sftp_path)
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                self.logger.info(f"Attempting SFTP connection (attempt {attempt + 1}/{max_retries + 1})")
                sftp, transport, sftp_path = self.create_sftp(user_type)
                self.logger.info("SFTP connection established successfully")
                return sftp, transport, sftp_path
                
            except Exception as e:
                last_exception = e
                self.logger.warning(f"SFTP connection attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < max_retries:
                    # 计算重试延迟时间（带随机抖动避免同时重试）
                    delay = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    self.logger.info(f"Waiting {delay:.2f} seconds before retry...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"All SFTP connection attempts failed. Last error: {str(e)}")
                    break
        
         # 所有重试都失败了
        # raise CustomException(f"SFTP connection failed after {max_retries + 1} attempts. Last error: {str(last_exception)}")
        self.logger.error(f"SFTP connection failed after {max_retries + 1} attempts. Last error: {str(last_exception)}")

    def _download_file_with_retry(self, sftp, remote_path: str, temp_path: str, filename: str, 
                                max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """
        带重试机制的文件下载
        Args:
            sftp: SFTP连接对象
            remote_path: 远程文件路径
            temp_path: 本地临时文件路径
            filename: 文件名
            max_retries: 最大重试次数
            retry_delay: 重试间隔时间（秒）
        Returns:
            bool: 下载是否成功
        """
        for attempt in range(max_retries + 1):
            try:
                # 如果临时文件已存在，先删除
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
                sftp.get(remote_path, temp_path)
                self.logger.info(f"File {filename} downloaded successfully on attempt {attempt + 1}")
                return True
                
            except Exception as e:
                self.logger.warning(f"Download attempt {attempt + 1} for {filename} failed: {str(e)}")
                
                # 清理可能存在的不完整文件
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    self.logger.info(f"Waiting {delay:.2f} seconds before retry...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"All download attempts for {filename} failed. Last error: {str(e)}")
                    break
        
        return False

    def _delete_remote_file_with_retry(self, sftp, remote_path: str, filename: str, 
                                    max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """
        带重试机制的远程文件删除
        Args:
            sftp: SFTP连接对象
            remote_path: 远程文件路径
            filename: 文件名
            max_retries: 最大重试次数
            retry_delay: 重试间隔时间（秒）
        Returns:
            bool: 删除是否成功
        """
        for attempt in range(max_retries + 1):
            try:
                sftp.remove(remote_path)
                self.logger.info(f"Deleted source file {filename} from SFTP on attempt {attempt + 1}")
                return True
                
            except Exception as e:
                self.logger.warning(f"Delete attempt {attempt + 1} for {filename} failed: {str(e)}")
                
                if attempt < max_retries:
                    delay = retry_delay + random.uniform(0, 0.5)
                    self.logger.info(f"Waiting {delay:.2f} seconds before retry...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Failed to delete source file {filename} from SFTP after {max_retries + 1} attempts: {str(e)}")
                    # 即使删除失败，也不影响整个流程，只记录日志
                    break
        
        return False

    def upload_cos_to_sftp(self, region: str, filename: str, user_type: str = 'vdi') -> bool:
        """
        从COS上传文件到SFTP
        Args:
            region: 地区代码
            filename: 文件名
            user_type: SFTP用户类型
        Returns:
            bool: 上传是否成功
        """
        try:
            sftp, transport, sftp_path = self.create_sftp(user_type)
            target_path = self.get_sftp_path(region, 'output')
            bucket_name = self.get_bucket_name_by_region(region)
            
            try:
                # 创建临时文件
                temp_path = os.path.join(self.run_path("sftptemp"), filename)
                
                # 从COS下载文件
                self.get_bucket_file(bucket_name, filename, self.run_path("sftptemp"), self.ccos)
                
                # 上传到SFTP
                remote_path = f"{target_path}/{filename}"
                sftp.put(temp_path, remote_path)
                
                # 删除临时文件
                os.remove(temp_path)
                
                self.logger.info(f"Successfully uploaded {filename} to SFTP")
                return True
                
            finally:
                sftp.close()
                transport.close()
                
        except Exception as e:
            self.logger.error(f"COS to SFTP upload failed: {str(e)}")
            raise CustomException(f"COS to SFTP upload failed: {str(e)}")
        

    def upload_all_cos_to_sftp(self, region: str, user_type: str = 'vdi') -> Dict[str, list]:
        """
        从COS批量上传所有文件到SFTP，上传成功后备份文件到backup路径
        Args:
            region: 地区代码
            user_type: SFTP用户类型，默认为'vdi'
        Returns:
            Dict: 包含上传结果的字典，格式为 {'success': [...], 'failed': [...]}
        """
        result = {'success': [], 'failed': []}
        
        try:
            # 创建SFTP连接
            sftp, transport, sftp_path = self.create_sftp(user_type)
            
            # 获取对应region的bucket名称和SFTP目标路径
            bucket_name = self.get_bucket_name_by_region(region)
            target_path = self.get_sftp_path(region, 'output')
            
            # 确保临时目录存在
            temp_dir = self.run_path("sftptemp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            try:
                # 获取COS bucket中的所有文件列表
                file_list = self.get_bucket_contents(bucket_name, self.ccos)
                
                if not file_list:
                    self.logger.info(f"No files found in COS bucket: {bucket_name}")
                    return result
                
                self.logger.info(f"Found {len(file_list)} files in COS bucket: {bucket_name}")
                
                # 确保SFTP目标目录存在
                try:
                    sftp.listdir(target_path)
                except FileNotFoundError:
                    # 如果目录不存在，尝试创建（可能需要逐级创建）
                    self._create_sftp_directory(sftp, target_path)
                
                # 遍历处理每个文件
                for filename in file_list:
                    temp_path = None
                    
                    try:
                        self.logger.info(f"Processing file: {filename}")
                        
                        # 创建临时文件路径
                        temp_path = os.path.join(temp_dir, filename)
                        
                        # 从COS下载文件到本地临时目录
                        self.get_bucket_file(bucket_name, filename, temp_dir, self.ccos)
                        self.logger.debug(f"Downloaded {filename} from COS to temp directory")
                        
                        # 检查文件是否成功下载
                        if not os.path.exists(temp_path):
                            raise Exception(f"Failed to download file from COS: {filename}")
                        
                        # 获取文件大小用于日志记录
                        file_size = os.path.getsize(temp_path)
                        
                        # 上传文件到SFTP
                        remote_path = f"{target_path}/{filename}"
                        sftp.put(temp_path, remote_path)
                        self.logger.info(f"Uploaded {filename} ({file_size} bytes) to SFTP: {remote_path}")
                        
                        # 上传成功后，备份COS中的源文件
                        try:
                            self.backup_cloud_file(filename, bucket_name, self.ccos, bucket=1)
                            self.logger.info(f"Backed up {filename} in COS")
                        except Exception as backup_error:
                            self.logger.error(f"Failed to backup {filename} in COS: {str(backup_error)}")
                            # 备份失败不影响整体流程，但记录在日志中
                        
                        # 删除临时文件
                        if temp_path and os.path.exists(temp_path):
                            os.remove(temp_path)
                            self.logger.debug(f"Removed temp file: {temp_path}")
                        
                        # 记录成功
                        result['success'].append({
                            'filename': filename,
                            'size': file_size,
                            'remote_path': remote_path
                        })
                        
                    except Exception as e:
                        self.logger.error(f"Error processing file {filename}: {str(e)}")
                        
                        # 清理临时文件
                        if temp_path and os.path.exists(temp_path):
                            try:
                                os.remove(temp_path)
                                self.logger.debug(f"Cleaned up temp file {temp_path} after error")
                            except Exception as cleanup_error:
                                self.logger.error(f"Failed to cleanup temp file {temp_path}: {str(cleanup_error)}")
                        
                        # 记录失败
                        result['failed'].append({
                            'filename': filename,
                            'reason': str(e)
                        })
                
                # 输出处理结果汇总
                success_count = len(result['success'])
                failed_count = len(result['failed'])
                self.logger.info(f"Batch upload completed. Success: {success_count}, Failed: {failed_count}")
                
            finally:
                # 关闭SFTP连接
                sftp.close()
                transport.close()
                self.logger.debug("SFTP connection closed")
                
        except Exception as e:
            self.logger.error(f"Batch upload from COS to SFTP failed: {str(e)}")
            raise CustomException(f"Batch upload from COS to SFTP failed: {str(e)}")
        
        return result

    def _create_sftp_directory(self, sftp: paramiko.SFTPClient, directory: str):
        """
        递归创建SFTP目录
        Args:
            sftp: SFTP客户端
            directory: 要创建的目录路径
        """
        try:
            sftp.listdir(directory)
            return  # 目录已存在
        except FileNotFoundError:
            pass
        
        # 获取父目录
        parent_dir = os.path.dirname(directory)
        if parent_dir != directory:  # 避免无限递归
            self._create_sftp_directory(sftp, parent_dir)
        
        try:
            sftp.mkdir(directory)
            self.logger.debug(f"Created SFTP directory: {directory}")
        except Exception as e:
            self.logger.warning(f"Failed to create SFTP directory {directory}: {str(e)}")
            # 可能目录已经存在或权限不足，继续执行