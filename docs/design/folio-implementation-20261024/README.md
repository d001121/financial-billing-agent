# Folio 实现证据（合成数据）

最终核验见根目录design-qa.md。选择依据是../precision-ui-20261024/folio.jpg；后续用户明确要求海景融合并随页面滚动、日期可选、助手加宽/高度适配。

最终视觉：desktop-1024-final.png、desktop-1440-final.png、dashboard-mobile.png、detail-desktop.png、detail-desktop-800h.png、detail-mobile.png、detail-scrolled.png。
并排比较：comparison-final.jpg、comparison-focused.jpg。

date-range-desktop.png记录日期筛选68条，尚为中间海景横幅版本。desktop-1024-first.png、business-center.png、chart-bars.png、zoomed.png、source-drawer.png、tablet-820.png、management-mobile.png、new-material-mobile.png、empty-mobile.png均为迭代证据，不能当作最终海景样式。
sea-on/off-a/b为真实截图区域：开启两帧26499像素改变；关闭稳定后0像素改变。关闭截图为1024窗口，开启为1440窗口，只在各自同尺寸的两帧内部比较。

开发预览tests/visual/ocean.html?dataset=folio#/screen使用128条明确合成账单，默认#/tasks/ocean-demo为两费用详情。所有业务写入返回405，不连接真实后端/模型/OCR；不向生产增加样例数据。
