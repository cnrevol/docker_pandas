-- Create sc_scheduled_jobs table
CREATE TABLE IF NOT EXISTS sc_scheduled_jobs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL UNIQUE,  -- 任务名称（唯一标识）
    job_func VARCHAR(100) NOT NULL,         -- 任务函数名（如 "module.function"）
    trigger_type VARCHAR(20) NOT NULL,      -- 触发器类型（'cron'/'interval'/'date'）
    trigger_args JSON NOT NULL,             -- 触发器参数（如 cron表达式、间隔时间）
    job_args JSON,                          -- 任务参数（传递给函数的参数）
    job_kwargs JSON,                        -- 任务关键字参数
    enabled BOOLEAN DEFAULT TRUE,           -- 是否启用
    next_run_time TIMESTAMP,                -- 下次运行时间（自动更新）
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create sc_job_executions table for logging job executions
CREATE TABLE IF NOT EXISTS sc_job_executions (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,         -- 任务名称
    start_time TIMESTAMP NOT NULL,          -- 开始时间
    end_time TIMESTAMP,                     -- 结束时间
    status VARCHAR(20) NOT NULL,            -- 状态（'success'/'error'）
    result TEXT,                            -- 结果
    error_message TEXT,                     -- 错误信息
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create index on job_name for faster lookups
CREATE INDEX IF NOT EXISTS idx_sc_scheduled_jobs_job_name ON sc_scheduled_jobs(job_name);
CREATE INDEX IF NOT EXISTS idx_sc_job_executions_job_name ON sc_job_executions(job_name);

-- Insert sample jobs for the three required functions
INSERT INTO sc_scheduled_jobs (job_name, job_func, trigger_type, trigger_args, job_args, job_kwargs, enabled)
VALUES 
    ('load_post_MY', 'execute_load_post_job', 'cron', '{"hour": 8, "minute": 0}', '["MY"]', '{"action_user": "scheduler"}', true),
    ('load_post_SG', 'execute_load_post_job', 'cron', '{"hour": 8, "minute": 30}', '["SG"]', '{"action_user": "scheduler"}', true),
    ('load_aging_allocate_MY', 'execute_load_aging_allocate_job', 'cron', '{"hour": 9, "minute": 0}', '["MY"]', '{"prefix": "MY MBB", "action_user": "scheduler"}', true),
    ('delete_files', 'delete_files_job', 'cron', '{"day_of_week": "mon", "hour": 1, "minute": 0}', '["MY,SG,ID"]', '{"days": 30, "action_user": "scheduler"}', true)
ON CONFLICT (job_name) DO NOTHING; 