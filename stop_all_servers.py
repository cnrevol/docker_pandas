#!/usr/bin/env python3
"""
停止所有BPOD API服务器进程的脚本
"""

import os
import sys
import subprocess
import signal
import time

def get_python_processes():
    """获取所有Python进程"""
    try:
        # 在Windows上使用tasklist
        if os.name == 'nt':
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'], 
                                  capture_output=True, text=True, shell=True)
            lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            processes = []
            for line in lines:
                if line.strip():
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        pid = parts[1].strip('"')
                        if pid.isdigit():
                            processes.append(int(pid))
            return processes
        else:
            # 在Unix系统上使用ps
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            processes = []
            for line in result.stdout.split('\n'):
                if 'python' in line and 'api.py' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            processes.append(int(parts[1]))
                        except ValueError:
                            continue
            return processes
    except Exception as e:
        print(f"获取进程列表失败: {e}")
        return []

def stop_process(pid):
    """停止指定PID的进程"""
    try:
        if os.name == 'nt':
            # Windows
            subprocess.run(['taskkill', '/PID', str(pid), '/F'], 
                         capture_output=True, shell=True)
        else:
            # Unix
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # 进程已经停止
        return True
    except Exception as e:
        print(f"停止进程 {pid} 失败: {e}")
        return False

def main():
    """主函数"""
    print("🛑 正在停止所有BPOD API服务器进程...")
    
    # 获取所有Python进程
    processes = get_python_processes()
    
    if not processes:
        print("✅ 没有找到正在运行的Python进程")
        return
    
    print(f"找到 {len(processes)} 个Python进程:")
    for pid in processes:
        print(f"  - PID: {pid}")
    
    # 停止所有进程
    stopped_count = 0
    for pid in processes:
        print(f"正在停止进程 {pid}...")
        if stop_process(pid):
            print(f"✅ 进程 {pid} 已停止")
            stopped_count += 1
        else:
            print(f"❌ 停止进程 {pid} 失败")
    
    print(f"\n📊 总结:")
    print(f"  总进程数: {len(processes)}")
    print(f"  成功停止: {stopped_count}")
    print(f"  失败: {len(processes) - stopped_count}")
    
    if stopped_count > 0:
        print("\n✅ 所有API服务器进程已停止")
        print("💡 现在可以重新启动API服务器:")
        print("   python api.py")
        print("   或者")
        print("   python start_server.py")
    else:
        print("\n❌ 没有成功停止任何进程")

if __name__ == "__main__":
    main()
