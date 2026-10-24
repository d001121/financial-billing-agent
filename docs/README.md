# 项目文档

文档围绕当前方案、运行开发与验证证据组织。旧计划、未采用设计稿和重复截图已从目录移除，历史可从 Git 追溯。

| 阅读目的 | 文档 |
| --- | --- |
| 启动与演示 | [项目首页](../README.md) · [后端](../backend/README.md) · [前端](../frontend/README.md) |
| 了解项目难点与贡献 | [项目说明](project-solution.md) · [笔试答辩PDF](../output/pdf/Harbor_项目方案与笔试答辩.pdf) |
| 理解模块与执行边界 | [实现说明](implementation.md) · [Skill 与 Hook](skills-and-hooks.md) |
| 环境、恢复与性能 | [便携环境](portable-environment.md) · [恢复](recovery.md) · [性能](performance.md) |
| 核实证据与缺口 | [验收记录](acceptance.md) · [样本清单](sample-inventory.md) |
| 界面与业务取舍 | [界面说明](ui-design.md) · [补充思考](insights.md) |

开发约定只在根 [AGENT.md](../AGENT.md) 维护。`research/` 仅保留仍被项目方案、业务合同或验收结论引用的专题证据，日期与测试范围不能当作当前全量成绩。`assets/` 只保存文档使用的当前合成界面截图；运行素材在 `frontend/src/assets/`。

原题 HTML、本机原件和详细回执分别位于本地 `docs/assignment/`、`backend/data/`、`backend/tests/reports/`，不纳入 Git。源码克隆不附带本机资料。

## 重建 PDF

在安装了 reportlab、Pillow 的文档 Python 环境中运行 `python docs/scripts/build_project_report.py`。默认使用 Windows 等线字体；可通过 `--font-dir` 指定包含 Deng.ttf、Dengb.ttf 的目录。脚本只读答辩 Markdown 与合成截图，不连接模型、OCR 或后端。
