#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试所有路由模块是否能正常导入"""
import sys
import traceback

print("=" * 80)
print("测试路由模块导入")
print("=" * 80)

modules_to_test = [
    "app.routers.auth",
    "app.routers.projects",
    "app.routers.documents",
    "app.routers.versions",
    "app.routers.review_runs",
    "app.routers.issues_router",
    "app.routers.kb",
    "app.routers.export_router",
]

failed = []
success = []

for module_name in modules_to_test:
    try:
        module = __import__(module_name, fromlist=[''])
        router = getattr(module, 'router', None)
        if router:
            routes = getattr(router, 'routes', [])
            print(f"✓ {module_name}: 成功导入，{len(routes)}个路由")
            success.append(module_name)
        else:
            print(f"⚠ {module_name}: 导入成功但未找到router对象")
            failed.append(module_name)
    except Exception as e:
        print(f"✗ {module_name}: 导入失败 - {e}")
        failed.append(module_name)
        traceback.print_exc()

print("\n" + "=" * 80)
print(f"成功: {len(success)}/{len(modules_to_test)}")
print(f"失败: {len(failed)}/{len(modules_to_test)}")

if failed:
    print("\n失败的模块:")
    for m in failed:
        print(f"  - {m}")

print("\n" + "=" * 80)
print("测试主应用导入...")

try:
    from app.main import app
    print("✓ app.main 导入成功")
    
    # 检查路由数量
    route_count = len([r for r in app.routes if hasattr(r, 'path')])
    print(f"✓ 应用中共有 {route_count} 个路由")
    
except Exception as e:
    print(f"✗ app.main 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)
