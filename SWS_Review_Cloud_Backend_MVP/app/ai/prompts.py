REVIEW_SYSTEM = """你是一名水土保持方案/报告审查专家。根据给定的文档片段和规范条文，输出JSON格式的审查问题列表。

输出必须为合法JSON，且仅包含以下结构：
{
  "issues": [
    {
      "issue_type": "字符串（问题类型）",
      "severity": "S1|S2|S3（S1=致命，S2=严重，S3=一般）",
      "title": "问题标题（简短）",
      "description": "问题描述（详细说明）",
      "suggestion": "修复建议",
      "confidence": 0.0~1.0（置信度）,
      "evidence": [
        {
          "block_id": 整数（必须来自给定的block_id列表）,
          "page_no": 整数（页码，可选）,
          "quote": "引用原文片段（必须是block文本的子串）"
        }
      ],
      "norm_refs": [
        {
          "kb_chunk_id": 整数（必须来自给定的chunk_id）,
          "ref": "条款号",
          "quote": "引用条款片段"
        }
      ]
    }
  ]
}

重要约束：
1. 若无问题，输出 {"issues": []}
2. evidence中的block_id必须来自文档片段中标注的block_id
3. norm_refs中的kb_chunk_id必须来自给定的规范chunk（chunk_id在[]中标注）
4. quote必须是原文/条款的实际子串，禁止编造
5. 禁止编造条款号
6. confidence应基于证据充分性：有明确规范依据=0.9+，仅逻辑判断=0.6-0.8
"""


def build_review_messages(
    section_context: str,
    norm_chunks: list[dict],
    checkpoint_name: str,
    prompt_template: str = "",
) -> list[dict]:
    """
    构建AI审查消息
    
    Args:
        section_context: 文档片段（应包含block_id标注）
        norm_chunks: 规范条款chunks
        checkpoint_name: 审查点名称
        prompt_template: 自定义prompt模板（可选）
    """
    # 格式化规范条文
    norm_text = "\n\n".join(
        f"[chunk_id={c['id']}] {c.get('meta_json', {}).get('ref', '')}\n{c.get('chunk_text', '')[:1000]}"
        for c in norm_chunks[:5]
    )
    
    # 构建用户消息
    if prompt_template:
        # 使用自定义模板
        user = prompt_template.format(
            checkpoint_name=checkpoint_name,
            section_context=section_context[:8000],
            norm_text=norm_text,
        )
    else:
        # 默认模板
        user = f"""审查点：{checkpoint_name}

文档片段（每个段落前标注了block_id）：
{section_context[:8000]}

规范条文（每个条文前标注了chunk_id）：
{norm_text}

请仔细审查文档片段，对照规范条文，输出JSON格式的问题列表。确保所有evidence的block_id和norm_refs的kb_chunk_id都来自上述标注的ID。"""
    
    return [
        {"role": "system", "content": REVIEW_SYSTEM},
        {"role": "user", "content": user},
    ]
