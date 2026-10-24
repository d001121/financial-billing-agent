# 便携式 Python 环境

本项目使用 `backend/bishi1/` 中的私有 Python 运行时。目标系统为 Windows x64，无需安装 conda 或系统 Python。本轮先完成需求、代码和本机验收，暂不制作交付包或做移机验收；下文历史打包记录仅覆盖各自版本。

## 使用入口

在项目根目录的 PowerShell 中执行：

```powershell
.\backend\python.cmd --version
.\backend\python.cmd -m pip --version
.\backend\python.cmd -m pip check
.\backend\python.cmd .\backend\scripts\verify-runtime.py
.\backend\python.cmd .\backend\scripts\verify-mcp.py
```

环境已用于运行后端、官方 Agent Server、八个业务 Skill 和离线测试。直接依赖写在 `backend/requirements.txt`，当前安装的确切版本保存在 `backend/requirements.lock.txt`；恢复依赖使用 `./backend/python.cmd -m pip install -r backend/requirements.lock.txt`。本轮最终全量为 **234 passed、43 warnings、4 subtests passed，151.92秒**，报告为 `backend/tests/reports/office-confidence-pytest.txt`/`office-confidence-pytest.xml`；前端类型检查与生产构建已通过，不代表新版本已经通过移机或全部真实业务验收。

本轮业务版本为intake 1.2.0、extraction 1.2.1、evidence 1.1.2和新增billing-confidence 1.0.2；skills配置为v5，其他包的实际版本以各自SKILL.md及任务固定快照为准。历史任务继续使用原能力版本，不因目录或环境更新静默迁移。

2026-10-21 已补齐 `langchain[mcp]==1.4.6` 的可选依赖，FastMCP 为 4.1.2、MCP SDK 为 2.3.0；业务开发另加入 Deep Agents、Agent Server、SQLite 检查点、文档解析、GaussDB/Redis 驱动及测试所需依赖。最终版本和检查结果以交付锁文件与迁移报告为准。

OBS接入已安装官方 `esdk-obs-python==3.26.6` 并更新锁文件，配置由 `backend/.env` 读取。运行时检查增加真实SDK导入及离线签名验证，使用合成凭证和不可达示例域名，不上传材料或调用OCR。真实业务请求与验收见 `backend/tests/reports/obs-agent-task.json`。

从其他工作目录运行时，可用 `& '项目完整路径\backend\python.cmd' ...`。入口通过自身路径寻找解释器，不依赖系统 PATH。

## 环境组成

- `backend/bishi1/python.exe`：Python 3.13.16，来自 Python 官方 NuGet `python` 包。
- `backend/bishi1/Lib/site-packages/`：项目环境中的第三方依赖及 pip。
- `backend/bishi1/python313._pth`：使用相对路径隔离环境，并使解释器找到项目根与 `backend/` 包目录。
- `backend/python.cmd`：项目统一 Python 命令入口。
- `backend/scripts/bootstrap-runtime.ps1`：运行时重建脚本。
- `backend/scripts/verify-runtime.py`：离线检查解释器、依赖来源、MCP 导入和加密/Windows 原生扩展。
- `backend/scripts/verify-mcp.py`：用项目解释器启动本地 stdio MCP 子进程，验证发现、发现上下文退出后的工具调用及客户端显式关闭；不访问在线模型或外部业务服务。
- `backend/vendor/libreoffice/`：项目内LibreOffice 26.8.1.1，供Office转换、公式缓存重算与Word派生PDF；它是独立二进制工具，不是pip依赖。
- `backend/scripts/verify-portability.ps1`：打包、异地解压并从项目外启动的验证脚本，当前产物保存在 `backend/.build/`。
- `backend/scripts/package-app.py`、`backend/scripts/package-app.ps1`：完整应用打包，包含真实运行时和前端构建产物；可选带运行状态。
- `backend/scripts/verify-app-portability.ps1`：完整交付 ZIP 异地解压、项目外运行及第二端口 HTTP 验证，保留迁移报告和执行日志。

这是带完整解释器的私有运行时，不依赖普通 `venv` 对系统解释器的引用。第三方工具和二进制依赖安装后仍需要执行迁移验证。

## 重新取得运行时

交付包中已有 `backend/bishi1/` 时可直接使用。缺少运行时时，在项目根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\bootstrap-runtime.ps1
```

重建过程需要访问 NuGet 下载 Python 官方包；已有运行时会保留。此脚本仅重建解释器及随包附带的 pip，项目依赖按 `backend/requirements.lock.txt` 恢复。

官方包：`https://www.nuget.org/packages/python/3.13.16`

## 项目内 LibreOffice

当前 `backend/.env` 中的入口为：

```dotenv
DOC_CONVERTER=vendor/libreoffice/program/soffice.com
```

`backend/config/settings.py:office_converter()` 将相对路径解析到backend目录，与当前工作目录无关；也接受明确绝对路径。宿主将解析后的路径传给固定版本的document-intake，不依赖系统PATH已有Office。`office_preview` 是接入函数默认True的参数，当前宿主使用该默认值；没有 `OFFICE_PREVIEW` 环境变量开关。

项目目录内已展开官方Windows x86-64 MSI，运行版本26.8.1.1。下载时核对了官方MSI签名和SHA-256：`c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312`。原包为 `backend/vendor/libreoffice/LibreOffice_26.8.1_Win_x86-64.msi`，许可与NOTICE保留在同目录；详见 [vendor说明](../backend/vendor/README.md)。该哈希属于MSI，不是整个展开目录或派生PDF的哈希。

