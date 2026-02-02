#!/usr/bin/env python
"""
检查 Celery 配置和 Worker 状态
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def check_redis_connection():
    """检查 Redis 连接"""
    print("=" * 60)
    print("1. 检查 Redis 连接")
    print("=" * 60)
    
    try:
        import redis
        from app.settings import settings
        
        # 解析 Redis URL
        redis_url = settings.REDIS_URL
        broker_url = settings.CELERY_BROKER_URL
        
        print(f"Redis URL: {redis_url}")
        print(f"Celery Broker URL: {broker_url}")
        
        # 尝试连接 Redis
        try:
            # 解析 URL
            if redis_url.startswith("redis://"):
                # 移除 redis:// 前缀
                url_part = redis_url.replace("redis://", "")
                if "@" in url_part:
                    # 有密码
                    auth, host_part = url_part.split("@")
                    if ":" in auth:
                        password = auth.split(":")[-1]
                    else:
                        password = auth
                else:
                    password = None
                    host_part = url_part
                
                if "/" in host_part:
                    host_port, db = host_part.split("/")
                else:
                    host_port = host_part
                    db = "0"
                
                if ":" in host_port:
                    host, port = host_port.split(":")
                else:
                    host = host_port
                    port = 6379
                
                print(f"\n尝试连接 Redis:")
                print(f"  主机: {host}")
                print(f"  端口: {port}")
                print(f"  数据库: {db}")
                print(f"  密码: {'***' if password else '无'}")
                
                r = redis.Redis(
                    host=host,
                    port=int(port),
                    db=int(db),
                    password=password if password else None,
                    decode_responses=False,
                    socket_connect_timeout=3
                )
                r.ping()
                print("✅ Redis 连接成功！")
                return True
            else:
                print("❌ Redis URL 格式不正确")
                return False
        except redis.ConnectionError as e:
            print(f"❌ Redis 连接失败: {e}")
            print("\n请检查:")
            print("  1. Redis 服务是否正在运行")
            print("  2. Redis 连接配置是否正确（.env 文件中的 REDIS_URL）")
            print("  3. 防火墙是否阻止了连接")
            return False
        except Exception as e:
            print(f"❌ 连接 Redis 时出错: {e}")
            return False
            
    except ImportError:
        print("❌ redis 模块未安装")
        print("请运行: pip install redis")
        return False

def check_celery_import():
    """检查 Celery 模块导入"""
    print("\n" + "=" * 60)
    print("2. 检查 Celery 模块导入")
    print("=" * 60)
    
    try:
        from app.worker.tasks import pipeline_chain
        print("✅ Celery 任务模块导入成功")
        print(f"   任务函数: {pipeline_chain}")
        return True
    except ImportError as e:
        print(f"❌ 无法导入 Celery 任务模块: {e}")
        print("\n请检查:")
        print("  1. app/worker/tasks.py 文件是否存在")
        print("  2. 所有依赖模块是否正确导入")
        return False
    except Exception as e:
        print(f"❌ 导入 Celery 任务时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_celery_app():
    """检查 Celery 应用配置"""
    print("\n" + "=" * 60)
    print("3. 检查 Celery 应用配置")
    print("=" * 60)
    
    try:
        from app.worker.app import app as celery_app
        from app.settings import settings
        
        print(f"Celery 应用名称: {celery_app.main}")
        print(f"Broker URL: {celery_app.conf.broker_url}")
        print(f"Backend URL: {celery_app.conf.result_backend}")
        print(f"任务序列化: {celery_app.conf.task_serializer}")
        print(f"结果序列化: {celery_app.conf.result_serializer}")
        
        # 尝试获取注册的任务
        registered_tasks = list(celery_app.tasks.keys())
        print(f"\n已注册的任务数量: {len(registered_tasks)}")
        if registered_tasks:
            print("前5个任务:")
            for task_name in registered_tasks[:5]:
                print(f"  - {task_name}")
        
        return True
    except Exception as e:
        print(f"❌ 检查 Celery 应用配置时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_celery_worker():
    """检查 Celery Worker 是否运行"""
    print("\n" + "=" * 60)
    print("4. 检查 Celery Worker 状态")
    print("=" * 60)
    
    try:
        from app.worker.app import app as celery_app
        
        # 尝试获取活跃的 worker
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            print(f"✅ 发现 {len(active_workers)} 个活跃的 Celery Worker:")
            for worker_name, tasks in active_workers.items():
                print(f"  - {worker_name}: {len(tasks)} 个任务")
        else:
            print("❌ 未发现活跃的 Celery Worker")
            print("\n请启动 Celery Worker:")
            import sys
            if sys.platform == "win32":
                print("  Windows: python -m celery -A app.worker.app worker --loglevel=info --pool=solo")
                print("  或使用批处理脚本: 启动CeleryWorker.bat")
            else:
                print("  Linux/Mac: celery -A app.worker.app worker --loglevel=info")
            return False
        
        return True
    except Exception as e:
        print(f"⚠️  无法检查 Worker 状态: {e}")
        print("这可能意味着 Worker 未运行")
        print("\n请启动 Celery Worker:")
        import sys
        if sys.platform == "win32":
            print("  Windows: python -m celery -A app.worker.app worker --loglevel=info --pool=solo")
            print("  或使用批处理脚本: 启动CeleryWorker.bat")
        else:
            print("  Linux/Mac: celery -A app.worker.app worker --loglevel=info")
        return False

def main():
    print("\n" + "=" * 60)
    print("Celery 配置和状态检查")
    print("=" * 60)
    
    results = []
    
    # 1. 检查 Redis
    results.append(("Redis 连接", check_redis_connection()))
    
    # 2. 检查 Celery 导入
    results.append(("Celery 模块导入", check_celery_import()))
    
    # 3. 检查 Celery 应用
    results.append(("Celery 应用配置", check_celery_app()))
    
    # 4. 检查 Worker（需要 Redis 连接成功）
    if results[0][1]:  # Redis 连接成功
        results.append(("Celery Worker 状态", check_celery_worker()))
    else:
        print("\n" + "=" * 60)
        print("4. 检查 Celery Worker 状态")
        print("=" * 60)
        print("⚠️  跳过（Redis 连接失败）")
        results.append(("Celery Worker 状态", False))
    
    # 总结
    print("\n" + "=" * 60)
    print("检查结果总结")
    print("=" * 60)
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✅ 所有检查通过！Celery 配置正常。")
    else:
        print("\n❌ 部分检查失败，请根据上述提示修复问题。")
        print("\n常见问题解决方案:")
        print("1. Redis 未运行:")
        print("   - Windows: 下载 Redis for Windows 并启动服务")
        print("   - Linux/Mac: sudo systemctl start redis 或 redis-server")
        print("\n2. Celery Worker 未运行:")
        import sys
        if sys.platform == "win32":
            print("   Windows: python -m celery -A app.worker.app worker --loglevel=info --pool=solo")
            print("   或使用批处理脚本: 启动CeleryWorker.bat")
        else:
            print("   Linux/Mac: celery -A app.worker.app worker --loglevel=info")
        print("\n3. 检查 .env 文件中的 Redis 配置:")
        print("   REDIS_URL=redis://:密码@localhost:6379/0")
        print("   CELERY_BROKER_URL=redis://:密码@localhost:6379/1")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
