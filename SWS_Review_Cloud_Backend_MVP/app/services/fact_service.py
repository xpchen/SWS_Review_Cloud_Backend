"""
FactStore服务：从文档blocks和tables抽取结构化事实到doc_fact表。
用于一致性审查、公式计算、业务逻辑审查。
"""
import re
from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA

# 事实键定义（可扩展）
FACT_KEYS = {
    # 基础元信息
    "项目名称": ["项目名称", "工程名称", "建设项目名称"],
    "建设单位": ["建设单位", "业主单位"],
    "建设地点": ["建设地点", "项目位置", "项目地址"],
    "项目代码": ["项目代码", "统一社会信用代码"],
    
    # 规模与数量
    "总占地面积": ["总占地", "总占地面积", "项目占地"],
    "永久占地": ["永久占地", "永久占地面积"],
    "临时占地": ["临时占地", "临时占地面积"],
    "扰动面积": ["扰动面积", "扰动土地面积"],
    "损毁植被面积": ["损毁植被", "损毁植被面积"],
    "防治责任范围面积": ["防治责任范围", "防治责任范围面积"],
    
    # 土石方
    "挖方": ["挖方", "挖方量", "开挖量"],
    "填方": ["填方", "填方量", "回填量"],
    "借方": ["借方", "借土量"],
    "弃方": ["弃方", "弃方量", "弃渣量"],
    "外运量": ["外运", "外运量", "弃方外运"],
    
    # 工期
    "施工期起": ["施工期", "施工开始", "开工时间"],
    "施工期止": ["施工期", "施工结束", "竣工时间"],
    "设计水平年": ["设计水平年", "水平年"],
    
    # 投资
    "静态投资": ["静态投资", "工程投资", "总投资"],
    "水土保持投资": ["水土保持投资", "水保投资"],
    
    # 六项指标相关
    "治理达标面积": ["治理达标面积", "达标面积"],
    "水土流失总面积": ["水土流失总面积", "流失总面积"],
    "防治措施面积": ["防治措施面积", "措施面积"],
    "渣土防护量": ["渣土防护量", "防护量"],
    "渣土总量": ["渣土总量", "总渣土量"],
    "表土保护量": ["表土保护量", "保护表土量"],
    "可剥离表土量": ["可剥离表土量", "可剥离量"],
    "恢复面积": ["恢复面积", "已恢复面积"],
    "可恢复面积": ["可恢复面积", "应恢复面积"],
    "植被覆盖面积": ["植被覆盖面积", "覆盖面积"],
    "可绿化面积": ["可绿化面积", "应绿化面积"],
    
    # 预测计算相关
    "分区面积": ["分区面积", "预测分区面积"],
    "时段": ["时段", "预测时段"],
    "侵蚀模数": ["侵蚀模数", "侵蚀强度"],
    
    # 布尔型事实
    "是否弃渣": ["弃渣", "弃方", "弃土"],
    "是否临时用地": ["临时用地", "临时占地"],
    "是否消纳场": ["消纳场", "专门存放地"],
}


