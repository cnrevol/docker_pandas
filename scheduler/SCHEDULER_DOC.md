# BPOD Scheduler 模块文档

## 1. 技术实现

### 1.1 核心组件
- 使用 `APScheduler` 作为调度引擎
- 基于 `SQLAlchemy` 的持久化存储
- 集成到 FastAPI 框架中

### 1.2 主要功能
- 定时任务管理
- 任务执行状态追踪
- 任务立即执行
- 任务启用/禁用控制

## 2. 数据库表定义

### 2.1 sc_scheduled_jobs 表
```sql
CREATE TABLE sc_scheduled_jobs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(255) UNIQUE NOT NULL,
    job_func VARCHAR(255) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,
    trigger_args JSONB NOT NULL,
    job_args JSONB,
    job_kwargs JSONB,
    enabled BOOLEAN DEFAULT TRUE,
    next_run_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 sc_job_executions 表
```sql
CREATE TABLE sc_job_executions (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES sc_scheduled_jobs(id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 3. 业务处理

### 3.1 支持的业务操作
1. 加载数据文件和入账操作
   - 函数: `execute_load_post`
   - 参数: region, action_user

2. 加载账龄数据文件、和销账操作
   - 函数: `execute_load_aging_allocate`
   - 参数: region, prefix, action_user

3. 文件删除操作
   - 函数: `delete_files`
   - 参数: regions, days, action_user

### 3.2 触发器类型
- Cron: 基于时间表达式的调度
- Interval: 固定时间间隔的调度
- Date: 指定具体时间的调度

## 4. Web API 接口

### 4.1 任务管理
- `POST /api/scheduler/jobs`: 创建或更新任务
- `GET /api/scheduler/jobs`: 获取所有任务列表
- `GET /api/scheduler/jobs/{job_name}`: 获取特定任务详情
- `DELETE /api/scheduler/jobs/{job_name}`: 删除任务

### 4.2 任务控制
- `POST /api/scheduler/jobs/{job_name}/enable`: 启用任务
- `POST /api/scheduler/jobs/{job_name}/disable`: 禁用任务
- `POST /api/scheduler/jobs/{job_name}/run`: 立即执行任务

### 4.3 状态查询
- `GET /api/scheduler/status`: 获取调度器状态

## 5. 使用示例

### 5.1 创建定时任务
```json
{
    "job_name": "daily_load_post",
    "job_func": "execute_load_post_job",
    "trigger_type": "cron",
    "trigger_args": {
        "hour": "0",
        "minute": "0"
    },
    "job_args": ["IN", "system"],
    "enabled": true
}
```

### 5.2 创建间隔任务
```json
{
    "job_name": "hourly_file_cleanup",
    "job_func": "delete_files_job",
    "trigger_type": "interval",
    "trigger_args": {
        "hours": 1
    },
    "job_args": ["IN,US", 7, "system"],
    "enabled": true
}
``` 