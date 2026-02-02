-- 008: 增加字符串字段长度以支持更长的值
SET search_path = sws, public;

-- 1. 增加 doc_outline_node.node_no 字段长度（从32增加到64）
-- 某些文档的标题编号可能很长（如 1.2.3.4.5.6.7.8）
ALTER TABLE doc_outline_node ALTER COLUMN node_no TYPE varchar(64);

-- 2. 增加 doc_table_cell.unit 字段长度（从32增加到64）
-- 某些单位可能较长（如 "平方米/公顷"、"元/平方米" 等）
ALTER TABLE doc_table_cell ALTER COLUMN unit TYPE varchar(64);

-- 3. 添加注释
COMMENT ON COLUMN doc_outline_node.node_no IS '节点编号（如 "1.2.3"），最大64字符';
COMMENT ON COLUMN doc_table_cell.unit IS '单位（如 "m²"、"元"），最大64字符';
