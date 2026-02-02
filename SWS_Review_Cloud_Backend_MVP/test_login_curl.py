#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""使用 requests 库测试登录接口"""
import sys
import io

# Windows 控制台编码修复
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
import json

url = "http://localhost:8000/api/auth/login"
headers = {
    "Content-Type": "application/json"
}
data = {
    "username": "test",
    "password": "test"
}

print("=" * 60)
print("测试登录接口")
print("=" * 60)
print(f"\nURL: {url}")
print(f"方法: POST")
print(f"请求头: {headers}")
print(f"请求体: {json.dumps(data, indent=2, ensure_ascii=False)}")

try:
    response = requests.post(url, json=data, headers=headers)
    print(f"\n响应状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    
    try:
        response_json = response.json()
        print(f"响应体: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
    except:
        print(f"响应体（文本）: {response.text}")
    
    if response.status_code == 404:
        print("\n[ERROR] 返回 404 - 路由未找到")
        print("可能的原因：")
        print("  1. URL 路径不正确")
        print("  2. HTTP 方法不正确（应该是 POST）")
        print("  3. 服务未正确启动")
    elif response.status_code == 401:
        print("\n[OK] 返回 401 - 路由存在，但认证失败（这是正常的）")
    elif response.status_code == 422:
        print("\n[OK] 返回 422 - 路由存在，但请求参数验证失败")
    else:
        print(f"\n[INFO] 返回 {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print("\n[ERROR] 无法连接到服务器")
    print("请确保服务正在运行：")
    print("  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
except Exception as e:
    print(f"\n[ERROR] 请求失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
