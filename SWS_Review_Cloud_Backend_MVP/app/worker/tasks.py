import logging
from celery import chain
from .app import app
from . import pipeline
from .. import db
from ..settings import settings
from ..services.version_service import update_version_status

_schema = settings.DB_SCHEMA
logger = logging.getLogger(__name__)


def _fail_version(version_id: int, error_message: str) -> None:
    db.execute(
        f"UPDATE {_schema}.document_version SET status = 'FAILED', error_message = %(msg)s, updated_at = now() WHERE id = %(version_id)s",
        {"version_id": version_id, "msg": error_message[:2000]},
    )


@app.task(bind=True, max_retries=2)
def convert_docx_to_pdf_task(self, version_id: int):
    """任务1/7: DOCX转PDF"""
    try:
        logger.info(f"[版本 {version_id}] 开始任务: DOCX转PDF")
        update_version_status(version_id, "PROCESSING", progress=10, current_step="DOCX转PDF")
        pipeline.convert_docx_to_pdf(version_id)
        logger.info(f"[版本 {version_id}] 完成任务: DOCX转PDF")
        return version_id
    except Exception as e:
        logger.error(f"[版本 {version_id}] DOCX转PDF失败: {e}")
        _fail_version(version_id, str(e))
        raise


@app.task(bind=True, max_retries=2)
def parse_docx_structure_task(self, version_id: int):
    """任务2/7: 解析DOCX结构"""
    try:
        logger.info(f"[版本 {version_id}] 开始任务: 解析DOCX结构")
        update_version_status(version_id, "PROCESSING", progress=25, current_step="解析DOCX结构")
        pipeline.parse_docx_structure(version_id)
        logger.info(f"[版本 {version_id}] 完成任务: 解析DOCX结构")
        return version_id
    except Exception as e:
        logger.error(f"[版本 {version_id}] 解析DOCX结构失败: {e}")
        _fail_version(version_id, str(e))
        raise


@app.task(bind=True, max_retries=2)
def extract_pdf_layout_task(self, version_id: int):
    """任务3/7: 提取PDF布局"""
    try:
        logger.info(f"[版本 {version_id}] 开始任务: 提取PDF布局")
        update_version_status(version_id, "PROCESSING", progress=40, current_step="提取PDF布局")
        pipeline.extract_pdf_layout(version_id)
        logger.info(f"[版本 {version_id}] 完成任务: 提取PDF布局")
        return version_id
    except Exception as e:
        logger.error(f"[版本 {version_id}] 提取PDF布局失败: {e}")
        _fail_version(version_id, str(e))
        raise


@app.task(bind=True, max_retries=2)
def align_blocks_to_pdf_task(self, version_id: int):
    """任务4/7: 对齐块到PDF"""
    try:
        logger.info(f"[版本 {version_id}] 开始任务: 对齐块到PDF")
        update_version_status(version_id, "PROCESSING", progress=55, current_step="对齐块到PDF")
        pipeline.align_blocks_to_pdf(version_id)
        logger.info(f"[版本 {version_id}] 完成任务: 对齐块到PDF")
        return version_id
    except Exception as e:
        logger.error(f"[版本 {version_id}] 对齐块到PDF失败: {e}")
        _fail_version(version_id, str(e))
        raise


@app.task(bind=True, max_retries=2)
def extract_facts_task(self, version_id: int):
    """任务5/7: 抽取事实"""
    try:
        logger.info(f"[版本 {version_id}] 开始任务: 抽取事实")
        update_version_status(version_id, "PROCESSING", progress=70, current_step="抽取事实")
        count = pipeline.extract_facts(version_id)
        logger.info(f"[版本 {version_id}] 完成任务: 抽取事实 (共 {count} 条)")
        return version_id
    except Exception as e:
        # 事实抽取失败不影响主流程，记录日志即可
        logger.warning(f"[版本 {version_id}] 抽取事实失败（不影响主流程）: {e}")
        return version_id


@app.task(bind=True)
def build_chunks_task(self, version_id: int):
    """任务6/7: 构建块和索引（可选）"""
    try:
        logger.info(f"[版本 {version_id}] 开始任务: 构建块和索引")
        update_version_status(version_id, "PROCESSING", progress=85, current_step="构建块和索引")
        pipeline.build_chunks_and_index(version_id)
        logger.info(f"[版本 {version_id}] 完成任务: 构建块和索引")
    except Exception as e:
        logger.warning(f"[版本 {version_id}] 构建块和索引失败（可选步骤）: {e}")
    return version_id


@app.task(bind=True)
def finalize_ready_task(self, version_id: int):
    """任务7/7: 完成处理"""
    try:
        logger.info(f"[版本 {version_id}] 开始任务: 完成处理")
        update_version_status(version_id, "PROCESSING", progress=100, current_step="完成处理")
        pipeline.finalize_ready(version_id)
        logger.info(f"[版本 {version_id}] ✅ 所有任务完成，版本已就绪")
        return version_id
    except Exception as e:
        logger.error(f"[版本 {version_id}] 完成处理失败: {e}")
        _fail_version(version_id, str(e))
        raise


@app.task(bind=True)
def pipeline_chain(self, version_id: int):
    """运行完整管道: convert -> parse -> extract -> align -> extract_facts -> build -> finalize."""
    logger.info(f"[版本 {version_id}] 🚀 开始处理管道，共7个步骤")
    update_version_status(version_id, "PROCESSING", progress=0, current_step="初始化")
    s = chain(
        convert_docx_to_pdf_task.s(version_id),
        parse_docx_structure_task.s(),
        extract_pdf_layout_task.s(),
        align_blocks_to_pdf_task.s(),
        extract_facts_task.s(),  # 新增：抽取事实
        build_chunks_task.s(),
        finalize_ready_task.s(),
    )
    return s.apply_async()
