"""
APScheduler module for BPOD API - Improved Version
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import json
import importlib
import traceback
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text

from utils.db_util import Database
from utils.logger import BpodLogger
from operations import execute_load_post, delete_files,execute_load_aging_allocate_sftp

class SchedulerManager:
    """调度器管理类，统一管理调度器的生命周期"""
    
    def __init__(self):
        self.scheduler: Optional[BackgroundScheduler] = None
        self.logger = BpodLogger()
        self.db = Database(logger=self.logger)
        self.is_initialized = False
        
    def init_scheduler(self) -> BackgroundScheduler:
        """初始化调度器"""
        if self.scheduler is not None:
            self.logger.warning("Scheduler already initialized")
            return self.scheduler
            
        try:
            # 创建作业存储
            job_store = SQLAlchemyJobStore(
                engine=self.db.engine, 
                tablename="apscheduler_jobs"
            )
            
            # 创建调度器
            self.scheduler = BackgroundScheduler(
                jobstores={'default': job_store},
                job_defaults={
                    'coalesce': False,
                    'max_instances': 1,
                    'misfire_grace_time': 30
                }
            )
            
            # 添加事件监听器
            self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
            self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
            
            self.logger.info("Scheduler initialized successfully")
            return self.scheduler
            
        except Exception as e:
            self.logger.error(f"Failed to initialize scheduler: {str(e)}")
            raise
    
    def start_scheduler(self):
        """启动调度器"""
        if not self.scheduler:
            self.init_scheduler()
            
        if not self.scheduler.running:
            self.scheduler.start()
            self.is_initialized = True
            self.logger.info("Scheduler started successfully")
        else:
            self.logger.warning("Scheduler is already running")
    
    def stop_scheduler(self):
        """停止调度器"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            self.is_initialized = False
            self.logger.info("Scheduler stopped successfully")
    
    def load_jobs_from_db(self):
        """从数据库加载任务"""
        if not self.is_initialized:
            self.logger.error("Scheduler not initialized, cannot load jobs")
            return
            
        try:
            # 获取所有启用的任务
            query = "SELECT * FROM sc_scheduled_jobs WHERE enabled = TRUE"
            result = self.db.execute_query_col_name(query)
            
            # 清除所有现有任务
            self.scheduler.remove_all_jobs()
            
            # 添加任务到调度器
            loaded_count = 0
            for _, row in result.iterrows():
                if self._add_job_to_scheduler(row):
                    loaded_count += 1
            
            self.logger.info(f"Successfully loaded {loaded_count} jobs from database")
            
        except Exception as e:
            self.logger.error(f"Failed to load jobs from database: {str(e)}")
            self.logger.error(traceback.format_exc())
    
    def _add_job_to_scheduler(self, job_row) -> bool:
        """将单个任务添加到调度器"""
        try:
            job_name = job_row['job_name']
            job_func_name = job_row['job_func']
            trigger_type = job_row['trigger_type']

            trigger_args = self._ensure_json_obj(job_row['trigger_args'], {})
            job_args = self._ensure_json_obj(job_row['job_args'], [])
            job_kwargs = self._ensure_json_obj(job_row['job_kwargs'], {})
            
            # 获取任务函数
            func = self._get_job_function(job_func_name)
            if not func:
                return False
            
            # 添加任务到调度器
            self.scheduler.add_job(
                func,
                id=job_name,
                trigger=trigger_type,
                **trigger_args,
                args=job_args,
                kwargs=job_kwargs,
                replace_existing=True
            )
            
            self.logger.info(f"Added job {job_name} to scheduler")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add job {job_row.get('job_name', 'unknown')}: {str(e)}")
            return False
    
    def _get_job_function(self, job_func_name: str):
        """获取任务函数"""
        # 内置任务函数映射
        builtin_functions = {
            "execute_load_post_job": execute_load_post_job,
            "execute_load_aging_allocate_job": execute_load_aging_allocate_job,
            "delete_files_job": delete_files_job
        }
        
        if job_func_name in builtin_functions:
            return builtin_functions[job_func_name]
        
        # 尝试动态导入函数
        try:
            module_name, func_name = job_func_name.rsplit('.', 1)
            module = importlib.import_module(module_name)
            return getattr(module, func_name)
        except Exception as e:
            self.logger.error(f"Failed to import job function {job_func_name}: {str(e)}")
            return None
    
    def _ensure_json_obj(self, val, default):
        """确保值是JSON对象"""
        if not val:
            return default
        return json.loads(val) if isinstance(val, str) else val
    
    def _job_error_listener(self, event):
        """任务错误监听器"""
        self.logger.error(f"Job error: {event.job_id} - {event.exception}")
        self.logger.error(traceback.format_exc())

    def _job_executed_listener(self, event):
        """任务执行监听器"""
        self.logger.info(f"Job executed: {event.job_id}")


