# 版本管理 API 说明

## 新增功能

为文档版本添加了三个管理操作：**取消**、**重新处理**、**删除**。

## API 接口

### 1. 取消版本处理

**接口**: `POST /api/versions/{version_id}/cancel`

**描述**: 取消正在处理中的版本，将状态改为 `CANCELED`

**权限**: 需要项目成员权限

**请求参数**:
- `version_id` (路径参数): 版本ID

**响应**:
```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": 1,
    "status": "CANCELED",
    "message": "Version canceled successfully"
  }
}
```

**错误情况**:
- `404`: 版本不存在
- `400`: 版本状态不是 `PROCESSING`，无法取消
- `403`: 无权限访问

**使用场景**: 当版本正在处理中（`PROCESSING`），用户想要停止处理时使用。

---

### 2. 重新处理版本

**接口**: `POST /api/versions/{version_id}/reprocess`

**描述**: 重新触发版本的处理流程，将状态重置为 `PROCESSING` 并启动 pipeline

**权限**: 需要项目成员权限

**请求参数**:
- `version_id` (路径参数): 版本ID

**响应**:
```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": 1,
    "status": "PROCESSING",
    "message": "Version reprocessing started"
  }
}
```

**错误情况**:
- `404`: 版本不存在
- `400`: 版本状态不允许重新处理（只有 `FAILED`, `CANCELED`, `READY`, `UPLOADED` 可以重新处理）
- `500`: Celery worker 不可用
- `403`: 无权限访问

**使用场景**: 
- 版本处理失败（`FAILED`）后重新处理
- 版本被取消（`CANCELED`）后重新处理
- 已完成版本（`READY`）需要重新处理
- 已上传但未处理的版本（`UPLOADED`）开始处理

---

### 3. 删除版本

**接口**: `DELETE /api/versions/{version_id}`

**描述**: 删除版本及其所有相关数据（审查问题、审查运行、文档块、表格、大纲节点、事实等）

**权限**: 需要项目成员权限

**请求参数**:
- `version_id` (路径参数): 版本ID

**响应**:
```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": 1,
    "message": "Version deleted successfully"
  }
}
```

**错误情况**:
- `404`: 版本不存在
- `400`: 版本正在处理中（`PROCESSING`），无法删除（需要先取消）
- `500`: 删除失败
- `403`: 无权限访问

**注意事项**:
- 删除版本会级联删除所有相关数据
- `file_object` 记录会保留（可能被其他版本引用）
- 存储中的文件不会被自动删除（需要手动清理）

**使用场景**: 当版本不再需要，需要完全删除时使用。

---

## 版本状态说明

版本有以下状态：

- `UPLOADED`: 已上传，未开始处理
- `PROCESSING`: 正在处理中
- `READY`: 处理完成，可以使用
- `FAILED`: 处理失败
- `CANCELED`: 已取消

## 状态转换规则

```
UPLOADED → PROCESSING → READY
                    ↓
                  FAILED
                    ↓
                 CANCELED
```

**操作规则**:
- **取消**: 只能取消 `PROCESSING` 状态的版本
- **重新处理**: 可以重新处理 `FAILED`, `CANCELED`, `READY`, `UPLOADED` 状态的版本
- **删除**: 不能删除 `PROCESSING` 状态的版本（需要先取消）

## 前端使用示例

### 取消版本
```javascript
async function cancelVersion(versionId) {
  const response = await fetch(`/api/versions/${versionId}/cancel`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
}
```

### 重新处理版本
```javascript
async function reprocessVersion(versionId) {
  const response = await fetch(`/api/versions/${versionId}/reprocess`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
}
```

### 删除版本
```javascript
async function deleteVersion(versionId) {
  const response = await fetch(`/api/versions/${versionId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
}
```

## 实现细节

### 后端实现

1. **version_service.py**:
   - `cancel_version()`: 取消版本
   - `can_reprocess_version()`: 检查是否可以重新处理
   - `reprocess_version()`: 重新处理版本
   - `delete_version()`: 删除版本及相关数据

2. **versions.py** (路由):
   - `POST /api/versions/{version_id}/cancel`: 取消接口
   - `POST /api/versions/{version_id}/reprocess`: 重新处理接口
   - `DELETE /api/versions/{version_id}`: 删除接口

### 数据删除顺序

删除版本时，按以下顺序删除相关数据（避免外键约束错误）：
1. 审查问题 (`review_issue`)
2. 审查运行 (`review_run`)
3. 文档块 (`doc_block`)
4. 文档表格 (`doc_table`)
5. 文档大纲节点 (`doc_outline_node`)
6. 文档事实 (`doc_fact`)
7. 版本本身 (`document_version`)
