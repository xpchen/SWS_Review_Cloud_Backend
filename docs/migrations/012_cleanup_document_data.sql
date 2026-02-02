-- 012: 清理文档相关数据的SQL脚本
-- 注意：执行前请备份数据库！
SET search_path = sws, public;

-- ============================================================================
-- 选项1: 清理特定版本的所有数据
-- ============================================================================
-- 使用方法：将 <version_id> 替换为实际的版本ID
-- 
-- 示例：清理版本ID为13的所有数据
-- DELETE FROM sws.review_issue WHERE version_id = 13;
-- DELETE FROM sws.review_run WHERE version_id = 13;
-- DELETE FROM sws.doc_fact WHERE version_id = 13;
-- DELETE FROM sws.block_page_anchor WHERE block_id IN (SELECT id FROM sws.doc_block WHERE version_id = 13);
-- DELETE FROM sws.doc_table_cell WHERE table_id IN (SELECT id FROM sws.doc_table WHERE version_id = 13);
-- DELETE FROM sws.doc_block WHERE version_id = 13;
-- DELETE FROM sws.doc_table WHERE version_id = 13;
-- DELETE FROM sws.doc_outline_node WHERE version_id = 13;
-- DELETE FROM sws.document_version WHERE id = 13;

-- ============================================================================
-- 选项2: 清理特定文档的所有数据（包括所有版本）
-- ============================================================================
-- 使用方法：将 <document_id> 替换为实际的文档ID
-- 
-- 注意：这会删除该文档的所有版本及其所有相关数据！
-- 
-- 示例：清理文档ID为1的所有数据
/*
DO $$
DECLARE
    doc_id INTEGER := 1;  -- 修改这里的文档ID
BEGIN
    -- 删除审查问题（通过版本ID关联）
    DELETE FROM review_issue 
    WHERE version_id IN (SELECT id FROM document_version WHERE document_id = doc_id);
    
    -- 删除审查运行
    DELETE FROM review_run 
    WHERE version_id IN (SELECT id FROM document_version WHERE document_id = doc_id);
    
    -- 删除文档事实
    DELETE FROM doc_fact 
    WHERE version_id IN (SELECT id FROM document_version WHERE document_id = doc_id);
    
    -- 删除块页面锚点（通过块ID关联）
    DELETE FROM block_page_anchor 
    WHERE block_id IN (
        SELECT id FROM doc_block 
        WHERE version_id IN (SELECT id FROM document_version WHERE document_id = doc_id)
    );
    
    -- 删除表格单元格（通过表格ID关联）
    DELETE FROM doc_table_cell 
    WHERE table_id IN (
        SELECT id FROM doc_table 
        WHERE version_id IN (SELECT id FROM document_version WHERE document_id = doc_id)
    );
    
    -- 删除文档块
    DELETE FROM doc_block 
    WHERE version_id IN (SELECT id FROM document_version WHERE document_id = doc_id);
    
    -- 删除表格
    DELETE FROM doc_table 
    WHERE version_id IN (SELECT id FROM document_version WHERE document_id = doc_id);
    
    -- 删除大纲节点
    DELETE FROM doc_outline_node 
    WHERE version_id IN (SELECT id FROM document_version WHERE document_id = doc_id);
    
    -- 删除版本（会自动删除关联的文件对象引用，但不会删除file_object记录）
    DELETE FROM document_version WHERE document_id = doc_id;
    
    -- 删除文档
    DELETE FROM document WHERE id = doc_id;
    
    RAISE NOTICE '已清理文档 % 的所有数据', doc_id;
END $$;
*/

-- ============================================================================
-- 选项3: 清理所有文档数据（危险！）
-- ============================================================================
-- 警告：这会删除所有文档、版本、审查数据！
-- 执行前请确保已备份数据库！
/*
-- 删除所有审查问题
DELETE FROM review_issue;

-- 删除所有审查运行
DELETE FROM review_run;

-- 删除所有文档事实
DELETE FROM doc_fact;

-- 删除所有块页面锚点
DELETE FROM block_page_anchor;

-- 删除所有表格单元格
DELETE FROM doc_table_cell;

-- 删除所有文档块
DELETE FROM doc_block;

-- 删除所有表格
DELETE FROM doc_table;

-- 删除所有大纲节点
DELETE FROM doc_outline_node;

-- 删除所有版本
DELETE FROM document_version;

-- 删除所有文档
DELETE FROM document;

-- 注意：file_object 表不会被删除，因为文件对象可能被其他表引用
-- 如果需要清理未使用的文件对象，请手动执行：
-- DELETE FROM file_object WHERE id NOT IN (
--     SELECT DISTINCT source_file_id FROM document_version WHERE source_file_id IS NOT NULL
--     UNION
--     SELECT DISTINCT pdf_file_id FROM document_version WHERE pdf_file_id IS NOT NULL
--     UNION
--     SELECT DISTINCT structure_json_file_id FROM document_version WHERE structure_json_file_id IS NOT NULL
--     UNION
--     SELECT DISTINCT page_map_json_file_id FROM document_version WHERE page_map_json_file_id IS NOT NULL
--     UNION
--     SELECT DISTINCT text_full_file_id FROM document_version WHERE text_full_file_id IS NOT NULL
-- );
*/

