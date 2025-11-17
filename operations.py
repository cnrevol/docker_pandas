"""
Shared business logic for BPOD operations
"""
from typing import Dict, Any, List
from utils.logger import BpodLogger
from load_common import LoadAction
from post_common import PostAction
from post_india import PostActionIndia
from excute_common import ExecuteAction
from utils.file_util import FileUtil
from load_control import LoadControl
from output_common import OutputFileAction
from utils.db_util import Database

logger = BpodLogger()

def get_file_prefixes(region: str, is_post_file: str, log: BpodLogger) -> List[str]:
    """Fetch file prefixes from sc_raw_file_define by region and is_post_file flag."""
    try:
        db = Database(logger=log)
        query = (
            "SELECT file_prefix "
            "FROM sc_raw_file_define "
            "WHERE otc_region = %s AND is_post_file = %s"
        )
        params = (region, is_post_file)  # 按顺序对应 %s 占位符
        df = db.execute_query_to_pandas(query, params)

        prefixes = df["file_prefix"].dropna().astype(str).tolist() if (df is not None and not df.empty) else []
        log.info(f"Fetched {len(prefixes)} prefixes for region {region}, is_post_file {is_post_file}")
        return prefixes
    except Exception as e:
        log.error(f"Failed to fetch prefixes: {e}")
        return []

def execute_post(region: str, action_user: str) -> Dict[str, Any]:
    """Execute posting operation for a region"""
    logger.info(f'Post match Start Block. region:[{region}]')
    post_action = PostAction('Post Action', logger)
    post_action.excute_region_posting(region, action_user)
    return {"status": "success", "message": f"Posting completed for region {region}"}

def execute_load(region: str, files: List[str], action_user: str) -> Dict[str, Any]:
    """Execute loading operation for files in a region"""
    file_list = files
    
    logger.info(f'File check action block. region:{region}. file_list: {file_list}. user:{action_user}')
    load_control = LoadControl(logger)
    
    checker_flag = "yes"
    for file_pre in file_list:
        ret = load_control.check_file_can_load(file_pre, region)
        if not ret:
            checker_flag = "no"
            break
    
    logger.info(f"File check return flag: {checker_flag}")
    
    if checker_flag == "yes":
        # If all files can be loaded, proceed with loading
        load_action = LoadAction('Load Action', '', region, logger)
        for file_pre in file_list:
            logger.info(f"Loading file: {file_pre}")
            load_action.read_pfile_to_table(region, file_pre, action_user=action_user)
        
        return {"status": "success", "message": f"Files loaded successfully for region {region}"}
    else:
        return {"status": "error", "message": f"One or more files cannot be loaded for region {region}"}

def generate_post_output(region: str, action_user: str) -> Dict[str, Any]:
    """Generate posting output files for a region"""
    logger.info(f'Generating posting output files. region:[{region}]')
    output_action = OutputFileAction('Post action', logger)
    output_action.output_post_data(region, action_user)
    file_util = FileUtil(state = None, logger=logger)
    result = file_util.upload_all_cos_to_sftp('ifp-post', 'ifp')
    logger.debug(result)
    
    return {"status": "success", "message": f"Posting output files generated for region {region}"}

def generate_alloc_output(region: str, action_user: str) -> Dict[str, Any]:
    """Generate allocation output files for a region"""
    logger.info(f'Generating allocation output files. region:[{region}]')
    output_action = OutputFileAction('Post action', logger)
    output_action.output_alloc_data(region, action_user)
    file_util = FileUtil(state = None, logger=logger)
    result = file_util.upload_all_cos_to_sftp('ifp-post', 'ifp')
    logger.debug(result)
        
    return {"status": "success", "message": f"Allocation output files generated for region {region}"}

