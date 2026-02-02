import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .settings import settings
from .routers import auth, projects, documents, versions, review_runs, issues_router, kb, export_router

# 配置日志：确保日志输出到控制台
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)  # 输出到控制台
    ]
)

# 设置应用日志级别
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

app = FastAPI(title="SWS Review Cloud Backend (MVP)", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Static demo PDF
app.mount("/static", StaticFiles(directory="static"), name="static")


def ok(data=None):
    return {"code": "OK", "message": "success", "data": data}


# Local storage file serving (for get_signed_url when STORAGE_TYPE=local)
@app.get("/storage/{path:path}")
def serve_storage(path: str):
    root = Path(settings.LOCAL_STORAGE_DIR).resolve()
    full = (root / path).resolve()
    if not full.is_file() or not str(full).startswith(str(root)):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(full)


@app.exception_handler(HTTPException)
def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": "ERR", "message": exc.detail, "data": None}
    )


@app.get("/health")
def health():
    return ok({"status": "up"})


# 注册路由（带错误处理）
try:
    app.include_router(auth.router)
    logger.info("✓ auth路由注册成功")
except Exception as e:
    logger.error(f"✗ auth路由注册失败: {e}", exc_info=True)

try:
    app.include_router(projects.router)
    logger.info("✓ projects路由注册成功")
except Exception as e:
    logger.error(f"✗ projects路由注册失败: {e}", exc_info=True)

try:
    app.include_router(documents.router)
    logger.info("✓ documents路由注册成功")
except Exception as e:
    logger.error(f"✗ documents路由注册失败: {e}", exc_info=True)

try:
    app.include_router(versions.router)
    logger.info("✓ versions路由注册成功")
except Exception as e:
    logger.error(f"✗ versions路由注册失败: {e}", exc_info=True)

try:
    app.include_router(review_runs.router)
    logger.info("✓ review_runs路由注册成功")
except Exception as e:
    logger.error(f"✗ review_runs路由注册失败: {e}", exc_info=True)

try:
    app.include_router(issues_router.router)
    logger.info("✓ issues_router路由注册成功")
except Exception as e:
    logger.error(f"✗ issues_router路由注册失败: {e}", exc_info=True)

try:
    app.include_router(kb.router)
    logger.info("✓ kb路由注册成功")
except Exception as e:
    logger.error(f"✗ kb路由注册失败: {e}", exc_info=True)

try:
    app.include_router(export_router.router)
    logger.info("✓ export_router路由注册成功")
except Exception as e:
    logger.error(f"✗ export_router路由注册失败: {e}", exc_info=True)

# 调试：打印所有注册的路由
logger.info("=" * 60)
logger.info("已注册的路由列表:")
route_count = 0
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        for method in sorted(route.methods):
            if method != 'HEAD':
                logger.info(f"  {method:6s} {route.path}")
                route_count += 1
logger.info(f"总计: {route_count} 个路由")
logger.info("=" * 60)
