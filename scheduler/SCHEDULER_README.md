# BPOD API Scheduler Module

This module provides scheduling functionality for the BPOD API using APScheduler. It allows you to schedule and manage the following operations:

1. `execute_load_post` - Load files and perform posting for a region
2. `execute_load_aging_allocate` - Load aging data and perform allocation for a region
3. `delete_files` - Delete files older than a specified number of days

## Database Setup

Before using the scheduler, you need to create the necessary database tables. Run the `scheduler_tables.sql` script to create the tables:

```bash
psql -U your_username -d your_database -f scheduler_tables.sql
```

This will create the following tables:
- `sc_scheduled_jobs` - Stores job configurations
- `sc_job_executions` - Logs job execution history

## API Endpoints

The scheduler module provides the following API endpoints:

### Job Management

- `POST /api/scheduler/jobs` - Create or update a scheduled job
- `GET /api/scheduler/jobs` - List all scheduled jobs
- `GET /api/scheduler/jobs/{job_name}` - Get a specific scheduled job
- `DELETE /api/scheduler/jobs/{job_name}` - Delete a scheduled job
- `POST /api/scheduler/jobs/{job_name}/enable` - Enable a scheduled job
- `POST /api/scheduler/jobs/{job_name}/disable` - Disable a scheduled job
- `POST /api/scheduler/jobs/{job_name}/run` - Run a scheduled job immediately
- `GET /api/scheduler/status` - Get scheduler status

## Job Configuration

Jobs are configured using the following parameters:

- `job_name` - Unique identifier for the job
- `job_func` - Function to execute (e.g., `execute_load_post_job`)
- `trigger_type` - Type of trigger (`cron`, `interval`, or `date`)
- `trigger_args` - Arguments for the trigger (e.g., `{"hour": 8, "minute": 0}` for a cron trigger)
- `job_args` - Positional arguments for the job function
- `job_kwargs` - Keyword arguments for the job function
- `enabled` - Whether the job is enabled

## Example Job Configurations

### Load and Post Job

```json
{
  "job_name": "load_post_MY",
  "job_func": "execute_load_post_job",
  "trigger_type": "cron",
  "trigger_args": {
    "hour": 8,
    "minute": 0
  },
  "job_args": ["MY"],
  "job_kwargs": {
    "action_user": "scheduler"
  },
  "enabled": true
}
```

### Load Aging and Allocate Job

```json
{
  "job_name": "load_aging_allocate_MY",
  "job_func": "execute_load_aging_allocate_job",
  "trigger_type": "cron",
  "trigger_args": {
    "hour": 9,
    "minute": 0
  },
  "job_args": ["MY"],
  "job_kwargs": {
    "prefix": "MY MBB",
    "action_user": "scheduler"
  },
  "enabled": true
}
```

### Delete Files Job

```json
{
  "job_name": "delete_files",
  "job_func": "delete_files_job",
  "trigger_type": "cron",
  "trigger_args": {
    "day_of_week": "mon",
    "hour": 1,
    "minute": 0
  },
  "job_args": ["MY,SG,ID"],
  "job_kwargs": {
    "days": 30,
    "action_user": "scheduler"
  },
  "enabled": true
}
```

## Trigger Types

### Cron Trigger

The cron trigger allows you to schedule jobs based on a cron expression. The following fields are supported:

- `year` - 4-digit year
- `month` - 1-12
- `day` - 1-31
- `week` - 0-53
- `day_of_week` - 0-6 or mon,tue,wed,thu,fri,sat,sun
- `hour` - 0-23
- `minute` - 0-59
- `second` - 0-59

Example:
```json
{
  "hour": 8,
  "minute": 0
}
```

### Interval Trigger

The interval trigger allows you to schedule jobs at fixed intervals. The following fields are supported:

- `weeks` - Number of weeks
- `days` - Number of days
- `hours` - Number of hours
- `minutes` - Number of minutes
- `seconds` - Number of seconds

Example:
```json
{
  "hours": 1
}
```

### Date Trigger

The date trigger allows you to schedule jobs at a specific date and time.

Example:
```json
{
  "run_date": "2023-12-31T23:59:59"
}
```

## Logging

The scheduler module uses the same logging system as the rest of the API. Job executions are logged to the `sc_job_executions` table and to the log files.

## Error Handling

If a job fails, the error is logged to the `sc_job_executions` table and to the log files. The job will continue to run according to its schedule.

## Integration with Existing API

The scheduler module is integrated with the existing API. When the API starts, the scheduler is initialized and jobs are loaded from the database.

## Sample Jobs

The `scheduler_tables.sql` script includes sample jobs for the three required functions:

1. `load_post_MY` - Runs at 8:00 AM every day to load and post data for the MY region
2. `load_post_SG` - Runs at 8:30 AM every day to load and post data for the SG region
3. `load_aging_allocate_MY` - Runs at 9:00 AM every day to load aging data and perform allocation for the MY region
4. `delete_files` - Runs at 1:00 AM every Monday to delete files older than 30 days for the MY, SG, and ID regions 