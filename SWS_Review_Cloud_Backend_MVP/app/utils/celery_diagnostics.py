"""
Celery Worker 诊断工具
"""
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def check_celery_worker_status() -> dict:
    """
    检查 Celery Worker 状态
    
    Returns:
        dict: {
            "available": bool,  # Worker是否可用
            "broker_connected": bool,  # Broker连接状态
            "active_workers": int,  # 活跃Worker数量
            "registered_tasks": list,  # 注册的任务列表
            "error": str | None,  # 错误信息（如果有）
        }
    """
    result = {
        "available": False,
        "broker_connected": False,
        "active_workers": 0,
        "registered_tasks": [],
        "error": None,
    }
    
    try:
        from app.worker.app import app as celery_app
        from celery import current_app
        
        # 检查Broker连接
        try:
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            
            if active_workers:
                result["broker_connected"] = True
                result["active_workers"] = len(active_workers)
                result["available"] = True
                
                # 获取注册的任务
                registered = inspect.registered()
                if registered:
                    # 合并所有worker的任务列表
                    all_tasks = set()
                    for worker_tasks in registered.values():
                        all_tasks.update(worker_tasks)
                    result["registered_tasks"] = sorted(list(all_tasks))
            else:
                result["broker_connected"] = True  # Broker可连接，但没有活跃Worker
                result["error"] = "没有活跃的 Celery Worker"
                
        except Exception as e:
            result["error"] = f"无法连接到 Celery Broker: {e}"
            logger.debug(f"Celery broker connection error: {e}", exc_info=True)
            
    except ImportError as e:
        result["error"] = f"无法导入 Celery 应用: {e}"
    except Exception as e:
        result["error"] = f"诊断失败: {e}"
        logger.debug(f"Celery diagnostics error: {e}", exc_info=True)
    
    return result


def diagnose_celery_setup() -> None:
    """
    诊断 Celery 设置并打印结果
    """
    print("=" * 60)
    print("Celery Worker 诊断")
    print("=" * 60)
    print()
    
    # 检查Redis连接
    print("1. 检查 Redis 连接...")
    try:
        from app.settings import settings
        import redis
        
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        print("   ✅ Redis 连接正常")
        print(f"   Redis URL: {settings.REDIS_URL.split('@')[-1] if '@' in settings.REDIS_URL else settings.REDIS_URL}")
    except Exception as e:
        print(f"   ❌ Redis 连接失败: {e}")
        print()
        print("建议：")
        print("  1. 检查 Redis 服务是否运行")
        print("  2. 检查 .env 文件中的 REDIS_URL 配置")
        print("  3. 确认 Redis 密码是否正确")
        return
    
    print()
    
    # 检查Celery应用
    print("2. 检查 Celery 应用配置...")
    try:
        from app.worker.app import app as celery_app
        print("   ✅ Celery 应用加载成功")
        print(f"   Broker URL: {celery_app.conf.broker_url.split('@')[-1] if '@' in celery_app.conf.broker_url else celery_app.conf.broker_url}")
        print(f"   Backend URL: {celery_app.conf.result_backend.split('@')[-1] if '@' in celery_app.conf.result_backend else celery_app.conf.result_backend}")
        print(f"   Worker Pool: {celery_app.conf.worker_pool}")
    except Exception as e:
        print(f"   ❌ Celery 应用加载失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # 检查Worker状态
    print("3. 检查 Celery Worker 状态...")
    status = check_celery_worker_status()
    
    if status["available"]:
        print("   ✅ Celery Worker 可用")
        print(f"   活跃 Worker 数量: {status['active_workers']}")
        if status["registered_tasks"]:
            print(f"   注册的任务数量: {len(status['registered_tasks'])}")
            print("   已注册的任务:")
            for task in status["registered_tasks"][:10]:  # 只显示前10个
                print(f"     - {task}")
            if len(status["registered_tasks"]) > 10:
                print(f"     ... 还有 {len(status['registered_tasks']) - 10} 个任务")
    else:
        print("   ❌ Celery Worker 不可用")
        if status["error"]:
            print(f"   错误: {status['error']}")
        print()
        print("建议：")
        print("  1. 启动 Celery Worker:")
        print("     celery -A app.worker.app worker --pool=solo --loglevel=info")
        print("  2. 或使用提供的批处理脚本:")
        print("     启动CeleryWorker.bat")
        print("  3. 如果不需要 Celery，可以使用 --direct 参数直接执行:")
        print("     python 测试审查.py <version_id> --direct")
    
    print()
    print("=" * 60)


def can_use_celery() -> bool:
    """
    快速检查是否可以使用 Celery
    
    Returns:
        bool: 如果 Celery Worker 可用返回 True，否则返回 False
    """
    status = check_celery_worker_status()
    return status["available"]