# 全局调度器管理器实例
scheduler_manager = SchedulerManager()

# 任务函数
def execute_load_post_job(region: str, action_user: str):
    """Job function for execute_load_post"""
    try:
        scheduler_manager.logger.info(
            f'Scheduled job: Load and Post operation started. region:[{region}]. user:[{action_user}]'
        )
        result = execute_load_post(region, action_user)
        scheduler_manager.logger.info(
            f'Scheduled job: Load and Post operation completed. region:[{region}]. user:[{action_user}]'
        )
        return result
    except Exception as e:
        scheduler_manager.logger.error(f"Scheduled job error: {str(e)}")
        scheduler_manager.logger.error(traceback.format_exc())
        raise

def execute_load_aging_allocate_job(region: str, prefix: str, action_user: str):
    """Job function for execute_load_aging_allocate"""
    try:
        scheduler_manager.logger.info(
            f'Scheduled job: Load aging and allocate operation started. '
            f'region:[{region}]. prefix:[{prefix}]. user:[{action_user}]'
        )
        result = execute_load_aging_allocate_sftp(region, prefix, action_user)
        scheduler_manager.logger.info(
            f'Scheduled job: Load sftp aging and allocate operation completed. '
            f'region:[{region}]. prefix:[{prefix}]. user:[{action_user}]'
        )
        return result
    except Exception as e:
        scheduler_manager.logger.error(f"Scheduled job error: {str(e)}")
        scheduler_manager.logger.error(traceback.format_exc())
        raise

def delete_files_job(regions: str, days: int, action_user: str):
    """Job function for delete_files"""
    try:
        scheduler_manager.logger.info(
            f'Scheduled job: Delete files operation started. '
            f'regions:[{regions}]. days:[{days}]. user:[{action_user}]'
        )
        result = delete_files(regions, days, action_user)
        scheduler_manager.logger.info(
            f'Scheduled job: Delete files operation completed. '
            f'regions:[{regions}]. days:[{days}]. user:[{action_user}]'
        )
        return result
    except Exception as e:
        scheduler_manager.logger.error(f"Scheduled job error: {str(e)}")
        scheduler_manager.logger.error(traceback.format_exc())
        raise

# Pydantic 模型
class ScheduledJob(BaseModel):
    """Model for scheduled job"""
    id: Optional[int] = None
    job_name: str
    job_func: str
    trigger_type: str
    trigger_args: Dict[str, Any]
    job_args: Optional[List[Any]] = None
    job_kwargs: Optional[Dict[str, Any]] = None
    enabled: bool = True
    next_run_time: Optional[datetime] = None
    created_at: Optional[datetime] = None

class JobRequest(BaseModel):
    """Model for job request"""
    job_name: str
    job_func: str
    trigger_type: str
    trigger_args: Dict[str, Any]
    job_args: Optional[List[Any]] = None
    job_kwargs: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = True

class JobResponse(BaseModel):
    """Model for job response"""
    status: str
    message: str
    job: Optional[ScheduledJob] = None

# 注意：lifespan函数已移至api.py中统一管理
# 这里不再需要重复的lifespan函数定义

