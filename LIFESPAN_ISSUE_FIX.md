# BPOD API Lifespan 重复执行问题修复

## 问题描述

从日志中可以看到，`lifespan` 函数被执行了4次，导致调度器被重复初始化：

```
2025-08-18 14:11:29,625 - bpod_api - INFO - ✅ APScheduler已启动并加载任务
2025-08-18 14:11:29,625 - bpod_api - INFO - ✅ APScheduler已启动并加载任务
2025-08-18 14:11:29,625 - bpod_api - INFO - ✅ APScheduler已启动并加载任务
2025-08-18 14:11:29,625 - bpod_api - INFO - ✅ APScheduler已启动并加载任务
```

## 问题原因

1. **重复的lifespan函数定义**：
   - `api.py` 中定义了 `lifespan` 函数
   - `scheduler/scheduler.py` 中也定义了 `lifespan` 函数
   - 这导致了重复的初始化逻辑

2. **多个进程同时运行**：
   - 可能有多个API服务器实例在运行
   - 每个实例都会执行自己的lifespan函数

3. **多个启动入口**：
   - `api.py` 中的 `if __name__ == "__main__"`
   - `start_server.py` 中的启动脚本
   - `main.py` 中也可能启动

## 解决方案

### 1. 删除重复的lifespan函数

已删除 `scheduler/scheduler.py` 中的重复lifespan函数，只保留 `api.py` 中的完整版本。

### 2. 添加防护机制

在 `api.py` 的lifespan函数中添加了检查机制：

```python
# 检查调度器是否已经初始化，避免重复初始化
if not scheduler_manager.is_initialized:
    scheduler_manager.start_scheduler()
    scheduler_manager.load_jobs_from_db()
    logger.info("✅ APScheduler已启动并加载任务")
else:
    logger.info("✅ APScheduler已经初始化，跳过重复初始化")
```

### 3. 修复导入问题

更新了 `main.py` 中的导入，移除了对重复lifespan函数的引用。

### 4. 创建进程管理脚本

创建了 `stop_all_servers.py` 脚本来帮助停止所有正在运行的Python进程。

## 使用说明

### 停止所有服务器进程

```bash
python stop_all_servers.py
```

### 重新启动API服务器

```bash
# 方式1：直接启动
python api.py

# 方式2：使用启动脚本
python start_server.py
```

## 验证修复

启动服务器后，检查日志应该只看到一次初始化消息：

```
2025-08-18 14:11:29,625 - bpod_api - INFO - ✅ APScheduler已启动并加载任务
```

而不是之前的4次重复消息。

## 预防措施

1. **统一lifespan管理**：只在 `api.py` 中定义lifespan函数
2. **添加状态检查**：在初始化前检查是否已经初始化
3. **进程管理**：使用提供的脚本来管理服务器进程
4. **单一启动入口**：推荐使用 `start_server.py` 作为主要启动方式

## 注意事项

- 确保在重新启动服务器前停止所有现有进程
- 检查端口8000是否被占用
- 如果问题仍然存在，检查是否有其他Python脚本在运行API服务器
