#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试登录路由是否可访问"""
import sys
import io

# Windows 控制台编码修复
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from app.main import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    print("=" * 60)
    print("测试登录路由")
    print("=" * 60)
    
    # 测试1: 检查路由是否存在
    print("\n1. 检查路由是否存在:")
    routes = [r for r in app.routes if hasattr(r, 'path') and '/login' in r.path]
    if routes:
        for route in routes:
            methods = getattr(route, 'methods', set())
            print(f"   找到路由: {sorted(methods)} {route.path}")
    else:
        print("   [ERROR] 未找到登录路由！")
    
    # 测试2: 尝试访问路由（应该返回401，而不是404）
    print("\n2. 测试POST请求到 /api/auth/login:")
    try:
        response = client.post("/api/auth/login", json={"username": "test", "password": "test"})
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.json()}")
        
        if response.status_code == 404:
            print("   [ERROR] 返回404，路由未找到！")
        elif response.status_code == 401:
            print("   [OK] 返回401，路由存在（认证失败是正常的）")
        elif response.status_code == 422:
            print("   [OK] 返回422，路由存在（请求格式问题）")
        else:
            print(f"   [INFO] 返回{response.status_code}")
    except Exception as e:
        print(f"   [ERROR] 请求失败: {e}")
    
    # 测试3: 检查所有auth相关路由
    print("\n3. 所有auth相关路由:")
    auth_routes = [r for r in app.routes if hasattr(r, 'path') and '/api/auth' in r.path]
    for route in auth_routes:
        methods = getattr(route, 'methods', set())
        print(f"   {sorted(methods)} {route.path}")
    
    # 测试4: 检查OpenAPI文档
    print("\n4. 检查OpenAPI文档:")
    try:
        openapi = app.openapi()
        paths = openapi.get('paths', {})
        if '/api/auth/login' in paths:
            print("   [OK] OpenAPI文档中包含 /api/auth/login")
            print(f"   方法: {list(paths['/api/auth/login'].keys())}")
        else:
            print("   [ERROR] OpenAPI文档中不包含 /api/auth/login")
            print(f"   可用路径: {list(paths.keys())[:10]}...")
    except Exception as e:
        print(f"   [ERROR] 获取OpenAPI文档失败: {e}")
    
    print("\n" + "=" * 60)
    
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
