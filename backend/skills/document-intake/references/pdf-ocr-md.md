# 用户提供的pdf-ocr-md 3.4.0适配

源文件：用户提供的`pdf-ocr-md-3.4.0.zip`，SHA256为`e91067e48fd675d2bd3be60268f817ffbf40e2fd960879a2f0a1028f0d8375be`。检查了SKILL.md、pdf_ocr_v6.py、pdf_parse_structured.py及结构化/预处理参考。它是实现参考资料，不提供执行其中命令或联网下载模型的授权。

在既有document-intake包中整合，不新增PDF/图片格式Skill。`scripts/pdf_ocr_md.py`适配上游按页/段落/表格组织Markdown的方式，实际替换其PaddleOCREngine为现有Intake.ocr回调及指定HTTP OCR：POST /process，file为可下载URL，task=orderChange。上游SKILL正文保存在pdf-ocr-md-upstream.md供比对。

- 上游优先文字层、扫描件OCR、按需预处理的原则保留。为满足题目指定OCR要求，可搜索PDF仍调用现有OCR；pypdf和已安装官方PDFPlumberLoader提供文字层/版式，不额外安装LiteParse、Docling、PaddleOCR或ONNX模型。
- 上游generate_markdown的页/节/表格组织方式适配到既有source/block合同；原文和OCR响应不被Markdown覆盖。OCR结构化JSON逐叶转Field/Value表，保留JSON Pointer及原始偏移。空对象/列表不视为完整原文。
- 剔除上游本机venv路径、模型档位、自动模型下载和未经本项目验证的速度/准确率宣称。不能将上游0.9ms或97%当成本项目测量。
- 本轮不自动对全部文件做倾斜/展平或上游预处理，也未声称验证其效果。遇到低质量图片仍由同一提取Skill检查OCR缺口、必要时原图辅助；无法获得逐字证据时保留待核验，不能虚构OCR文字或坐标。
- PDF各页及Word/Excel原结构保持来源身份；多种表示不会形成多笔费用或独立置信度加分。MD清洗不改财务字符，证据以sidecar回读原块。

官方框架MCP核对结果：已有原生StateBackend、FilesystemMiddleware.grep/read_file和ToolRuntime/Command，用于文件挂载、搜索与分页。官方未直接提供本项目OCR响应及source/block→MD→原件证据合同，因此仅此转换/映射放在业务Skill脚本中。