def execute_load_post(region: str, action_user: str) -> Dict[str, Any]:
    """Execute sftp load and post operation for a region"""
    logger.info(f'Load and Post sftp operation started. region:[{region}]. user:[{action_user}]')
    
    prefixes = get_file_prefixes(region=region, is_post_file='1', log=logger)
    logger.debug(f"Using prefixes for SFTP download: {prefixes}")

    file_util = FileUtil(state = None, logger=logger)
    result = file_util.download_sftp_to_cos(region=region, user_type='ifp', prefixes=prefixes)
    logger.info(result)
    if len(result['failed']) > 0:
        logger.error('Download from SFTP server Failed. ')
        return {
            "status": "Failed", 
            "message": f"Load and Post sftp operation completed failed for region {region},user:[{action_user}]"
        }
    
    # Load all files for the region
    load_action = LoadAction(region, '', region, logger)
    bank_data = load_action.read_region_all_file(action_user=action_user)
    
    logger.info(f'Load operation sftp completed. region:[{region}]. user:[{action_user}]. bank_data:[{bank_data}]')
    
    # If there has bank data, do the post match
    if bank_data > 0:
        # Use PostActionIndia for India region, otherwise use PostAction
        if region == "IN":
            action = PostActionIndia('Common post action', logger)
        else:
            action = PostAction('Common post action', logger)
        
        action.excute_region_posting(region, action_user=action_user)
        logger.info(f'Posting operation completed. region:[{region}]. user:[{action_user}]')
        
        return {
            "status": "success", 
            "message": f"Load and post operations completed for region {region}",
            "bank_data": bank_data
        }
    else:
        logger.info(f'No bank data, posting skipped. region:[{region}]. user:[{action_user}]')
        return {
            "status": "success", 
            "message": f"No bank data found for region {region}, posting skipped",
            "bank_data": bank_data
        }


def execute_load_aging_allocate_sftp(region: str, prefix: str, action_user: str) -> Dict[str, Any]:
    """Execute load sftp aging and allocate operation for a region"""
    logger.info(f'Load SFTP aging and allocate operation started. region:[{region}]. prefix:[{prefix}]. user:[{action_user}]')
    
    prefixes = get_file_prefixes(region=region, is_post_file='3', log=logger)
    logger.debug(f"Using prefixes for SFTP download: {prefixes}")

    file_util = FileUtil(state = None, logger=logger)
    result = file_util.download_sftp_to_cos(region=region, user_type='ifp', prefixes=prefixes)
    logger.info(result)
    if len(result['failed']) > 0:
        logger.error('Download from SFTP server Failed. ')
        return {
            "status": "Failed", 
            "message": f"Load SFTP aging and allocate operations completed for region {region}, prefix {prefix}"
        }
    
    # Execute load aging and allocate operation
    execute_action = ExecuteAction(logger)
    execute_action.exec_load_aging_allocate(region, prefix, action_user)
    
    logger.info(f'Load sftp aging and allocate operation completed. region:[{region}]. prefix:[{prefix}]. user:[{action_user}]')
    
    return {
        "status": "success", 
        "message": f"Load aging and allocate operations completed for region {region}, prefix {prefix}"
    }

def execute_load_aging_allocate(region: str, prefix: str, action_user: str) -> Dict[str, Any]:
    """Execute load aging and allocate operation for a region"""
    logger.info(f'Load aging and allocate operation started. region:[{region}]. prefix:[{prefix}]. user:[{action_user}]')
    
    # Execute load aging and allocate operation
    execute_action = ExecuteAction(logger)
    execute_action.exec_load_aging_allocate(region, prefix, action_user)
    
    logger.info(f'Load aging and allocate operation completed. region:[{region}]. prefix:[{prefix}]. user:[{action_user}]')
    
    return {
        "status": "success", 
        "message": f"Load aging and allocate operations completed for region {region}, prefix {prefix}"
    }

def delete_files(regions: str, days: int, action_user: str) -> Dict[str, Any]:
    """Delete files older than specified days for given regions"""
    logger.debug(f"Delete bucket files regions:{regions}. days:{days}")
    file_util = FileUtil(logger=logger)
    
    deleted_regions = []
    for region in regions.split(','):
        logger.debug(f"Delete region: {region}")
        file_util.del_cos_files_before_days(region, days)
        deleted_regions.append(region)
        logger.info(f"Delete bucket files region: {region} finished.")
    
    return {
        "status": "success", 
        "message": f"Files older than {days} days deleted for regions: {', '.join(deleted_regions)}"
    } 