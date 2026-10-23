# 原件定位与双视图（2026-10-22）

## 已修复

- `evidence-linking` 的 `build_preview` 仍只负责只读投影；新增 `original_location.py` 作为最小领域缺口实现。
- PDF 有文字层时，使用保存原件的实际字符几何和现有金额/币种解析器定位；不再要求 PDF 文本顺序与 `PDFPlumberLoader(layout=True)` 的整段引用一致。字段值和费用上下文用于选择费用行，重复金额保留多处候选，界面要求用户对照。
- PDF/图片没有可用文字层时，按页面/帧使用项目便携环境中的 RapidOCR 生成定位辅助框。它只用于黄色显示，不改变指定 OCR 的提取结果、原文、金额或证据事实；低分识别不生成框。
- Office 预览复用 document-intake 的 LibreOffice 转 PDF 能力并按原文件哈希缓存，作为展示产物，不改任务快照或历史证据。Excel/Word 保留已有结构化 sheet/row/cell/paragraph 视图。
- 预览抽屉统一为两个顶层页签：默认“原件定位”（PDF/Office PDF/图片及黄色标注），第二个“提取原文”（OCR/文字/结构化块）。

## 验证

- `backend/skills/evidence-linking/tests/test_original_location.py`：使用已保存的 `PDF示例账单1.pdf` 费用行，原始引文为布局顺序，PDF 实际文本层中字段分散时仍返回第 1 页真实归一化坐标；1 passed。
- evidence-linking 定向测试：86 passed。
- `backend` 相关文件 `py_compile` 通过。
- Vue `npm run typecheck` 和 `npm run build` 通过（2501 modules，Vite 1.11s）。
- 正式 Agent Server 已在无 busy 线程时优雅重启并恢复健康；重启辅助报告的历史线程基线比当前数据库少 1 个线程，因此未将该报告的旧 `threads_unchanged` 断言写成通过。当前 `/api/health` 返回 database/redis ok，源材料预览接口对现有 EML 返回 200。

## 仍需明确

- 扫描件的黄色框依赖 RapidOCR 本地辅助结果；如果指定远端 OCR 返回坐标，后续可优先使用其真实坐标，当前不从文字猜坐标。
- 原始 PDF/Office 位置是物理展示定位；提取原文页签仍显示经过文本/OCR的保存内容，两者不混淆。
