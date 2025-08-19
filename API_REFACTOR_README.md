# BPOD API 重构说明

## 重构概述

本次重构将BPOD API项目从单一文件结构重构为模块化结构，使用FastAPI最佳实践，实现了以下改进：

1. **模块化设计**：将API按功能分离到不同模块
2. **生命周期管理**：自动管理APScheduler的启动和关闭
3. **统一错误处理**：全局异常处理和日志记录
4. **健康检查**：提供系统状态监控端点
5. **API文档**：自动生成Swagger文档

## 项目结构

```
mage_python/
├── api.py                    # 主应用入口文件
├── business_api.py           # 业务API模块
├── scheduler/
│   └── scheduler.py          # 调度器模块
├── operations.py             # 业务操作逻辑
├── utils/                    # 工具模块
└── config/                   # 配置文件
```

## 主要改进

### 1. 模块化API组织

#### 业务API (`business_api.py`)
- 使用APIRouter组织业务相关的API端点
- 包含所有BPOD业务操作：post、load、output等
- 统一的错误处理和日志记录

#### 调度器API (`scheduler/scheduler.py`)
- 提供APScheduler的完整管理功能
- 支持任务的CRUD操作
- 实时状态监控和任务控制

### 2. 生命周期管理

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动启动APScheduler
    scheduler_manager.start_scheduler()
    scheduler_manager.load_jobs_from_db()
    yield
    # 关闭时自动停止APScheduler
    scheduler_manager.stop_scheduler()
```

### 3. 统一API注册

```python
# 注册业务API路由
app.include_router(business_router)

# 注册调度器API路由
scheduler_router = create_scheduler_router()
app.include_router(scheduler_router)
```

## API端点说明

### 根路径和健康检查
- `GET /` - API信息
- `GET /health` - 健康检查（包含调度器状态）

### 业务API (`/api/*`)
- `POST /api/post` - 执行Post操作
- `POST /api/load` - 执行Load操作
- `POST /api/output/post` - 生成Post输出
- `POST /api/output/alloc` - 生成Alloc输出
- `POST /api/load-post` - 执行Load-Post操作
- `POST /api/load-aging-allocate` - 执行Load-Aging-Allocate操作
- `POST /api/delete-files` - 删除文件操作

### 调度器API (`/api/scheduler/*`)
- `GET /api/scheduler/jobs` - 获取所有任务
- `POST /api/scheduler/jobs` - 创建/更新任务
- `GET /api/scheduler/jobs/{job_name}` - 获取特定任务
- `DELETE /api/scheduler/jobs/{job_name}` - 删除任务
- `POST /api/scheduler/jobs/{job_name}/enable` - 启用任务
- `POST /api/scheduler/jobs/{job_name}/disable` - 禁用任务
- `POST /api/scheduler/jobs/{job_name}/run` - 立即运行任务
- `GET /api/scheduler/status` - 获取调度器状态
- `POST /api/scheduler/reload` - 重新加载任务

## 启动方式

### 直接运行
```bash
python api.py
```

### 使用uvicorn
```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### 生产环境部署
```bash
# 使用gunicorn
gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 使用docker
docker build -t bpod-api .
docker run -p 8000:8000 bpod-api
```

## 配置说明

### 环境变量
```bash
# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bpod
DB_USER=username
DB_PASSWORD=password

# 应用配置
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
```

### 配置文件
- `config/app_config.yml` - 应用配置
- `config/database_config.yml` - 数据库配置
- `config/log_config.yml` - 日志配置

## 监控和日志

### 健康检查
```bash
curl http://localhost:8000/health
```

响应示例：
```json
{
  "status": "healthy",
  "message": "BPOD API is running",
  "timestamp": "2024-01-01T12:00:00",
  "scheduler_status": {
    "running": true,
    "initialized": true,
    "job_count": 5
  }
}
```

### 日志记录
- 请求日志：记录所有API请求和响应时间
- 错误日志：记录所有异常和错误信息
- 调度器日志：记录任务执行状态

## 最佳实践

### 1. API设计
- 使用Pydantic模型进行数据验证
- 统一的响应格式
- 详细的API文档注释

### 2. 错误处理
- 全局异常处理器
- 详细的错误信息
- 适当的HTTP状态码

### 3. 性能优化
- 异步处理
- 数据库连接池
- 请求日志记录

### 4. 安全性
- 输入验证
- SQL注入防护
- 错误信息脱敏

## 开发指南

### 添加新的API端点

1. 在`business_api.py`中添加新的路由：
```python
@business_router.post("/new-endpoint")
async def new_endpoint(request: Request, data: NewRequestModel):
    """新端点描述"""
    try:
        result = some_operation(data)
        return result
    except Exception as e:
        logger.log_error(e, request)
        raise HTTPException(status_code=500, detail=str(e))
```

2. 定义请求模型：
```python
class NewRequestModel(BaseModel):
    field1: str
    field2: int
```

### 添加新的调度任务

1. 在`scheduler/scheduler.py`中添加任务函数：
```python
def new_scheduled_job(param1: str, param2: int):
    """新的调度任务"""
    try:
        scheduler_manager.logger.info(f'执行新任务: {param1}, {param2}')
        result = some_operation(param1, param2)
        scheduler_manager.logger.info(f'任务完成: {result}')
        return result
    except Exception as e:
        scheduler_manager.logger.error(f"任务错误: {str(e)}")
        raise
```

2. 通过API创建任务：
```bash
curl -X POST "http://localhost:8000/api/scheduler/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "job_name": "new_job",
    "job_func": "new_scheduled_job",
    "trigger_type": "interval",
    "trigger_args": {"seconds": 3600},
    "job_args": ["param1", 123],
    "enabled": true
  }'
```

## 故障排除

### 常见问题

1. **调度器启动失败**
   - 检查数据库连接
   - 确认调度器表已创建
   - 查看日志文件

2. **API响应慢**
   - 检查数据库性能
   - 查看请求日志
   - 优化查询语句

3. **任务执行失败**
   - 检查任务函数是否存在
   - 查看调度器日志
   - 验证任务参数

### 调试模式

```bash
# 启用调试日志
export LOG_LEVEL=DEBUG
python api.py

# 查看详细日志
tail -f logs/bpod.log
```

## 版本历史

- v1.0.0 - 初始版本，单一文件结构
- v1.1.0 - 重构版本，模块化设计，生命周期管理

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

[项目许可证信息]
