@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 运行测试：广东领创化工方案（上传 + 处理 + AI 审查）
echo 默认文档：..\docs\校核文件\方案\广东领创化工新材料有限公司年产98万吨绿色化工新材料项目(报批稿).docx
echo.
python 测试领创化工方案.py %*
pause
