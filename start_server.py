#!/usr/bin/env python3
"""
BPOD API 服务器启动脚本
支持多种启动模式和配置选项
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path

def setup_environment():
    """设置环境变量和路径"""
    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # 设置默认环境变量
    os.environ.setdefault('LOG_LEVEL', 'INFO')
    os.environ.setdefault('API_HOST', '0.0.0.0')
    os.environ.setdefault('API_PORT', '8000')

def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description='BPOD API 服务器启动脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python start_server.py                    # 默认启动
  python start_server.py --host 127.0.0.1   # 指定主机
  python start_server.py --port 9000        # 指定端口
  python start_server.py --reload           # 开发模式
  python start_server.py --workers 4        # 生产模式
        """
    )
    
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='服务器主机地址 (默认: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='服务器端口 (默认: 8000)'
    )
    
    parser.add_argument(
        '--reload',
        action='store_true',
        help='启用自动重载 (开发模式)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='工作进程数 (默认: 1)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error'],
        default='info',
        help='日志级别 (默认: info)'
    )
    
    parser.add_argument(
        '--config',
        help='配置文件路径'
    )
    
    return parser

def main():
    """主函数"""
    # 设置环境
    setup_environment()
    
    # 解析命令行参数
    parser = create_parser()
    args = parser.parse_args()
    
    # 设置环境变量
    os.environ['API_HOST'] = args.host
    os.environ['API_PORT'] = str(args.port)
    os.environ['LOG_LEVEL'] = args.log_level.upper()
    
    # 导入应用
    try:
        from api import app
        print(f"✅ 成功导入BPOD API应用")
    except ImportError as e:
        print(f"❌ 导入应用失败: {e}")
        sys.exit(1)
    
    # 打印启动信息
    print("🚀 启动BPOD API服务器...")
    print(f"   主机: {args.host}")
    print(f"   端口: {args.port}")
    print(f"   日志级别: {args.log_level}")
    print(f"   工作进程: {args.workers}")
    print(f"   自动重载: {'是' if args.reload else '否'}")
    print(f"   文档地址: http://{args.host}:{args.port}/docs")
    print(f"   健康检查: http://{args.host}:{args.port}/health")
    print("-" * 50)
    
    # 启动服务器
    try:
        if args.reload:
            # 开发模式
            uvicorn.run(
                "api:app",
                host=args.host,
                port=args.port,
                reload=True,
                log_level=args.log_level,
                access_log=True
            )
        else:
            # 生产模式
            uvicorn.run(
                "api:app",
                host=args.host,
                port=args.port,
                workers=args.workers,
                log_level=args.log_level,
                access_log=True
            )
    except KeyboardInterrupt:
        print("\n🛑 服务器已停止")
    except Exception as e:
        print(f"❌ 启动服务器失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
