# 官方能力核对与最小缺口

核对日期2026-10-21；先通过LangChain Docs MCP搜索document loaders与knowledge-base，再通过API Reference MCP读取BaseLoader、Document、UnstructuredLoader，最后GitHub MCP读取固定源码。

| 操作 | 官方复用 | 本包最小业务缺口 |
| --- | --- | --- |
| 文档标准对象 | langchain-core Document | source内容与邮件出现位置分离、业务coverage/issues产物合同 |
| Loader调用 | BaseLoader.lazy_load，保留原生load/aload | 同一intake函数的Document投影，不自建加载执行框架 |
| PDF逐页读取 | 官方knowledge-base示例直接组合pypdf与Document | 题面强制OCR、切片原页映射和waiting_url状态；pypdf只作辅助预览 |
| 通用多格式 | UnstructuredLoader可本地partition或服务API，输出元素Document | 它的SDK请求为Unstructured PartitionRequest，不接受本题file/task/callBack/taskType合同；普通元素metadata不实现本项目附件出现身份、Excel公式缓存验证与派生件覆盖门禁 |
| 具体格式 | 直接采用Python email、Pillow、openpyxl/xlrd、python-docx、BeautifulSoup | 补来源锚点、格式限制与错误状态；不重写PDF/OOXML/XLS/MIME解析器 |
| Excel公式与旧格式 | 官方BaseLoader/Document投影，成熟openpyxl/xlrd读取，LibreOffice转换/重算 | 补原公式/原缓存/重算缓存的版本区分、原件与派生哈希、sheet/cell证据锚点；不解释公式或实现Office解析器 |
| Word结构与预览 | 官方Loader接口、python-docx原序读取、LibreOffice PDF渲染与pypdf逐页读取 | 补合并/嵌套/重复表头等证据metadata、原件与转换谱系及绑定PDF哈希的非权威预览页；不将排版设置当物理页 |
| OBS发布OCR输入 | 华为官方SDK `ObsClient.putFile/createSignedUrl/close` | 官方 `OBSFileLoader` 用于下载读取，补本题所需的原件/切片发布、签名下载地址及来源回执 |
| 派发前校验 | LangChain `AgentMiddleware.wrap_tool_call`，宿主已有 `policy.check` | Skill内部上传/OCR前调用注入的无参guard；不另建Hook链或把内部HTTP冒充独立工具调用 |
| 题面OCR结构化响应 | BaseLoader/Document提供原生内容与metadata投影，核对通用JSONLoader职责 | 仅验证本服务success/data.list合同并保留原JSON、传输范围与response_pointer；不复制通用加载器或模型提取层 |

UnstructuredLoader固定源码 `langchain-ai/langchain-unstructured@9bd9d35f7de9af389e46e1601dce54575b565d62:libs/unstructured/langchain_unstructured/document_loaders.py` 已读取：本地委托unstructured.partition.auto.partition，远端使用client.general.partition，返回元素text与metadata。它具有成熟解析能力，本包没有声称LangChain缺少多格式读取；本项目需要精确Excel单元格/公式、邮件出现层次与固定OCR协议，故采用官方文档展示的成熟格式库+Document方式补这些业务合同，而不为此再引入一套不同OCR服务。

Office 1.2.0调整前再次查询Docs MCP的document loaders/knowledge-base及API Reference MCP的 `BaseLoader`、`UnstructuredLoader`，同时检索Excel/Word专用Loader。索引未命中不能当作不存在；随后读取官方固定源码 `langchain-ai/langchain-community@f425a3ed1933173fb3694b81359d1519c4f82d36:libs/community/langchain_community/document_loaders/excel.py` 和 `word_document.py`（该轮GitHub MCP未暴露，以HTTP读取同一固定提交）。`UnstructuredExcelLoader` 委托 `partition_xlsx` 输出元素/HTML；`UnstructuredWordDocumentLoader` 委托 `partition_doc/partition_docx`，`Docx2txtLoader` 返回整体文本Document。这些是现成读取能力，但没有提供本项目原文件与转换件哈希、精确cell锚点、原公式缓存与重算版本区分、固定预览版本页映射的完整合同。因此继续复用 `BaseLoader.lazy_load` 与Document，格式解析与计算交给现成库/LibreOffice，只补必要证据metadata，不另写加载、执行、公式或分页框架。

Office验证运行时为LibreOffice 26.8.1.1；宿主负责提供转换器路径，本包不读取宿主.env或反向导入backend。实际公式50/20/70、真正二进制XLS/DOC转换和跨页DOCX渲染由合成格式fixture覆盖；这不等于题目独立真实金标或长材料在线性能验收。具体输入输出与限制见 `intake-contract.md`。

OBS能力于同日补查：先使用LangChain Docs/API MCP检索OBS集成，再读取固定官方源码 `langchain-ai/langchain-community@f425a3ed1933173fb3694b81359d1519c4f82d36:libs/community/langchain_community/document_loaders/obs_file.py`。`OBSFileLoader` 确实存在，其职责是 `ObsClient.downloadFile` 后调用 `UnstructuredFileLoader.load`；它不负责将本地材料上传并生成题面OCR可下载的URL。检索未命中本身不是能力缺失依据。本包只补这一发布职责，直接组合华为SDK，未重写OBS传输或签名算法。

