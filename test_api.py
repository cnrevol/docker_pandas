#!/usr/bin/env python3
"""
BPOD API 测试脚本
用于验证API端点是否正常工作
"""

import requests
import json
import sys
from datetime import datetime

# API基础URL
BASE_URL = "http://localhost:8000"

def test_root_endpoint():
    """测试根路径端点"""
    print("🔍 测试根路径端点...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 根路径测试成功: {data.get('message', 'N/A')}")
            return True
        else:
            print(f"❌ 根路径测试失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 根路径测试异常: {e}")
        return False

def test_health_endpoint():
    """测试健康检查端点"""
    print("🔍 测试健康检查端点...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 健康检查测试成功: {data.get('status', 'N/A')}")
            print(f"   调度器状态: {data.get('scheduler_status', {})}")
            return True
        else:
            print(f"❌ 健康检查测试失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 健康检查测试异常: {e}")
        return False

def test_load_get_endpoint():
    """测试Load GET端点"""
    print("🔍 测试Load GET端点...")
    try:
        response = requests.get(f"{BASE_URL}/api/load?region=test&action_user=test_user")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Load GET测试成功: {data.get('message', 'N/A')}")
            return True
        else:
            print(f"❌ Load GET测试失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Load GET测试异常: {e}")
        return False

def test_load_post_endpoint():
    """测试Load POST端点"""
    print("🔍 测试Load POST端点...")
    try:
        payload = {
            "region": "test_region",
            "action_user": "test_user",
            "files": "test_files"
        }
        response = requests.post(
            f"{BASE_URL}/api/load",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Load POST测试成功")
            return True
        else:
            print(f"❌ Load POST测试失败: {response.status_code}")
            print(f"   响应内容: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Load POST测试异常: {e}")
        return False

def test_scheduler_status():
    """测试调度器状态端点"""
    print("🔍 测试调度器状态端点...")
    try:
        response = requests.get(f"{BASE_URL}/api/scheduler/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 调度器状态测试成功")
            print(f"   运行状态: {data.get('running', False)}")
            print(f"   任务数量: {data.get('job_count', 0)}")
            return True
        else:
            print(f"❌ 调度器状态测试失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 调度器状态测试异常: {e}")
        return False

def test_scheduler_jobs():
    """测试调度器任务列表端点"""
    print("🔍 测试调度器任务列表端点...")
    try:
        response = requests.get(f"{BASE_URL}/api/scheduler/jobs")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 调度器任务列表测试成功")
            print(f"   任务数量: {len(data)}")
            return True
        else:
            print(f"❌ 调度器任务列表测试失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 调度器任务列表测试异常: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始BPOD API测试...")
    print(f"   测试时间: {datetime.now()}")
    print(f"   目标URL: {BASE_URL}")
    print("-" * 50)
    
    # 测试结果统计
    total_tests = 6
    passed_tests = 0
    
    # 执行测试
    tests = [
        test_root_endpoint,
        test_health_endpoint,
        test_load_get_endpoint,
        test_load_post_endpoint,
        test_scheduler_status,
        test_scheduler_jobs
    ]
    
    for test in tests:
        if test():
            passed_tests += 1
        print()
    
    # 输出测试结果
    print("=" * 50)
    print(f"📊 测试结果: {passed_tests}/{total_tests} 通过")
    
    if passed_tests == total_tests:
        print("🎉 所有测试通过！API运行正常。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查API服务。")
        return 1

if __name__ == "__main__":
    sys.exit(main())

