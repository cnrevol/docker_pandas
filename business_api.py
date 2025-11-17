"""
Business API module for BPOD operations
使用APIRouter方式组织业务API
"""

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from utils.logger import BpodLogger
from operations import (
    execute_post, 
    execute_load, 
    generate_post_output, 
    generate_alloc_output, 
    execute_load_post, 
    execute_load_aging_allocate, 
    delete_files
)

# Initialize logger
logger = BpodLogger()

# ========== Pydantic Models ==========
    # private String region;
    # private String bank;
    # private String currency;
    # private String file_prefix;
    # private String file_action;
    # private String file_name;
    # private String action_user;
    # private List<String> files;
# class PostRequest(BaseModel):
#     bank: Optional[str] = None
#     currency: Optional[str] = None
#     file_prefix: Optional[str] = None
#     file_action: Optional[str] = None
#     file_name: Optional[str] = None
#     region: Optional[str] = None
#     action_user: str

# class LoadRequest(BaseModel):
#     bank: Optional[str] = None
#     currency: Optional[str] = None
#     file_prefix: Optional[str] = None
#     file_action: Optional[str] = None
#     file_name: Optional[str] = None
#     region: Optional[str] = None
#     action_user: str
#     files: Optional[List[str]]= None

# class OutputRequest(BaseModel):
#     bank: Optional[str] = None
#     currency: Optional[str] = None
#     file_prefix: Optional[str] = None
#     file_action: Optional[str] = None
#     file_name: Optional[str] = None
#     region: Optional[str] = None
#     action_user: str

class LoadPostRequest(BaseModel):
    bank: Optional[str] = None
    currency: Optional[str] = None
    file_prefix: Optional[str] = None
    file_action: Optional[str] = None
    file_name: Optional[str] = None
    region: Optional[str] = None
    action_user: str

# class LoadAgingAllocateRequest(BaseModel):
#     bank: Optional[str] = None
#     currency: Optional[str] = None
#     file_prefix: Optional[str] = None
#     file_action: Optional[str] = None
#     file_name: Optional[str] = None
#     region: Optional[str] = None
#     action_user: str
#     prefix: Optional[str] = None

class Variables(BaseModel):
    region: Optional[str] = None
    bank: Optional[str] = None
    currency: Optional[str] = None
    file_prefix: Optional[str] = None
    file_action: Optional[str] = None
    file_name: Optional[str] = None
    files: Optional[List[str]] = None
    action_user: str

class PipelineRun(BaseModel):
    variables: Variables

class PipelineRequest(BaseModel):
    pipeline_run: PipelineRun

class DeleteFilesRequest(BaseModel):
    bank: Optional[str] = None
    currency: Optional[str] = None
    file_prefix: Optional[str] = None
    file_action: Optional[str] = None
    file_name: Optional[str] = None
    regions: Optional[str] = None
    days: Optional[int] = None
    action_user: str

# ========== Create Business API Router ==========
business_router = APIRouter(prefix="/api", tags=["business"])

# ========== Business API Endpoints ==========
@business_router.post("/post")
async def api_execute_post(request: Request,pipeline_request: PipelineRequest,background_tasks: BackgroundTasks):
    """执行Post操作"""
    try:
        post_request  = pipeline_request.pipeline_run.variables
        # 异步执行，不阻塞返回
        background_tasks.add_task(
            execute_post,
            post_request.region,
            post_request.action_user
        )
        # 立即返回
        return {
            "status": "started",
            "message": f"Post task started for region {post_request.region}"
        }

        # result = execute_post(post_request.region, post_request.action_user)
        # return result
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

@business_router.post("/load")
async def api_execute_load(request: Request, pipeline_request: PipelineRequest,background_tasks: BackgroundTasks):
    """执行Load操作"""
    try:
        load_request = pipeline_request.pipeline_run.variables
        # result = execute_load(load_request.region, load_request.files, load_request.action_user)
        background_tasks.add_task(
            execute_load,
            load_request.region,
            load_request.files,
            load_request.action_user
        )
        return {"status": "started", "message": f"Files load started for region {load_request.region}"}

        return result
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

@business_router.post("/output/post")
async def api_generate_post_output(request: Request, pipeline_request: PipelineRequest,background_tasks: BackgroundTasks):
    """生成Post输出"""
    try:
        output_request = pipeline_request.pipeline_run.variables
        # result = generate_post_output(output_request.region, output_request.action_user)
        # return result
        background_tasks.add_task(
            generate_post_output,
            output_request.region,
            output_request.action_user
        )
        return {"status": "started", "message": f"Posting output files started for region {output_request.region}"}
    
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

@business_router.post("/output/alloc")
async def api_generate_alloc_output(request: Request, pipeline_request: PipelineRequest,background_tasks: BackgroundTasks):
    """生成Alloc输出"""
    try:
        output_request = pipeline_request.pipeline_run.variables

        # result = generate_alloc_output(output_request.region, output_request.action_user)
        # return result
        background_tasks.add_task(
            generate_alloc_output,
            output_request.region,
            output_request.action_user
        )
        return {"status": "started", "message": f"Allocation output files started for region {output_request.region}"}
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

@business_router.post("/load-post")
async def api_execute_load_post(request: Request, load_post_request: LoadPostRequest):
    """执行Load-Post操作"""
    try:
        result = execute_load_post(load_post_request.region, load_post_request.action_user)
        return result
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

@business_router.post("/load-aging-allocate")
async def api_execute_load_aging_allocate(request: Request, pipeline_request: PipelineRequest,background_tasks: BackgroundTasks):
    """执行Load-Aging-Allocate操作"""
    try:
        load_aging_allocate_request= pipeline_request.pipeline_run.variables

        # 提交后台任务
        background_tasks.add_task(
            execute_load_aging_allocate,
            load_aging_allocate_request.region,
            load_aging_allocate_request.file_prefix,
            load_aging_allocate_request.action_user
        )
        # 立即返回
        return {
            "status": "started",
            "message": f"Load aging and allocate operations started for region {load_aging_allocate_request.region}, "
                       f"prefix {load_aging_allocate_request.file_prefix}"
        }
    
        # result = execute_load_aging_allocate(
        #     load_aging_allocate_request.region,
        #     load_aging_allocate_request.file_prefix,
        #     load_aging_allocate_request.action_user
        # )
        # return result
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

@business_router.post("/delete-files")
async def api_delete_files(request: Request, delete_files_request: DeleteFilesRequest):
    """删除文件操作"""
    try:
        result = delete_files(
            delete_files_request.regions,
            delete_files_request.days,
            delete_files_request.action_user
        )
        return result
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

# ========== Export Models for Main App ==========
# 导出模型供主应用使用
__all__ = [
    "business_router",
    "PostRequest",
    "LoadRequest", 
    "OutputRequest",
    "LoadPostRequest",
    "LoadAgingAllocateRequest",
    "DeleteFilesRequest"
]
