# 接入与来源合同

## Python输入

入口 `scripts/skill.py:intake_document(path, *, ...)`，参数：

| 参数 | 默认值与意义 |
| --- | --- |
| source_url | 根材料的远端可下载HTTP(S) URL；不会自动用于邮件附件或PDF子文件 |
| output_dir | 产物目录；省略时在输入同目录的 `.intake/<path-hash>/` |
| ocr_endpoint | 题面指定的 `http://36.103.199.11:5002/process` |
| ocr_request | 注入函数，关键字 `endpoint,payload,timeout`，返回httpx.Response或可JSON序列化值；可由宿主接入受控HTTP客户端 |
| url_resolver | 注入函数 `(Path, mapping)->str或None`，提供对应原件、切片或图片帧的可下载URL，优先于OBS发布 |
| ocr_text_pointer | 明确JSON Pointer，例如 `/data/text`；仅在核实真实响应后配置，目标必须为非空字符串；显式配置时优先于orderChange映射 |
| ocr_response_format | `text`（默认兼容）或 `orderChange`；后者读取已核实的题面结构化响应，见下文 |
| pdf_pages_per_slice | 20页；原页索引以1起始，OCR没有虚构的page-range参数 |
| max_depth/max_files/max_total_bytes | 8/200/104857600；超限项有来源和失败问题，不静默截断 |
| doc_converter | LibreOffice soffice路径；省略时在PATH发现soffice.com/soffice/libreoffice。宿主可注入项目自带的绝对路径；Skill不自行读取.env |
| office_preview | `true`；可用转换器存在时为Word生成版本化PDF预览。设为false可只解析内容与锚点，不进行预览转换 |
| occurrence_id | 根出现位置标识，默认root；同内容在不同根输入出现时宿主传不同ID |
| obs_options | 可选OBS配置字典；仅 `enabled is True` 且没有URL时自动发布，具体字段见下文 |
| request_guard | 可选无参回调，在OBS上传、OCR派发及Office转换前分别调用；抛出异常即阻止该次外部操作 |

OCR固定请求体 `{"file":url,"task":"orderChange","callBack":"","taskType":""}`，httpx连接10秒、读取300秒。本包不自行重试，原生宿主重试应重新核对预算、版本和暂停。缺URL且未启用OBS时返回 `ocr_waiting_url`。localhost URL不能给远端服务使用。可下载URL是否真实可达仍须通过真实调用验证。

## OBS自动发布

`obs_options` 接受 `enabled,access_key_id,secret_access_key,server,bucket,security_token,object_prefix,socket_timeout,expires`。`server` 必须为HTTPS；`security_token` 可为空，前缀默认 `images`，超时默认60秒；签名默认3600秒，至少300秒。凭证由宿主配置注入，不从材料或模型参数中读取。当前后端从 `.env` 的 `OBS_*` 映射这些连接项，不将凭证保存到任务或能力配置；旧Skill快照不接收新增参数。

每个OCR输入先使用 `source_url`，没有提供时询问 `url_resolver`；仍无URL且 `enabled is True` 才延迟创建 `OBSPublisher`。原件、邮件附件、PDF切片和多帧图片分别按实际传输文件发布，不把根文件URL误用于派生件。已有非空URL不会因下载失败自动改走OBS。

发布直接组合华为官方SDK `ObsClient.putFile` 与 `createSignedUrl("GET", ...)`。对象key为 `<object_prefix>/workorder-agent/<文件SHA256><扩展名>`，上传包含SHA256元数据和内容类型；不修改桶或对象ACL，也不依赖匿名公开读取。签名URL使用SDK原样返回地址，不替换成公开域名或自行拼签名。SDK使用certifi证书路径、正数超时和 `max_retry_count=0`；签名协商仍可能产生SDK内部请求，不能将一次调用等同于一次HTTP。

上传只有HTTP 2xx才产生成功回执。`source.metadata.obs_objects` 保存bucket、object_key、SHA256、字节数、HTTP状态、ETag、request_id、上传时间，以及原页/帧/source映射；签名成功后补充过期时间。回执不保存密钥或签名URL。上传或签名失败记录 `obs_upload_failed`，不派发OCR；上传已成功但签名失败时仍保留上传回执。`intake_document` 在finally中关闭本次创建的OBS客户端。

