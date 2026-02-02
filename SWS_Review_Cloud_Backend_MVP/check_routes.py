#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查所有注册的路由"""
import sys
import traceback
import io

# Windows 控制台编码修复
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from app.main import app
    
    print("=" * 80)
    print("FastAPI 路由检查")
    print("=" * 80)
    
    # 获取所有路由
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                if method != 'HEAD':
                    routes.append((method, route.path))
    
    print(f"\n已注册的路由（共{len(routes)}个）:\n")
    
    # 按路径排序
    routes_sorted = sorted(routes, key=lambda x: (x[1], x[0]))
    
    # 按标签分组显示
    by_tag = {}
    for method, path in routes_sorted:
        # 从路径推断标签
        if path.startswith('/api/auth'):
            tag = 'auth'
        elif path.startswith('/api/projects'):
            tag = 'projects'
        elif path.startswith('/api/documents'):
            tag = 'documents'
        elif path.startswith('/api/versions'):
            tag = 'versions'
        elif path.startswith('/api/review-runs'):
            tag = 'review-runs'
        elif path.startswith('/api/issues'):
            tag = 'issues'
        elif path.startswith('/api/kb'):
            tag = 'kb'
        elif path.startswith('/api/versions') and 'export' in path:
            tag = 'export'
        elif path == '/health':
            tag = 'system'
        else:
            tag = 'other'
        
        if tag not in by_tag:
            by_tag[tag] = []
        by_tag[tag].append((method, path))
    
    for tag in sorted(by_tag.keys()):
        print(f"\n[{tag.upper()}]")
        for method, path in by_tag[tag]:
            print(f"  {method:6s} {path}")
    
    # 检查登录接口
    login_routes = [r for r in routes if '/login' in r[1]]
    print(f"\n\n登录相关路由:")
    if login_routes:
        for method, path in login_routes:
            print(f"  {method:6s} {path}")
    else:
        print("  [WARNING] 未找到登录路由！")
    
    # 检查auth路由
    auth_routes = [r for r in routes if '/api/auth' in r[1]]
    print(f"\n认证相关路由:")
    if auth_routes:
        for method, path in auth_routes:
            print(f"  {method:6s} {path}")
    else:
        print("  [WARNING] 未找到认证路由！")
    
    print("\n" + "=" * 80)
    
except ModuleNotFoundError as e:
    print(f"[ERROR] 缺少依赖模块: {e}")
    print("\n请先安装项目依赖:")
    print("  pip install -r requirements.txt")
    print("\n或者激活虚拟环境后再运行此脚本。")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] {e}")
    traceback.print_exc()
    sys.exit(1)
