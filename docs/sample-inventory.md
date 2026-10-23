# 原题样本清点

本页保留最初清点时的结构事实；表中的 waiting_url/partial 和“未在线OCR”均为当时状态。目录调整后，四份原件位于 `backend/data/samples/`，题面位于 `docs/assignment/`。后续已获准启用OBS并完成真实原题OCR和新EML接入，结果见 [验收记录](acceptance.md)及 [obs-agent-task.json](../backend/tests/reports/obs-agent-task.json)；原始manifest与报告不改写。

2026-10-21 已用项目便携解释器和 `document-intake` Skill读取用户给出的 `backend/data/samples/`。机器可读来源、大小、SHA256、父子关系及状态在 `backend/evals/datasets/manifest.json`；原件未修改。

| 原件 | 验证到的结构 | 当前接入状态 |
| --- | --- | --- |
| PDF示例账单1.pdf | 3页；原生辅助文本可读 | waiting_url：指定OCR仍缺服务可下载URL |
| PDF 示例账单2.pdf | 1页；原生辅助文本可读 | waiting_url |
| 图片示例.png | PNG，598×841，1帧；已人工查看原图 | waiting_url |
| 深圳容宇 PRE-ALERT…Arrived time 2026-10-30.eml | 已读取邮件头、纯文本正文，另有1幅内嵌JPG及2个PDF附件 | partial：正文已读，附件OCR待URL |

邮件内部清点：

| 出现位置 | 原附件名 | 已核对结构 |
| --- | --- | --- |
| mime/1/2 | InsertPic_C25B.jpg | JPEG，1500×770，1帧 |
| mime/2 | 4055331281 MBL.pdf | 1页PDF |
| mime/3 | 4055331281 HBL.pdf | 1页PDF |

两份PDF附件名中数字与MBL/HBL之间为U+00A0不换行空格；保留原名，存储安全名及内容哈希单独管理。四份原件及三个附件合计七个出现位置，PDF页数合计六页。

样本的具体业务检查重点：

- 账单2的辅助原生文本有两条同名HANDLING CHARGE，金额65与35，另有1310.40，总计1410.40；提取应保留两个不同原始行。此项目前是预览核对发现，不能作为已完成指定OCR的证据。
- 账单1含245.0000当期费用及多段条件性收费条款；条款中的25、1100、150等金额不应仅凭出现数字就新增费用。原生文本不足以证明视觉表格完整。
- 邮件正文有本次H/C $50及MBL/HBL、箱号等上下文；实际付款方向仍需调用方逐次提供记账主体。
- PNG已人工查看，WHARFAGE ADMINISTRATION FEE 5.00与WHARFAGE 21.90，USD合计26.90可辨；这只是人工原图观察，未完成OCR、完整字段标签或财务方向金标准。

当前manifest的 `financial_ground_truth` 为null；没有用模型生成答案冒充标准答案。这些材料已经参与开发，角色为development_inventory，不能再作为独立最终holdout。公开或打包真实材料的范围由交付要求另行确定，不自动上传。

缺少真实XLS/XLSX、DOC/DOCX、TIFF、长PDF、已有账单与明确修改指令。包内 `backend/skills/document-intake/tests/test_intake.py` 生成临时合成材料验证格式合同，明确不属于原题业务标签。当前14项离线检查覆盖MIME递归与同字节不同出现、损坏附件保留兄弟项、XLSX公式缓存/隐藏/合并、DOCX嵌套/合并/内嵌图、TIFF逐帧、PDF切片原页映射、OCR协议/响应/错误、官方Loader和项目外CLI。

清点重现命令：

```powershell
.\backend\python.cmd backend/skills/document-intake/scripts/inventory.py 'backend/data/samples' --output-dir 'backend/data/sample-inventory' --manifest 'backend/evals/datasets/manifest.json'
.\backend\python.cmd -m unittest discover -s backend/skills/document-intake/tests -v
```

清点当时尚未验证真实在线OCR及DOC转换。后续真实OCR接入已有独立报告；本轮补齐项目内LibreOffice，以明确标注的合成二进制OLE DOC/XLS完成实际转换、公式重算和Word渲染，见 `backend/tests/fixtures/office/README.md` 与 `backend/tests/reports/office-confidence-pytest.txt`。该格式验证不替代原题或独立真实业务金标。PDF辅助预览单独保存在preview_text，authoritative=false；正式source.text不混入辅助预览。