宿主注入的 `request_guard` 在上传和OCR派发前重验任务暂停/取消、revision、Skill启停及必需Hook状态；拒绝会停止对应调用。它不单独增加工具调用计数，不逐一拦截SDK内部HTTP，也不会撤回已发出的请求。外层原生LangChain工具/middleware负责工具级派发与共享计量，本包没有另建Hook或工具执行器。

## OCR响应映射与来源

HTTP原始字节与JSON分别保存为 `ocr_wire_response`、`ocr_raw`，先保存原响应再映射；非JSON、HTTP错误、超时与映射失败分别报错。`text` 模式保留既有行为：原响应为非空字符串时直接形成 `ocr_text` 块，或按显式 `ocr_text_pointer` 取得非空字符串；不猜测字段。

2026-10-21真实PNG响应已确认是 `{"success":true,"data":{"list":[{"invoiceNumber":...,"chargeList":[...],...}],...},...}`。它是OCR服务整理的结构化结果，不能当原件逐字转录。`orderChange` 模式且没有显式text pointer时，先要求 `success is True`，再要求 `/data/list` 为非空列表且每项均为非空字典。服务未确认成功记录 `ocr_service_failed`；结构不符记录 `ocr_response_invalid`，保留原响应并进入失败或部分状态。

每个单据对象以保留原键值的JSON序列化为一个 `ocr_structured` 内容块，锚点为 `<传输锚点>/document:<1起始序号>`，metadata包含 `raw_response`、`response_pointer=/data/list/<0起始索引>`、`response_format=orderChange` 及传输原页/帧映射。这只是服务响应投影，后续费用提取、字段标准化、覆盖与财务校验仍由对应Skill完成。缺失的币种、交易方或主体不能由适配器补造；原题PNG已观察到字段缺失，相关结果须按证据进入复核。

服务返回的 `page_index/pages_split` 尚未确认物理页/坐标语义，仅随原始JSON保留。多页传输片段只有原页范围，没有逐项页归属；仅单页片能据真实传输边界设置page。图片帧同样来自实际传输边界。本包没有生成页内坐标或原件表格结构；`chargeList` 是服务结构，不能冒充原件表格坐标。输入URL、宿主guard与网络回调不能从文档中的文字取得授权。

首次真实接入证据为项目根 `tests/reports/obs-ocr-real.json`：上传HTTP 200、签名下载HTTP 200且SHA256一致、题面OCR HTTP 200。该报告保留了当时尚未配置结构映射的 `partial/ocr_response_unmapped` 状态；不改写为后续映射或整体财务验收成功。后续任务与测试结果另按实际运行记录。

OCR原响应产物提供由文件/切片字节哈希、包版本、接口、响应格式与文本映射配置组成的cache_key，配置摘要另存。宿主按相同输入及版本复用不可变产物，包内不另建缓存服务。OCR服务版本目前未知，明确记录unknown；外部服务升级无法由现有键自动发现，不能承诺跨升级缓存一致性。

## 输出

`{skill,version,status,sources,issues,coverage,artifacts}`。status为 `ready/waiting_url/partial/failed`。

source包含 `source_id,content_id,parent_source_id,occurrence_id,name,path,size_bytes,format,status,mime_type,text,blocks,metadata`。

- content_id是字节SHA256；source_id由父出现、MIME位置/根出现ID及内容哈希派生，重复附件不丢出现语境。
- blocks都有 `source_id,anchor,text,authoritative`，并按格式带page、sheet/row/cells、part等。`structure_only=true`的Word行块是结构索引，不应与单元格内容重复提费。source.text只含正式内容块且排除结构索引，source.preview_text单独保存辅助预览；没有OCR时PDF的text为空，不能用preview_text伪装正式OCR完成。
- 原件是path指向的不可覆盖输入；artifacts记录派生文件、SHA256、原页/帧与source_id。大产物由宿主保存，Agent只拿摘要和引用。
- issues含 `code,message,source_id,scope,blocking`。附件失败会保留失败source并使父邮件partial。
- coverage提供每个出现的状态和块数；PDF/图片另提供OCR范围/帧状态。来源接入不等于语义提取覆盖闭合。

`ShippingDocumentLoader`复用官方BaseLoader，只实现lazy_load，输出官方Document的文本/metadata投影；详情保留在loader.result。同一业务函数供工具、CLI和loader调用。

## 格式行为和限制

