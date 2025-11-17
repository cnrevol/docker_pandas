from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import traceback
import json
from datetime import datetime
from contextlib import asynccontextmanager
import uvicorn
import time
from dotenv import load_dotenv

from utils.logger import BpodLogger
from utils.db_util import Database
from post_common import PostAction
from post_india import PostActionIndia
from load_control import LoadControl
from load_common import LoadAction
from output_common import OutputFileAction
from excute_common import ExecuteAction
from utils.file_util import FileUtil

# Import scheduler module and business API
from scheduler import create_scheduler_router, scheduler_manager
from business_api import business_router

# Initialize logger
logger = BpodLogger()

load_dotenv()

# ========== Pydantic Models ==========
class HealthResponse(BaseModel):
    status: str
    message: str
    timestamp: datetime
    scheduler_status: Dict[str, Any]

# ========== FastAPI Lifecycle Management ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI应用生命周期管理"""
    # 启动时
    logger.info("🚀 启动BPOD API应用...")
    try:
        # 检查调度器是否已经初始化，避免重复初始化
        if not scheduler_manager.is_initialized:
            scheduler_manager.start_scheduler()
            scheduler_manager.load_jobs_from_db()
            logger.info("✅ APScheduler已启动并加载任务")
        else:
            logger.info("✅ APScheduler已经初始化，跳过重复初始化")
    except Exception as e:
        logger.error(f"❌ 启动APScheduler失败: {str(e)}")
        raise
    
    logger.info("✅ 所有服务已启动")
    yield
    
    # 关闭时
    logger.info("🛑 关闭BPOD API应用...")
    try:
        if scheduler_manager.is_initialized:
            scheduler_manager.stop_scheduler()
            logger.info("✅ APScheduler已停止")
        else:
            logger.info("✅ APScheduler未初始化，无需停止")
    except Exception as e:
        logger.error(f"❌ 停止APScheduler失败: {str(e)}")
    
    logger.info("✅ 所有服务已关闭")

# ========== Create FastAPI App ==========
app = FastAPI(
    title="BPOD API",
    description="API for BPOD operations with APScheduler integration",
    version="1.0.0",
    lifespan=lifespan
)

# ========== Middleware ==========
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response_time = time.time() - start_time
    logger.log_request(request, response_time)
    return response

# ========== Exception Handler ==========
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.log_error(exc, request)
    return {"status": "error", "message": str(exc)}

# ========== Root and Health Check Endpoints ==========
@app.get("/", tags=["root"])
async def root():
    """根路径 - API信息"""
    return {
        "message": "BPOD API Server",
        "version": "1.0.0",
        "description": "API for BPOD operations with APScheduler integration",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """健康检查端点"""
    try:
        # 获取调度器状态
        scheduler_status = {
            "running": scheduler_manager.scheduler.running if scheduler_manager.scheduler else False,
            "initialized": scheduler_manager.is_initialized,
            "job_count": len(scheduler_manager.scheduler.get_jobs()) if scheduler_manager.scheduler else 0
        }
        
        return HealthResponse(
            status="healthy",
            message="BPOD API is running",
            timestamp=datetime.now(),
            scheduler_status=scheduler_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")

# ========== Register API Routers ==========
# 注册业务API路由
app.include_router(business_router)

# 注册调度器API路由
scheduler_router = create_scheduler_router()
app.include_router(scheduler_router)

# ========== Application Entry Point ==========
if __name__ == "__main__":
    logger.info("启动BPOD API服务器...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    ) 