接入通过独立临时LibreOffice用户配置、headless转换及120秒转换超时，保留原件、派生件、转换器版本、参数、返回码、标准输出/错误和哈希。XLS优先转XLSX以保留公式来源；XLSX缺缓存或声明需要重算时使用LibreOffice产生可追溯缓存，仍保留原公式、原缓存、重算值和来源。外部链接、重算失败和无缓存金额继续复核，不以0替代。

DOC转DOCX后保留原件/派生关系；Word派生PDF只用于预览。页码映射以唯一规范化文本匹配绑定PDF字节哈希；重复或未匹配内容保持内容锚点，不能伪造页码/坐标，也不将渲染页当作原DOCX稳定物理页。字体、转换器和渲染输出变化时需要重新验证映射。本轮已有Office合成材料回归；真实复杂材料、在线业务及浏览器结果以实际验收记录为准，尚未进行包含这套新工具的交付包或移机验收。

## 历史打包与迁移验证（本轮暂停）

本轮按职责重构后的项目外运行时、原生扩展、OBS离线签名和pip check通过，证据为 `backend/tests/reports/responsibility-runtime.json`；用户已明确暂不处理交付包，以下保留上一轮打包方式和历史结果，不作为当前结论。上一轮目录集中已将解释器、入口和后端资源归入 `backend/`。新结构工作区已通过161项回归（30.93秒）、项目外运行时/SDK离线签名与pip check，官方服务四HTTP检查全200，三个历史任务及原中断和原件保留，见[验收记录](acceptance.md)。新结构完整候选ZIP从中文空格迁移目录、项目外工作目录通过161项回归（61.19秒），运行时/SDK/依赖/MCP、服务与历史状态检查全部通过，证据见[相关验证范围](acceptance.md)。当时的标准名交付包已收录该阶段文档和报告；下方140/161项旧报告保留为目录调整前的历史证据，其中绝对路径与候选哈希不改写。

完整应用的交付入口及状态边界见 [相关验证范围](acceptance.md)。构建后的 Vue 页面随包提供，启动不要求安装 Node.js；从根目录运行 `start.cmd`，界面为 `http://127.0.0.1:2024/app/`。

```powershell
.\backend\python.cmd .\backend\scripts\package-app.py --include-state
powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify-app-portability.ps1
```

默认输出 `delivery/harbor-bishi1-windows-x64.zip`。不传 `--include-state` 时不打本地任务历史；带状态时通过 SQLite backup API 保存检查点，并包含原件、Skill 固定版本和最后刷盘的官方 dev 元数据。外部 GaussDB 业务记录及 Redis 服务仍由 `backend/.env` 指定。打包前暂停任务并等待在途调用结束和元数据刷盘；官方 dev 约 10 秒刷盘不等于跨存储零丢失快照。

交付 ZIP 包含 `backend/bishi1/`、`backend/python.cmd`、应用代码、Vue 构建产物、配置、原题/样本及说明，按用户要求保留 `backend/.env`；排除 `backend/.build/`、`node_modules`、旧交付 ZIP 和测试缓存。脚本不递归删除任何目录。

正式交付前将包解压到另一处包含空格或中文的路径，从项目外工作目录运行解释器、检查依赖并执行项目测试，确认没有引用原始绝对路径。Redis、GaussDB、OCR 和模型服务仍由 `backend/.env` 配置提供，不属于 Python 运行时本身。

2026-10-21 补齐 MCP 依赖后，已重新通过 `pip check`、ZIP 解压到含中文和空格的新目录、从项目外启动的验证；Python、LangChain、MCP 依赖、加密及 Windows 原生扩展均能加载，本地 stdio 工具发现及发现上下文退出后调用也通过。该次运行时 ZIP 为 75,985,240 字节，验证产物保存在 `.build/portability-86934de7cdc14339848796894624d3d4/`。这是当前 Windows x64 机器上的环境迁移检查，尚未验证业务流程。

OBS 接入前的完整应用包曾在 `.build/迁移 空格-1885b544/` 通过 140 项离线测试及目录迁移，历史报告保留为 `backend/tests/reports/app-portability.json`。上一轮含 `esdk-obs-python==3.26.6` 的候选已在 `.build/迁移 空格-2e9fd76f/` 重新通过：运行时与 SDK 离线签名、依赖、真实 stdio MCP、161 项离线测试及 4 个子测试、第二端口服务与 Vue 生产页、GaussDB/Redis 健康、三个任务的 checkpoint/消息/中断、旧 EML 原件哈希及已批准 Excel 的两条正式导出。原始测试为 43 warnings、41.16 秒；未恢复中断、未调用在线模型、未修改 `backend/.env`。新版报告为 `backend/tests/reports/app-portability-obs.json`，测试输出为 `backend/tests/reports/app-portability-obs-tests.txt`。真实 OBS/OCR 已在原工作目录验证，迁移时不重复外部调用。路径长度、候选与最终包哈希区别和外部服务边界见 [相关验证范围](acceptance.md)。这是当前 Windows x64 主机上的目录迁移，不代表真实旧 DOC 或跨操作系统兼容性已经验收。

本地 MCP 验证使用 `sys.executable` 的项目私有解释器和绝对脚本路径，不调用可能记录旧路径的 `Scripts/*.exe`。在当前单服务 MCPConfig 下，发现的工具名为 `add`，调用 `19 + 23` 得到 `42`。这验证真实本地协议与适配器，不代表外部 MCP 的认证、网络或业务工具已通过。迁移脚本已纳入相同的 MCP 检查。

验证脚本在 `finally` 中以独立超时窗口调用 `adapter.client.close()`，显式释放可能保持连接的 stdio 子进程；原目录和迁移目录均复验通过，检查未遗留验证服务器进程。发现上下文退出后的调用可能复用底层会话，该检查不宣称重新建立了物理连接。

可重新执行迁移检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify-portability.ps1
```
