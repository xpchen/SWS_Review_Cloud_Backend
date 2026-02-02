"""
Block服务：提供outline_node到heading block的映射查询
用于修复P0-6：evidence_block_ids统一使用block.id
"""
from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA


def get_heading_block_id(version_id: int, outline_node_id: int) -> int | None:
    """
    获取outline_node对应的heading block_id
    
    Args:
        version_id: 版本ID
        outline_node_id: outline节点ID
    
    Returns:
        heading block_id，如果不存在则返回None
    """
    block = db.fetch_one(
        f"""
        SELECT id FROM {_schema}.doc_block
        WHERE version_id = %(v)s
        AND outline_node_id = %(oid)s
        AND block_type = 'HEADING'
        LIMIT 1
        """,
        {"v": version_id, "oid": outline_node_id}
    )
    return block["id"] if block else None


def get_first_block_id(version_id: int) -> int:
    """
    获取文档第一个block_id（用于兜底）
    
    Args:
        version_id: 版本ID
    
    Returns:
        第一个block_id，如果不存在则返回1
    """
    block = db.fetch_one(
        f"""
        SELECT id FROM {_schema}.doc_block
        WHERE version_id = %(v)s
        ORDER BY order_index
        LIMIT 1
        """,
        {"v": version_id}
    )
    return block["id"] if block else 1


def get_outline_heading_block_map(version_id: int) -> dict[int, int]:
    """
    获取outline_node_id到heading_block_id的映射
    
    Args:
        version_id: 版本ID
    
    Returns:
        {outline_node_id: heading_block_id} 映射字典
    """
    blocks = db.fetch_all(
        f"""
        SELECT outline_node_id, id
        FROM {_schema}.doc_block
        WHERE version_id = %(v)s
        AND block_type = 'HEADING'
        AND outline_node_id IS NOT NULL
        """,
        {"v": version_id}
    )
    return {b["outline_node_id"]: b["id"] for b in blocks}


def get_block_page_no(block_id: int) -> int | None:
    """
    从block_page_anchor表获取block的page_no
    
    Args:
        block_id: block ID
    
    Returns:
        page_no，如果不存在则返回None
    """
    anchor = db.fetch_one(
        f"""
        SELECT page_no FROM {_schema}.block_page_anchor
        WHERE block_id = %(bid)s
        ORDER BY confidence DESC
        LIMIT 1
        """,
        {"bid": block_id}
    )
    return anchor["page_no"] if anchor else None


def get_block_page_info(block_ids: list[int]) -> dict[int, dict]:
    """
    批量获取block的page_no和anchor_rects
    
    Args:
        block_ids: block ID列表
    
    Returns:
        {block_id: {"page_no": int, "anchor_rects": list}} 映射
    """
    if not block_ids:
        return {}
    
    anchors = db.fetch_all(
        f"""
        SELECT block_id, page_no, rect_norm, confidence
        FROM {_schema}.block_page_anchor
        WHERE block_id = ANY(%(ids)s)
        ORDER BY block_id, confidence DESC
        """,
        {"ids": block_ids}
    )
    
    result = {}
    for anchor in anchors:
        bid = anchor["block_id"]
        if bid not in result:
            result[bid] = {
                "page_no": anchor["page_no"],
                "anchor_rects": [],
            }
        
        # 添加rect_norm到anchor_rects
        if anchor.get("rect_norm"):
            result[bid]["anchor_rects"].append(anchor["rect_norm"])
    
    return result