def extract_facts(version_id: int) -> int:
    """
    从文档blocks和tables抽取事实到doc_fact表。
    返回抽取的事实数量。
    """
    # 清理旧事实
    db.execute(f"DELETE FROM {_schema}.doc_fact WHERE version_id = %(v)s", {"v": version_id})
    
    # 获取outline节点（用于scope）
    outline_nodes = db.fetch_all(
        f"""
        SELECT id, node_no, title, level
        FROM {_schema}.doc_outline_node
        WHERE version_id = %(v)s
        ORDER BY order_index
        """,
        {"v": version_id}
    )
    outline_map = {n["id"]: n for n in outline_nodes}
    
    # 获取所有blocks
    blocks = db.fetch_all(
        f"""
        SELECT id, outline_node_id, block_type, text
        FROM {_schema}.doc_block
        WHERE version_id = %(v)s AND text IS NOT NULL
        ORDER BY order_index
        """,
        {"v": version_id}
    )
    
    # 获取所有tables
    tables = db.fetch_all(
        f"""
        SELECT t.id, t.table_no, t.title, t.outline_node_id,
               b.id as block_id
        FROM {_schema}.doc_table t
        LEFT JOIN {_schema}.doc_block b ON b.table_id = t.id
        WHERE t.version_id = %(v)s
        """,
        {"v": version_id}
    )
    
    facts_inserted = 0
    
    # 从blocks抽取文本型事实
    for block in blocks:
        text = block.get("text") or ""
        if not text.strip():
            continue
        
        outline_node_id = block.get("outline_node_id")
        scope = _get_scope(outline_node_id, outline_map)
        
        # 匹配事实键
        for fact_key, patterns in FACT_KEYS.items():
            for pattern in patterns:
                # 查找模式：pattern + 可能的数值/文本
                # 例如："总占地面积" + "12.5" + "hm²"
                regex = rf"{re.escape(pattern)}[：:：\s]*([\d.，,]+)\s*([^\d\s，,。.；;]+)?"
                matches = re.finditer(regex, text)
                for match in matches:
                    value_str = match.group(1).replace("，", ",").replace(",", "")
                    unit = match.group(2).strip() if match.group(2) else None
                    
                    try:
                        value_num = float(value_str)
                        # 单位换算（hm² -> m², 万元 -> 元）
                        if unit:
                            if "万" in unit:
                                value_num *= 10000
                                unit = unit.replace("万", "")
                            if unit in ["hm²", "公顷"]:
                                value_num *= 10000
                                unit = "m²"
                        
                        _insert_fact(
                            version_id=version_id,
                            fact_key=fact_key,
                            value_num=value_num,
                            value_text=None,
                            unit=unit,
                            scope=scope,
                            source_block_id=block["id"],
                            source_table_id=None,
                            confidence=0.7,
                        )
                        facts_inserted += 1
                    except ValueError:
                        # 文本型事实
                        value_text = match.group(0)
                        _insert_fact(
                            version_id=version_id,
                            fact_key=fact_key,
                            value_num=None,
                            value_text=value_text,
                            unit=None,
                            scope=scope,
                            source_block_id=block["id"],
                            source_table_id=None,
                            confidence=0.6,
                        )
                        facts_inserted += 1
    
    # 从tables抽取数值型事实
    for table in tables:
        table_id = table["id"]
        table_no = table.get("table_no") or f"表{table_id}"
        outline_node_id = table.get("outline_node_id")
        scope = f"{table_no}" + (f"({_get_scope(outline_node_id, outline_map)})" if outline_node_id else "")
        
        # 获取表格单元格
        cells = db.fetch_all(
            f"""
            SELECT r, c, text, num_value, unit
            FROM {_schema}.doc_table_cell
            WHERE table_id = %(tid)s
            ORDER BY r, c
            """,
            {"tid": table_id}
        )
        
        # 按行组织
        by_row = {}
        for cell in cells:
            r = cell["r"]
            by_row.setdefault(r, []).append(cell)
        
        # 查找表头行（通常第一行）
        if by_row:
            header_row = by_row.get(0, [])
            header_texts = [c.get("text") or "" for c in header_row]
            
            # 匹配表头中的事实键
            for fact_key, patterns in FACT_KEYS.items():
                for pattern in patterns:
                    for hi, header_text in enumerate(header_texts):
                        if pattern in header_text:
                            # 查找该列的数据行
                            for r_idx, row_cells in by_row.items():
                                if r_idx == 0:
                                    continue  # 跳过表头
                                if hi < len(row_cells):
                                    cell = row_cells[hi]
                                    num_value = cell.get("num_value")
                                    unit = cell.get("unit")
                                    if num_value is not None:
                                        _insert_fact(
                                            version_id=version_id,
                                            fact_key=fact_key,
                                            value_num=num_value,
                                            value_text=None,
                                            unit=unit,
                                            scope=scope,
                                            source_block_id=table.get("block_id"),
                                            source_table_id=table_id,
                                            confidence=0.8,
                                        )
                                        facts_inserted += 1
    
    return facts_inserted


def _get_scope(outline_node_id: int | None, outline_map: dict) -> str:
    """根据outline_node_id生成scope字符串"""
    if not outline_node_id or outline_node_id not in outline_map:
        return "项目整体"
    node = outline_map[outline_node_id]
    node_no = node.get("node_no") or ""
    title = node.get("title") or ""
    return f"{node_no} {title}".strip() or "项目整体"


def _insert_fact(
    version_id: int,
    fact_key: str,
    value_num: float | None,
    value_text: str | None,
    unit: str | None,
    scope: str,
    source_block_id: int | None,
    source_table_id: int | None,
    confidence: float,
) -> None:
    """插入事实到doc_fact表（使用ON CONFLICT更新）"""
    sql = f"""
    INSERT INTO {_schema}.doc_fact
    (version_id, fact_key, value_num, value_text, unit, scope, source_block_id, source_table_id, confidence)
    VALUES (%(version_id)s, %(fact_key)s, %(value_num)s, %(value_text)s, %(unit)s, %(scope)s, %(source_block_id)s, %(source_table_id)s, %(confidence)s)
    ON CONFLICT (version_id, fact_key, scope)
    DO UPDATE SET
        value_num = EXCLUDED.value_num,
        value_text = EXCLUDED.value_text,
        unit = EXCLUDED.unit,
        source_block_id = EXCLUDED.source_block_id,
        source_table_id = EXCLUDED.source_table_id,
        confidence = EXCLUDED.confidence,
        updated_at = now()
    """
    db.execute(sql, {
        "version_id": version_id,
        "fact_key": fact_key,
        "value_num": value_num,
        "value_text": value_text,
        "unit": unit,
        "scope": scope,
        "source_block_id": source_block_id,
        "source_table_id": source_table_id,
        "confidence": confidence,
    })


def get_facts(version_id: int, fact_key: str | None = None, scope: str | None = None) -> list[dict]:
    """查询事实"""
    conditions = ["version_id = %(version_id)s"]
    params = {"version_id": version_id}
    
    if fact_key:
        conditions.append("fact_key = %(fact_key)s")
        params["fact_key"] = fact_key
    
    if scope:
        conditions.append("scope = %(scope)s")
        params["scope"] = scope
    
    sql = f"""
    SELECT id, fact_key, value_num, value_text, unit, scope, source_block_id, source_table_id, confidence
    FROM {_schema}.doc_fact
    WHERE {' AND '.join(conditions)}
    ORDER BY fact_key, scope
    """
    return db.fetch_all(sql, params)
