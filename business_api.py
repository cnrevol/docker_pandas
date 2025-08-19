"""
Business API module for BPOD operations
使用APIRouter方式组织业务API
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any
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
class PostRequest(BaseModel):
    region: str
    action_user: str

class LoadRequest(BaseModel):
    region: str
    action_user: str
    files: str

class OutputRequest(BaseModel):
    region: str
    action_user: str

class LoadPostRequest(BaseModel):
    region: str
    action_user: str

class LoadAgingAllocateRequest(BaseModel):
    region: str
    action_user: str
    prefix: str

class DeleteFilesRequest(BaseModel):
    regions: str
    days: int
    action_user: str

# ========== Create Business API Router ==========
business_router = APIRouter(prefix="/api", tags=["business"])

# ========== Business API Endpoints ==========
@business_router.post("/post")
async def api_execute_post(request: Request, post_request: PostRequest):
    """执行Post操作"""
    try:
        result = execute_post(post_request.region, post_request.action_user)
        return result
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

@business_router.post("/load")
async def api_execute_load(request: Request, load_request: LoadRequest):
    """执行Load操作"""
    try:
        result = execute_load(load_request.region, load_request.files, load_request.action_user)
        return result
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

@business_router.post("/output/post")
async def api_generate_post_output(request: Request, output_request: OutputRequest):
    """生成Post输出"""
    try:
        result = generate_post_output(output_request.region, output_request.action_user)
        return result
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))

@business_router.post("/output/alloc")
async def api_generate_alloc_output(request: Request, output_request: OutputRequest):
    """生成Alloc输出"""
    try:
        result = generate_alloc_output(output_request.region, output_request.action_user)
        return result
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
async def api_execute_load_aging_allocate(request: Request, load_aging_allocate_request: LoadAgingAllocateRequest):
    """执行Load-Aging-Allocate操作"""
    try:
        result = execute_load_aging_allocate(
            load_aging_allocate_request.region,
            load_aging_allocate_request.prefix,
            load_aging_allocate_request.action_user
        )
        return result
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
