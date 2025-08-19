"""
Example script demonstrating how to use the BPOD API Scheduler Module
"""

# import requests
# import json
# import time

# # Base URL for the API
# BASE_URL = "http://localhost:8000"

# def create_load_post_job():
#     """Create a load and post job for MY region"""
#     url = f"{BASE_URL}/api/scheduler/jobs"
    
#     # Job configuration
#     job_config = {
#         "job_name": "load_post_MY_example",
#         "job_func": "execute_load_post_job",
#         "trigger_type": "cron",
#         "trigger_args": {
#             "hour": 10,
#             "minute": 0
#         },
#         "job_args": ["MY"],
#         "job_kwargs": {
#             "action_user": "example_user"
#         },
#         "enabled": True
#     }
    
#     # Send request to create job
#     response = requests.post(url, json=job_config)
#     print(f"Create job response: {response.status_code}")
#     print(json.dumps(response.json(), indent=2))
    
#     return response.json()

# def list_jobs():
#     """List all scheduled jobs"""
#     url = f"{BASE_URL}/api/scheduler/jobs"
    
#     # Send request to list jobs
#     response = requests.get(url)
#     print(f"List jobs response: {response.status_code}")
#     print(json.dumps(response.json(), indent=2))
    
#     return response.json()

# def run_job(job_name):
#     """Run a job immediately"""
#     url = f"{BASE_URL}/api/scheduler/jobs/{job_name}/run"
    
#     # Send request to run job
#     response = requests.post(url)
#     print(f"Run job response: {response.status_code}")
#     print(json.dumps(response.json(), indent=2))
    
#     return response.json()

# def get_scheduler_status():
#     """Get scheduler status"""
#     url = f"{BASE_URL}/api/scheduler/status"
    
#     # Send request to get status
#     response = requests.get(url)
#     print(f"Status response: {response.status_code}")
#     print(json.dumps(response.json(), indent=2))
    
#     return response.json()

# if __name__ == "__main__":
#     # Create a job
#     job = create_load_post_job()
    
#     # List all jobs
#     jobs = list_jobs()
    
#     # Get scheduler status
#     status = get_scheduler_status()
    
#     # Run the job immediately
#     if job.get("job", {}).get("job_name"):
#         run_job(job["job"]["job_name"])
    
#     print("Example completed successfully!") 