SDK依据为 `huaweicloud/huaweicloud-sdk-python-obs@5558ee6d8b038e7d1d6296ad57531bb7522e027c`；适配版本 `esdk-obs-python==3.26.6`，使用 `putFile` 的contentType/SHA256元数据、2xx回执、SDK原生GET签名与close，不设置ACL。安装后已核对这些符号与参数；真实桶上传、签名下载及题面OCR验收以运行报告为准，不能由接口核对或离线测试推导。

题面响应于同日真实核实：PNG上传和签名下载均HTTP 200且下载哈希一致，指定OCR返回HTTP 200和 `success/data.list` 结构。首次报告 `tests/reports/obs-ocr-real.json` 保存当时未映射的partial，不能据此宣称财务验收通过。新增 `ocr_response_format=orderChange` 只校验已核实的服务状态与非空单据对象，保留对象原键值为 `ocr_structured` 块及 `/data/list/<index>` 引用；显式text pointer仍优先，默认text保持兼容。服务的页字段语义未核实，不转换成物理页/坐标；缺失币种、交易方等仍交后续证据/财务校验。

本项已先查Docs MCP的文档加载器标准接口、知识库投影用法，并检索JSONLoader及API Reference；当前索引未命中JSONLoader不作为它不存在的依据。随后核对固定官方源码 `langchain-ai/langchain-community@f425a3ed1933173fb3694b81359d1519c4f82d36:libs/community/langchain_community/document_loaders/json_loader.py`：GitHub MCP因OAuth refresh失败未能读取，改用HTTP读取raw.githubusercontent.com的同一固定提交，返回200。`JSONLoader._get_text` 对dict/list直接调用 `json.dumps(content)`，`text_content=False` 已提供通用JSON投影能力。本包同样使用标准库序列化；只补success检查、题面data.list业务单据边界、覆盖与来源锚点，不另建JSON loader。BaseLoader/Document继续承担原生加载和标准对象投影，也不在接入层再做模型费用提取。

本轮还通过Docs MCP读取custom middleware的wrap-style hooks，并用API Reference MCP核对 `AgentMiddleware`。`wrap_tool_call` 包围LangChain工具handler，Skill内部SDK/HTTP不会自动成为独立工具事件。当前内部guard复用宿主任务暂停、revision、启停及必需Hook检查；不独立计数、不逐SDK请求拦截。共享计量保留在外层原生工具/middleware边界。

本包不实现Agent loop、Skill加载/执行器、重试、调度、Hook派发或中断。宿主原生SkillsMiddleware负责工具披露，宿主通过函数调用、OBS配置与受控HTTP/guard回调装配。

实际安装版本已在项目便携解释器核对：langchain1.4.6、langchain-core1.6.12、pypdf6.21.1、Pillow13.0.0、openpyxl3.1.5、xlrd2.0.2、python-docx1.2.0、beautifulsoup4.15.0、esdk-obs-python3.26.6。详细锁定由根requirements.lock.txt统一维护。

官方入口：

- https://docs.langchain.com/oss/python/langchain/knowledge-base
- https://docs.langchain.com/oss/python/integrations/document_loaders
- https://reference.langchain.com/python/langchain-core/langchain_core/document_loaders/base/BaseLoader
- https://reference.langchain.com/python/langchain-core/langchain_core/documents/base/Document
- https://reference.langchain.com/python/langchain-unstructured/langchain_unstructured/document_loaders/UnstructuredLoader
- https://docs.langchain.com/oss/python/langchain/middleware/custom
- https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware
- https://github.com/langchain-ai/langchain-community/blob/f425a3ed1933173fb3694b81359d1519c4f82d36/libs/community/langchain_community/document_loaders/obs_file.py
- https://github.com/langchain-ai/langchain-community/blob/f425a3ed1933173fb3694b81359d1519c4f82d36/libs/community/langchain_community/document_loaders/json_loader.py
- https://github.com/langchain-ai/langchain-community/blob/f425a3ed1933173fb3694b81359d1519c4f82d36/libs/community/langchain_community/document_loaders/excel.py
- https://github.com/langchain-ai/langchain-community/blob/f425a3ed1933173fb3694b81359d1519c4f82d36/libs/community/langchain_community/document_loaders/word_document.py
- https://support.huaweicloud.com/intl/en-us/sdk-python-devg-obs/obs_22_0001.html
- https://github.com/huaweicloud/huaweicloud-sdk-python-obs/tree/5558ee6d8b038e7d1d6296ad57531bb7522e027c
- https://pypdf.readthedocs.io/en/stable/user/merging-pdfs.html
- https://docs.python.org/3/library/email.parser.html
- https://python-docx.readthedocs.io/en/latest/api/document.html
- https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html
