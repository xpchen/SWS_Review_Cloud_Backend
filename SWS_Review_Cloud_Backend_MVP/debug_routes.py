#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""详细调试路由匹配"""
import sys
import io

# Windows 控制台编码修复
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from app.main import app
from fastapi.routing import APIRoute

print("=" * 80)
print("路由匹配调试")
print("=" * 80)

# 获取所有路由
routes = []
for route in app.routes:
    if isinstance(route, APIRoute):
        routes.append({
            'path': route.path,
            'methods': sorted(route.methods),
            'endpoint': route.endpoint.__name__ if hasattr(route.endpoint, '__name__') else str(route.endpoint),
        })

# 按路径排序
routes_sorted = sorted(routes, key=lambda x: x['path'])

print("\n所有路由详情:")
for i, route in enumerate(routes_sorted, 1):
    print(f"\n{i}. 路径: {route['path']}")
    print(f"   方法: {', '.join(route['methods'])}")
    print(f"   端点: {route['endpoint']}")

# 检查登录路由
print("\n" + "=" * 80)
print("检查登录路由:")
login_routes = [r for r in routes_sorted if '/login' in r['path'] or '/api/auth/login' == r['path']]
if login_routes:
    for route in login_routes:
        print(f"\n找到登录路由:")
        print(f"  路径: {route['path']}")
        print(f"  方法: {', '.join(route['methods'])}")
        print(f"  端点: {route['endpoint']}")
else:
    print("\n[ERROR] 未找到登录路由！")

# 检查是否有冲突的路由
print("\n" + "=" * 80)
print("检查可能冲突的路由:")
conflict_routes = [r for r in routes_sorted if r['path'].startswith('/api/') or r['path'].startswith('/storage')]
print("\n所有 /api/ 和 /storage 开头的路由:")
for route in conflict_routes:
    print(f"  {', '.join(route['methods']):20s} {route['path']}")

# 测试路由匹配
print("\n" + "=" * 80)
print("测试路由匹配:")
test_path = "/api/auth/login"
print(f"\n测试路径: {test_path}")

# 手动检查路由匹配
from fastapi.routing import Match
for route in app.routes:
    if isinstance(route, APIRoute):
        match, scope = route.matches({"type": "http", "path": test_path, "method": "POST"})
        if match != Match.NONE:
            print(f"\n匹配到路由:")
            print(f"  路径: {route.path}")
            print(f"  方法: {sorted(route.methods)}")
            print(f"  匹配类型: {match}")
            if match == Match.PARTIAL:
                print(f"  [WARNING] 部分匹配 - 可能有问题！")
            elif match == Match.FULL:
                print(f"  [OK] 完全匹配")

print("\n" + "=" * 80)