-- ============================================================================
-- 选项4: 清理特定项目下的所有文档数据
-- ============================================================================
-- 使用方法：将 <project_id> 替换为实际的项目ID
/*
DO $$
DECLARE
    proj_id INTEGER := 1;  -- 修改这里的项目ID
BEGIN
    -- 删除审查问题
    DELETE FROM review_issue 
    WHERE version_id IN (
        SELECT dv.id FROM document_version dv
        JOIN document d ON dv.document_id = d.id
        WHERE d.project_id = proj_id
    );
    
    -- 删除审查运行
    DELETE FROM review_run 
    WHERE version_id IN (
        SELECT dv.id FROM document_version dv
        JOIN document d ON dv.document_id = d.id
        WHERE d.project_id = proj_id
    );
    
    -- 删除文档事实
    DELETE FROM doc_fact 
    WHERE version_id IN (
        SELECT dv.id FROM document_version dv
        JOIN document d ON dv.document_id = d.id
        WHERE d.project_id = proj_id
    );
    
    -- 删除块页面锚点
    DELETE FROM block_page_anchor 
    WHERE block_id IN (
        SELECT db.id FROM doc_block db
        JOIN document_version dv ON db.version_id = dv.id
        JOIN document d ON dv.document_id = d.id
        WHERE d.project_id = proj_id
    );
    
    -- 删除表格单元格
    DELETE FROM doc_table_cell 
    WHERE table_id IN (
        SELECT dt.id FROM doc_table dt
        JOIN document_version dv ON dt.version_id = dv.id
        JOIN document d ON dv.document_id = d.id
        WHERE d.project_id = proj_id
    );
    
    -- 删除文档块
    DELETE FROM doc_block 
    WHERE version_id IN (
        SELECT dv.id FROM document_version dv
        JOIN document d ON dv.document_id = d.id
        WHERE d.project_id = proj_id
    );
    
    -- 删除表格
    DELETE FROM doc_table 
    WHERE version_id IN (
        SELECT dv.id FROM document_version dv
        JOIN document d ON dv.document_id = d.id
        WHERE d.project_id = proj_id
    );
    
    -- 删除大纲节点
    DELETE FROM doc_outline_node 
    WHERE version_id IN (
        SELECT dv.id FROM document_version dv
        JOIN document d ON dv.document_id = d.id
        WHERE d.project_id = proj_id
    );
    
    -- 删除版本
    DELETE FROM document_version 
    WHERE document_id IN (SELECT id FROM document WHERE project_id = proj_id);
    
    -- 删除文档
    DELETE FROM document WHERE project_id = proj_id;
    
    RAISE NOTICE '已清理项目 % 下的所有文档数据', proj_id;
END $$;
*/

-- ============================================================================
-- 选项5: 清理所有审查数据（保留文档和版本）
-- ============================================================================
-- 只删除审查相关数据，保留文档和版本数据
/*
DELETE FROM issue_action_log;
DELETE FROM review_issue;
DELETE FROM review_run;
*/

-- ============================================================================
-- 选项6: 清理未使用的文件对象（谨慎使用）
-- ============================================================================
-- 删除没有被任何版本引用的文件对象
-- 注意：这不会删除存储中的实际文件，只会删除数据库记录
/*
DELETE FROM file_object 
WHERE id NOT IN (
    SELECT DISTINCT source_file_id FROM document_version WHERE source_file_id IS NOT NULL
    UNION
    SELECT DISTINCT pdf_file_id FROM document_version WHERE pdf_file_id IS NOT NULL
    UNION
    SELECT DISTINCT structure_json_file_id FROM document_version WHERE structure_json_file_id IS NOT NULL
    UNION
    SELECT DISTINCT page_map_json_file_id FROM document_version WHERE page_map_json_file_id IS NOT NULL
    UNION
    SELECT DISTINCT text_full_file_id FROM document_version WHERE text_full_file_id IS NOT NULL
);
*/

-- ============================================================================
-- 查询脚本：查看数据统计
-- ============================================================================

-- 查看文档和版本统计
/*
SELECT 
    p.id as project_id,
    p.name as project_name,
    COUNT(DISTINCT d.id) as document_count,
    COUNT(DISTINCT dv.id) as version_count,
    COUNT(DISTINCT rr.id) as review_run_count,
    COUNT(DISTINCT ri.id) as issue_count
FROM project p
LEFT JOIN document d ON d.project_id = p.id
LEFT JOIN document_version dv ON dv.document_id = d.id
LEFT JOIN review_run rr ON rr.version_id = dv.id
LEFT JOIN review_issue ri ON ri.version_id = dv.id
GROUP BY p.id, p.name
ORDER BY p.id;
*/

-- 查看特定文档的详细信息
/*
SELECT 
    d.id as document_id,
    d.title as document_title,
    dv.id as version_id,
    dv.version_no,
    dv.status,
    COUNT(DISTINCT don.id) as outline_nodes,
    COUNT(DISTINCT db.id) as blocks,
    COUNT(DISTINCT dt.id) as tables,
    COUNT(DISTINCT df.id) as facts,
    COUNT(DISTINCT rr.id) as review_runs,
    COUNT(DISTINCT ri.id) as issues
FROM document d
JOIN document_version dv ON dv.document_id = d.id
LEFT JOIN doc_outline_node don ON don.version_id = dv.id
LEFT JOIN doc_block db ON db.version_id = dv.id
LEFT JOIN doc_table dt ON dt.version_id = dv.id
LEFT JOIN doc_fact df ON df.version_id = dv.id
LEFT JOIN review_run rr ON rr.version_id = dv.id
LEFT JOIN review_issue ri ON ri.version_id = dv.id
WHERE d.id = 1  -- 修改这里的文档ID
GROUP BY d.id, d.title, dv.id, dv.version_no, dv.status
ORDER BY dv.version_no;
*/
