# 合成Office格式样例

本目录由 `build_fixtures.py` 使用openpyxl、python-docx及LibreOffice生成，属于格式回归样例，不是题目业务金标、真实发票或在线模型输出。

- `fees-multisheet.xlsx`：3个工作表、隐藏/veryHidden工作表、隐藏行列、日期、合并区域、结构化表格；原文件不含公式缓存，预期公式明细50/20、合计70，另一币种费用15 EUR。
- `fees-multisheet.xls`：由真实LibreOffice导出的OLE二进制Excel 97格式。
- `fees-cross-page.docx`：小页幅、多页长表、重复表头、合并cell、嵌套表格及显式分页；证据按内容锚点定位。
- `fees-cross-page.doc`：由真实LibreOffice导出的OLE二进制Word 97格式。
- `expected.json`：合成标记、预期值与生成转换器版本；不将其作为独立业务评测标签。

从仓库根目录重新生成全部格式：

```powershell
./backend/python.cmd backend/tests/fixtures/office/build_fixtures.py --converter backend/vendor/libreoffice/program/soffice.com
```

LibreOffice的实际转换输出由Skill保存为独立派生件；测试检查原始样例字节不被覆盖，以及来源/哈希/公式缓存版本关系。`backend/skills/document-intake/tests/test_office.py` 在项目转换器存在时运行真实转换测试；没有配置转换器时会明确跳过这些用例。
