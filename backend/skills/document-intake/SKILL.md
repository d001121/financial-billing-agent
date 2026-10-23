---
name: document-intake
description: 读取邮件和附件以及PDF、图片、Excel、Word，调用指定OCR并生成干净Markdown及真实来源映射。
metadata:
  version: "1.8.0"
  include_tools: "intake_documents"
---

# 接入材料供自主阅读

调用intake_documents接入当前任务上传的原件。邮件解码正文并递归处理附件；PDF/图片调用指定OCR，参考可用PDF文字/版式；Office保留表格顺序、工作表/单元格/段落。所有格式生成Markdown和原文映射，保留原始响应。

接入只返回材料清单；短材料随后调用read_materials一次批量读取正文和引用。只有read_materials返回mode=search的长材料才用原生grep/read_file或窗口读取。不需要创建分块完成清单。已pin的本Skill不再read_file重读。附件IO/OCR在现有有界并发中处理。

指定OCR的成功原始响应按文件内容和请求配置复用，不按上传ID或提示词版本失效；相同内容并发请求共享一次识别。每次上传仍重新生成来源ID、引用和产物，不复用主体或财务判断。PDF本地初读可先展示，远程OCR核对完成后才生成最终核验结果。OCR缓存、上传、请求与总耗时可在回执中核对。

本项目只向模型提供文本，图片查看由指定OCR代替。OCR响应的success/data.list是结构化单据，不冒充逐字全文；空chargeList不能证明图片没有费用，错误和未识别内容如实保留。

图片同时通过原生RapidOCRBlobParser补充`frame:N/local-text`全文（宿主默认开启，可用IMAGE_TEXT_OCR_ENABLE关闭）。该文本独立保留来源哈希、帧号、识别方法和耗时，可用于核对远程结构化响应漏掉的币种等字段；模型仍须结合表头与费用行判断语义。远程OCR未成功时，本地文本仅为预览，不能替代指定接口的成功验收。不得把本地OCR推测当作人工确认。

PDF有文字层时，除OCR结构化字段外还保留`page:N/layout`和`page:N/layout/financial`；Markdown按财务行→版式→plain→OCR排序。`pdf_layout_financial`保留原始layout行并提供解析后的`rows`（description/amount/currency/rate/quantity/pc），是费用表格的首选表示。

OCR需要远端可下载URL，宿主使用用户配置的OBS生成签名地址；秘密不进入模型参数。接口、便携调用和产物合同见[接入合同](references/intake-contract.md)与[pdf-ocr-md适配](references/pdf-ocr-md.md)。scripts/skill.py可独立使用。