EML使用标准库MIME与编码解析，plain/html正文择一并记录替代部分；附件/内嵌图/嵌套邮件递归。文件名去除路径与Windows保留字符，保留原名（包括不换行空格）。文本附件不会误当重复正文。HTML用BeautifulSoup去script/style并转文本。

PDF使用pypdf逐页清点及辅助文本，长件由PdfWriter产生连续子文件；切片与模型语义分块分开，跨页重建由document-extraction负责。PDF与图片都必须走题面OCR，native_preview不能计为OCR成功。

图片使用Pillow读取/校验，多帧TIFF生成各帧PNG并保存原帧映射，逐帧取得URL并执行OCR。自动上传仅由宿主明确启用的OBS配置触发。

XLSX使用openpyxl分别读取原公式与原缓存，保留所有sheet（含hidden/veryHidden）、sheet/row/cell锚点、隐藏行列、合并区域、日期、数字格式及Excel表格范围和行角色。每cell保存 `formula,formula_origin,formula_range,value,cached_value,original_cached_value,value_origin`，原公式不由本包解释。缓存缺失、手工计算或工作簿要求刷新时，若存在转换器，直接用LibreOffice生成新的XLSX以取得计算缓存；使用原公式及新缓存，不覆盖原件。转换失败、仍缺缓存、计算错误或外部工作簿链接会形成阻断问题，不把缺失值补为0。未配置转换器时仍读取原缓存，明确报告需要重算或缺缓存。

XLS存在转换器时先由LibreOffice转成XLSX再读取，source身份、content_id和锚点仍属于原XLS；公式注明 `formula_origin=libreoffice-conversion`，派生件与原件分别保存哈希，不能声称它是从原XLS直接回读的表达式。无转换器或转换失败时回退xlrd读取缓存、合并与隐藏信息，并以 `xls_formula_lineage` 明确阻断；xlrd本身不提供可靠公式血缘。

DOCX使用python-docx按原顺序读取段落、表格、嵌套表格；合并cell代理指向保留锚点，避免重复提费。段落保存part、XML路径、分页/同页设置及所属表格/行/cell；结构行另保存重复表头、禁止跨页拆行及grid信息，不把这些排版设置当作真实页码。读取页眉页脚；用OOXML补充文本框、脚注/尾注清点，并标记修订和图片。按XML图片出现位置解析关系，导出原图递归执行OCR，保留part/relationship_id/package_member；外链图不会自动下载，非位图绘图明确待核对。未完成修订视图解析和内嵌图OCR时返回partial。

DOC直接组合LibreOffice转换为DOCX，保留原DOC source和派生DOCX child，后者的 `parent_source_id` 指原DOC，metadata保存原件content_id和转换版本。转换失败保留日志与具体问题；缺转换器报告 `doc_converter_missing`。每次Office转换使用独立临时UserInstallation，版本查询10秒、转换120秒；无论成功失败保存 `conversion_log`，含命令、转换版本、退出码/stdout/stderr、原件/派生SHA256。转换产物存于 `office-conversion/<source_id>/<purpose>/`，本包不自写公式引擎。

启用 `office_preview` 且转换器可用时，DOCX由LibreOffice渲染为PDF，artifact kind为 `office_word-preview`。`source.metadata.office_preview` 合同为 `{path,format:"pdf",sha256,page_count,converter_version,original_content_id,authoritative:false}`。pypdf仅用于读取该渲染的逐页文本；归一化文本在整份预览中仅出现一次时，内容block可增加 `preview={pages:[1起始页码],artifact_sha256,mapping:"unique-normalized-text-match",authoritative:false}`。重复或无法匹配的文本不猜页码。原始Word的anchor保持不变，不设置block.page，`physical_pages_known=false`；预览页绑定具体PDF哈希，不能替代原件证据。

版本1.2.0新增Office转换、公式缓存重算与Word渲染合同。`tests/fixtures/office/` 的样例是由openpyxl/python-docx及真实LibreOffice生成的合成格式fixture，含真正OLE二进制XLS/DOC；它们验证格式接入、计算及来源关系，不属于真实题目业务金标或在线OCR验收。

错误会保留结构化范围，不转换成“0条费用成功”。业务附件不执行。单个Skill可携带本目录与requirements迁移，宿主需要注入文件存储、受控网络及自己的校验策略。
