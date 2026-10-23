# 合成 Office 费用单

本目录四种文件均为明确标注的合成材料，不属于原题或独立真实金标。

- `synthetic-confidence.xlsx`：两行费用，Handling Fee=2×25=50 USD，Doc Fee=1×20=20 USD，原文总额70 USD；编号DEMO-EXCEL-002。
- `synthetic-confidence.docx`：同一费用答案，编号DEMO-WORD-002。
- `.xls`、`.doc`：由项目内LibreOffice从上述现代格式转换，实际OLE魔数`d0cf11e0a1b11ae1`，用于验证旧格式转换链。
- 签发方Demo Carrier、接收方和记账主体Demo Trading Ltd；无旧账单、无更新指令，明确收费关系时预期CREATE/AP。

两次早期Qwen现代格式在线任务及其实际缺口见`backend/tests/reports/office-confidence-online.json`。后续固定答案UI验收不冒充新的模型抽取结果；回归与在线报告分开记录。