# API端点创建函数
def create_scheduler_api(app: FastAPI):
    """Create scheduler API endpoints"""
    
    @app.post("/api/scheduler/jobs", response_model=JobResponse)
    async def create_or_update_job(request: Request, job_request: JobRequest):
        """Create or update a scheduled job"""
        try:
            # 转换参数为JSON字符串
            job_args_json = json.dumps(job_request.job_args) if job_request.job_args else None
            job_kwargs_json = json.dumps(job_request.job_kwargs) if job_request.job_kwargs else None
            trigger_args_json = json.dumps(job_request.trigger_args)
            
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_request.job_name])
            
            if len(result) > 0:
                # 更新现有任务
                update_query = """
                UPDATE sc_scheduled_jobs 
                SET job_func = %s, trigger_type = %s, trigger_args = %s, 
                    job_args = %s, job_kwargs = %s, enabled = %s
                WHERE job_name = %s
                """
                scheduler_manager.db.execute_update_query(
                    update_query, 
                    [
                        job_request.job_func, 
                        job_request.trigger_type, 
                        trigger_args_json, 
                        job_args_json, 
                        job_kwargs_json, 
                        job_request.enabled, 
                        job_request.job_name
                    ]
                )
                message = f"Job {job_request.job_name} updated successfully"
            else:
                # 创建新任务
                insert_query = """
                INSERT INTO sc_scheduled_jobs 
                (job_name, job_func, trigger_type, trigger_args, job_args, job_kwargs, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                scheduler_manager.db.execute_insert_query(
                    insert_query, 
                    [
                        job_request.job_name, 
                        job_request.job_func, 
                        job_request.trigger_type, 
                        trigger_args_json, 
                        job_args_json, 
                        job_kwargs_json, 
                        job_request.enabled
                    ]
                )
                message = f"Job {job_request.job_name} created successfully"
            
            # 重新加载任务
            scheduler_manager.load_jobs_from_db()
            
            # 获取任务详情
            job_query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            job_result = scheduler_manager.db.execute_query_col_name(job_query, [job_request.job_name])
            
            job = ScheduledJob(**job_result.iloc[0].to_dict()) if len(job_result) > 0 else None
            
            return JobResponse(status="success", message=message, job=job)
            
        except Exception as e:
            scheduler_manager.logger.error(f"API error in create_or_update_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/scheduler/jobs", response_model=List[ScheduledJob])
    async def list_jobs(request: Request):
        """List all scheduled jobs"""
        try:
            query = "SELECT * FROM sc_scheduled_jobs ORDER BY created_at DESC"
            result = scheduler_manager.db.execute_query_col_name(query)
            
            jobs = [ScheduledJob(**row.to_dict()) for _, row in result.iterrows()]
            return jobs
            
        except Exception as e:
            scheduler_manager.logger.error(f"API error in list_jobs: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/scheduler/jobs/{job_name}", response_model=ScheduledJob)
    async def get_job(request: Request, job_name: str):
        """Get a specific scheduled job"""
        try:
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            return ScheduledJob(**result.iloc[0].to_dict())
            
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in get_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/scheduler/jobs/{job_name}", response_model=JobResponse)
    async def delete_job(request: Request, job_name: str):
        """Delete a scheduled job"""
        try:
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            # 从数据库删除任务
            delete_query = "DELETE FROM sc_scheduled_jobs WHERE job_name = %s"
            scheduler_manager.db.execute_update_query(delete_query, [job_name])
            
            # 从调度器移除任务
            try:
                scheduler_manager.scheduler.remove_job(job_name)
            except Exception:
                pass  # 任务可能不在调度器中
            
            return JobResponse(status="success", message=f"Job {job_name} deleted successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in delete_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/scheduler/jobs/{job_name}/enable", response_model=JobResponse)
    async def enable_job(request: Request, job_name: str):
        """Enable a scheduled job"""
        try:
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            # 更新数据库中的任务
            update_query = "UPDATE sc_scheduled_jobs SET enabled = TRUE WHERE job_name = %s"
            scheduler_manager.db.execute_update_query(update_query, [job_name])
            
            # 重新加载任务
            scheduler_manager.load_jobs_from_db()
            
            return JobResponse(status="success", message=f"Job {job_name} enabled successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in enable_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/scheduler/jobs/{job_name}/disable", response_model=JobResponse)
    async def disable_job(request: Request, job_name: str):
        """Disable a scheduled job"""
        try:
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            # 更新数据库中的任务
            update_query = "UPDATE sc_scheduled_jobs SET enabled = FALSE WHERE job_name = %s"
            scheduler_manager.db.execute_update_query(update_query, [job_name])
            
            # 从调度器移除任务
            try:
                scheduler_manager.scheduler.remove_job(job_name)
            except Exception:
                pass  # 任务可能不在调度器中
            
            return JobResponse(status="success", message=f"Job {job_name} disabled successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in disable_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/scheduler/jobs/{job_name}/run", response_model=JobResponse)
    async def run_job(request: Request, job_name: str):
        """Run a scheduled job immediately"""
        try:
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            # 立即运行任务
            job_obj = scheduler_manager.scheduler.get_job(job_name)
            if job_obj:
                job_obj.modify(next_run_time=datetime.now())
                return JobResponse(status="success", message=f"Job {job_name} scheduled to run immediately")
            else:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found in scheduler")
                
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in run_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/scheduler/status", response_model=Dict[str, Any])
    async def get_scheduler_status(request: Request):
        """Get scheduler status"""
        try:
            jobs = scheduler_manager.scheduler.get_jobs() if scheduler_manager.scheduler else []
            
            status = {
                "running": scheduler_manager.scheduler.running if scheduler_manager.scheduler else False,
                "initialized": scheduler_manager.is_initialized,
                "job_count": len(jobs),
                "jobs": [
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                        "trigger": str(job.trigger)
                    }
                    for job in jobs
                ]
            }
            
            return status
            
        except Exception as e:
            scheduler_manager.logger.error(f"API error in get_scheduler_status: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/scheduler/reload", response_model=JobResponse)
    async def reload_jobs(request: Request):
        """Reload all jobs from database"""
        try:
            scheduler_manager.load_jobs_from_db()
            return JobResponse(status="success", message="Jobs reloaded successfully")
        except Exception as e:
            scheduler_manager.logger.error(f"API error in reload_jobs: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

# 新增：创建调度器APIRouter的函数
def create_scheduler_router():
    """Create and return a scheduler APIRouter"""
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
    
    @router.post("/jobs", response_model=JobResponse)
    async def create_or_update_job(request: Request, job_request: JobRequest):
        """Create or update a scheduled job"""
        try:
            # 转换参数为JSON字符串
            job_args_json = json.dumps(job_request.job_args) if job_request.job_args else None
            job_kwargs_json = json.dumps(job_request.job_kwargs) if job_request.job_kwargs else None
            trigger_args_json = json.dumps(job_request.trigger_args)
            
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_request.job_name])
            
            if len(result) > 0:
                # 更新现有任务
                update_query = """
                UPDATE sc_scheduled_jobs 
                SET job_func = %s, trigger_type = %s, trigger_args = %s, 
                    job_args = %s, job_kwargs = %s, enabled = %s
                WHERE job_name = %s
                """
                scheduler_manager.db.execute_update_query(
                    update_query, 
                    [
                        job_request.job_func, 
                        job_request.trigger_type, 
                        trigger_args_json, 
                        job_args_json, 
                        job_kwargs_json, 
                        job_request.enabled, 
                        job_request.job_name
                    ]
                )
                message = f"Job {job_request.job_name} updated successfully"
            else:
                # 创建新任务
                insert_query = """
                INSERT INTO sc_scheduled_jobs 
                (job_name, job_func, trigger_type, trigger_args, job_args, job_kwargs, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                scheduler_manager.db.execute_insert_query(
                    insert_query, 
                    [
                        job_request.job_name, 
                        job_request.job_func, 
                        job_request.trigger_type, 
                        trigger_args_json, 
                        job_args_json, 
                        job_kwargs_json, 
                        job_request.enabled
                    ]
                )
                message = f"Job {job_request.job_name} created successfully"
            
            # 重新加载任务
            scheduler_manager.load_jobs_from_db()
            
            # 获取任务详情
            job_query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            job_result = scheduler_manager.db.execute_query_col_name(job_query, [job_request.job_name])
            
            job = ScheduledJob(**job_result.iloc[0].to_dict()) if len(job_result) > 0 else None
            
            return JobResponse(status="success", message=message, job=job)
            
        except Exception as e:
            scheduler_manager.logger.error(f"API error in create_or_update_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/jobs", response_model=List[ScheduledJob])
    async def list_jobs(request: Request):
        """List all scheduled jobs"""
        try:
            query = "SELECT * FROM sc_scheduled_jobs ORDER BY created_at DESC"
            result = scheduler_manager.db.execute_query_col_name(query)
            
            jobs = [ScheduledJob(**row.to_dict()) for _, row in result.iterrows()]
            return jobs
            
        except Exception as e:
            scheduler_manager.logger.error(f"API error in list_jobs: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/jobs/{job_name}", response_model=ScheduledJob)
    async def get_job(request: Request, job_name: str):
        """Get a specific scheduled job"""
        try:
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            return ScheduledJob(**result.iloc[0].to_dict())
            
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in get_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/jobs/{job_name}", response_model=JobResponse)
    async def delete_job(request: Request, job_name: str):
        """Delete a scheduled job"""
        try:
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            # 从数据库删除任务
            delete_query = "DELETE FROM sc_scheduled_jobs WHERE job_name = %s"
            scheduler_manager.db.execute_update_query(delete_query, [job_name])
            
            # 从调度器移除任务
            try:
                scheduler_manager.scheduler.remove_job(job_name)
            except Exception:
                pass  # 任务可能不在调度器中
            
            return JobResponse(status="success", message=f"Job {job_name} deleted successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in delete_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/jobs/{job_name}/enable", response_model=JobResponse)
    async def enable_job(request: Request, job_name: str):
        """Enable a scheduled job"""
        try:
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            # 更新数据库中的任务
            update_query = "UPDATE sc_scheduled_jobs SET enabled = TRUE WHERE job_name = %s"
            scheduler_manager.db.execute_update_query(update_query, [job_name])
            
            # 重新加载任务
            scheduler_manager.load_jobs_from_db()
            
            return JobResponse(status="success", message=f"Job {job_name} enabled successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in enable_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/jobs/{job_name}/disable", response_model=JobResponse)
    async def disable_job(request: Request, job_name: str):
        """Disable a scheduled job"""
        try:
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            # 更新数据库中的任务
            update_query = "UPDATE sc_scheduled_jobs SET enabled = FALSE WHERE job_name = %s"
            scheduler_manager.db.execute_update_query(update_query, [job_name])
            
            # 从调度器移除任务
            try:
                scheduler_manager.scheduler.remove_job(job_name)
            except Exception:
                pass  # 任务可能不在调度器中
            
            return JobResponse(status="success", message=f"Job {job_name} disabled successfully")
            
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in disable_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/jobs/{job_name}/run", response_model=JobResponse)
    async def run_job(request: Request, job_name: str):
        """Run a scheduled job immediately"""
        try:
            # 检查任务是否存在
            query = "SELECT * FROM sc_scheduled_jobs WHERE job_name = %s"
            result = scheduler_manager.db.execute_query_col_name(query, [job_name])
            
            if len(result) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
            
            # 立即运行任务
            job_obj = scheduler_manager.scheduler.get_job(job_name)
            if job_obj:
                job_obj.modify(next_run_time=datetime.now())
                return JobResponse(status="success", message=f"Job {job_name} scheduled to run immediately")
            else:
                raise HTTPException(status_code=404, detail=f"Job {job_name} not found in scheduler")
                
        except HTTPException:
            raise
        except Exception as e:
            scheduler_manager.logger.error(f"API error in run_job: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/status", response_model=Dict[str, Any])
    async def get_scheduler_status(request: Request):
        """Get scheduler status"""
        try:
            jobs = scheduler_manager.scheduler.get_jobs() if scheduler_manager.scheduler else []
            
            status = {
                "running": scheduler_manager.scheduler.running if scheduler_manager.scheduler else False,
                "initialized": scheduler_manager.is_initialized,
                "job_count": len(jobs),
                "jobs": [
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                        "trigger": str(job.trigger)
                    }
                    for job in jobs
                ]
            }
            
            return status
            
        except Exception as e:
            scheduler_manager.logger.error(f"API error in get_scheduler_status: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/reload", response_model=JobResponse)
    async def reload_jobs(request: Request):
        """Reload all jobs from database"""
        try:
            scheduler_manager.load_jobs_from_db()
            return JobResponse(status="success", message="Jobs reloaded successfully")
        except Exception as e:
            scheduler_manager.logger.error(f"API error in reload_jobs: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return router

# 向后兼容的函数
def init_scheduler():
    """向后兼容：初始化调度器"""
    return scheduler_manager.init_scheduler()

def load_jobs_from_db():
    """向后兼容：从数据库加载任务"""
    return scheduler_manager.load_jobs_from_db()

# 获取调度器实例
def get_scheduler():
    """获取调度器实例"""
    return scheduler_manager.scheduler