# Windows x64 便携交付

当前状态（2026-10-21）：用户已明确先完成需求，本轮职责重构不制作、更新或迁移交付包。本文保留此前打包方式和原验收版本的历史迁移结果；旧 ZIP、哈希、路径和通过记录不能作为本轮重构结论。重新启用交付工作时，需先按当前职责树检查工程工具并验证新包。

交付包含实际安装的 `backend/bishi1/` 私有 Python 解释器、后端、Vue 构建产物和源码、七个业务 Skill、Hook/配置、测试、评测、示例、文档、题目原文和用户提供的数据，以及用户明确授权随本地交付保留的 `backend/.env`。启动应用不需要 Node.js、conda 或系统 Python；重新构建前端仍需要 Node.js 和 `npm ci`。

## 既有交付命令（当前暂停）

```powershell
.\backend\python.cmd .\backend\scripts\package-app.py --dry-run
.\backend\python.cmd .\backend\scripts\package-app.py --include-state
```

也可使用 `powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\package-app.ps1 -IncludeState`。默认 ZIP 为 `delivery/harbor-bishi1-windows-x64.zip`，可用 `--output` 或 PowerShell `-Output` 指定其他位置；报告为同名 `.package.json`，包含大小、SHA-256、文件分类与 CRC 检查结果。包内 `delivery-manifest.json` 说明包含范围及状态边界。清单使用顶层目录白名单，递归排除 `node_modules`、`.build`、`delivery`、`sample-check`、`.sample-check`、测试/字节码缓存、旧 ZIP 和 TypeScript 增量构建信息。

默认不包含运行历史，启动后建立新的本地检查点。`--include-state` 额外包含 `backend/data/assets/`、`backend/data/releases/`、`backend/data/checkpoints.sqlite` 和 `backend/.langgraph_api/.langgraph_ops.pckl`。SQLite 通过标准库 `sqlite3.Connection.backup` 取得含已提交 WAL 内容的一致数据库，检查通过后才写入 ZIP；不直接复制正在使用的 SQLite/WAL/SHM 文件。

GaussDB 业务记录和 Redis 服务仍是 `backend/.env` 指定的外部服务。带状态包不是独立的数据库全量备份；迁移后继续使用同一 GaussDB 时才能看到其历史业务记录。原始资产和 Skill 固定版本随包迁移，代码通过项目相对存储定位这些文件。

官方本地 dev 的线程/运行元数据约每 10 秒写入磁盘。打带状态包前，应暂停任务、等待在途调用结束和元数据刷盘。SQLite、资产、dev 元数据以及远端 GaussDB 之间没有跨存储原子快照；强制中止前未刷盘的 dev 元数据可能丢失。生产恢复保证需另用官方生产部署条件。

## 解压与迁移验证

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify-app-portability.ps1
```

脚本使用包内 Python 的 `zipfile` 解压到 `backend/.build/迁移 空格-<短ID>/`，日志保存在 `backend/.build/app-portability-<唯一ID>/`。默认迁移目录保持较短，以兼容未启用 Windows 长路径的机器和原始 EML 的长文件名。脚本从项目目录之外启动新解释器，检查解释器隔离及原生扩展、`pip check`、真实本地 stdio MCP 和全部离线测试。随后用新目录的解释器在 2025 端口启动官方 Agent Server，检查 `/ok`、`/api/health`、`/app/` 和样本清单；不会创建 Agent run。调用环境及临时验证配置将 `AGENT_SERVER_URL` 设为同一端口，通过 CLI 原生 `env` 映射固定覆盖值；HTTP 烟测临时将文本/视觉模型指向关闭的本地端口，避免访问在线模型，不修改 `backend/.env`。可用 `-Archive`、`-Destination`、`-Port` 覆盖路径或端口。

启动服务器时的工作目录显式设为新项目的 `backend/`，与 `backend/start.cmd` 的目录处理一致，使官方 dev 能读取迁移的元数据；解释器、MCP、测试均从外部工作目录调用。脚本只结束自己创建的服务器 PID，不结束其他 Python 或开发服务器，也不递归删除任何目录。迁移文件、执行日志和 `portability-report.json` 都保留，报告记录压缩包哈希、各项结果、服务器 PID 和 `backend/.env` 未修改校验。

带状态包优先用 `backend/tests/reports/structure-before.json` 核对本次移动前的三个历史任务；只有该基线不存在时，才回退至 `backend/tests/reports/restart-before.json` 的两个原有线程，并在存在 `backend/tests/reports/obs-agent-task.json` 时另核对新OBS任务。官方只读状态接口返回的检查点、人工中断 ID 和消息数必须保持一致，不提交恢复命令。旧 EML 任务的历史绝对路径由 `backend.infrastructure.assets.asset_file` 映射到新目录的资产；验证脚本断言解析结果属于新目录，并下载原件比对 SHA-256。

已批准 Excel 任务另检查正式导出：HTTP 200、顶层两条记录、金额为数字 20 和 50，均为 `CREATE/AP`。验证不创建 Agent run，也不恢复等待 OCR URL 的旧 EML 或等待币种/收费双方的新 EML 中断。Windows PowerShell 5.1 的 JSON 响应按原始字节显式解码为 UTF-8，避免无 charset 响应的中文文件名乱码；`ConvertFrom-Json` 解析的顶层JSON数组直接赋值接收，避免额外包装一层数组；本次已核对三个独立线程UUID及两条导出记录。

验证操作已先经 LangChain Docs MCP 的 `langsmith/cli`、`langsmith/use-threads` 与 API Reference MCP 的 `langgraph_sdk.get_state` 核对：使用 `langgraph-cli==0.4.37` 的原生 dev/config/env 能力，以及 `langgraph-sdk==0.4.8` 对应的线程状态 HTTP 合同；不执行自有 Agent 循环或恢复工具。打包、SHA-256、解压和 SQLite backup 使用标准库及 PowerShell，不属于 Agent 编排实现。

这是 Windows x64 同一台机器上的目录迁移验收；不代表同一套二进制环境支持 Linux/macOS。旧 DOC 转换使用配置的 `DOC_CONVERTER` 或可用的 LibreOffice `soffice`，转换程序不随 Python 运行时自动提供；外部 GaussDB、Redis、OCR 下载 URL 与模型服务按各自运行条件接入。

## 上一轮目录集中的验证状态（历史）

前后端已分别集中到 `backend/` 和 `frontend/`，当前启动、测试、打包及迁移命令均以新位置为准。新结构工作区已完成 **161 passed、43 warnings、4 subtests passed（30.93 秒）** 全量回归，`pip check` 与项目外运行时/SDK 离线签名通过。以 `backend/` 为工作目录启动的官方 Server 四个 HTTP 检查均为 200，健康为 `ok`，4 份原题样本可列出；三个历史任务的 checkpoint、消息数和原中断保留，旧 EML 原件哈希不变，已批准导出仍为 200/两条 CREATE/AP（20、50），OBS 待补充任务导出仍为 422，没有新建运行或恢复中断。 证据为 [pytest-structure.txt](../backend/tests/reports/pytest-structure.txt)、[pytest-structure.xml](../backend/tests/reports/pytest-structure.xml)、[structure-before.json](../backend/tests/reports/structure-before.json) 和 [structure-after.json](../backend/tests/reports/structure-after.json)。

本次新结构完整候选ZIP迁移已执行完成，验证脚本退出0、`Passed=true`。实际解压目录为 `backend/.build/迁移 空格-80a1e622/`，从项目外工作目录 `backend/.build/app-portability-4fab7cbf05d141028edf90fe65576234/outside cwd/` 调用包内解释器。运行时、原生扩展、OBS SDK离线签名、`pip check`、真实本地stdio MCP与全量回归均退出0，测试为 **161 passed、43 warnings、4 subtests passed（61.19秒）**。

| 已验候选包 | 实际值 |
| --- | --- |
| 文件 | `backend/.build/structure-candidate-v2.zip` |
| 字节数 | 103181917 |
| SHA-256 | `81c666aaedf6fe4514287c09c34d21c292423fccc9ca61ccc9e9ccb967591260` |
| 报告 | [app-portability-structure.json](../backend/tests/reports/app-portability-structure.json) |
| 测试输出 | [app-portability-structure-tests.txt](../backend/tests/reports/app-portability-structure-tests.txt) |

迁移后的官方Server以新 `backend/` 为工作目录启动，`/ok`、`/api/health`、`/app/`、`/api/samples`均返回200，健康为 `ok`。三个历史任务的checkpoint、消息数和原中断保持一致，全部 `Resumed=false`。旧EML原件返回1,479,995字节、SHA-256 `fad3298ec8fd3da0e092dfbed0a313be28170073f1e01125195a5dfe9b886e58`，资产实际解析至迁移目录。已批准任务正式导出200、两条CREATE/AP、数字金额20和50，没有新建Agent run。`.env`未改、在线模型请求0；仅自行创建的迁移Server PID38080已结束，2025无监听，迁移目录与日志保留。

该哈希只对应已完成验收的候选包。当时的标准名交付包已收录该阶段文档和报告并重新生成，最终大小和哈希以 `delivery/harbor-bishi1-windows-x64.package.json` 为准；不能将候选哈希写成最终包哈希。标准包与已验候选的运行文件一致，差异限于说明文档、验收报告和交付清单。以下目录调整前结果继续保留为历史证据。

## 2026-10-21 目录调整前的实测结果

OBS/SDK 版本完整验证命令退出 0，报告见 [app-portability-obs.json](../backend/tests/reports/app-portability-obs.json)，原始测试输出见 [app-portability-obs-tests.txt](../backend/tests/reports/app-portability-obs-tests.txt)。实际解压位置为 `C:\Users\dzx\Desktop\笔试1\.build\迁移 空格-2e9fd76f`，从 `.build/app-portability-f8cb14aafcd0497c8d5899f0cb73e37f/outside cwd/` 调用新解释器；运行时、原生扩展、OBS SDK 离线签名、`pip check`、真实本地 stdio MCP 均通过，全部 **161 项测试通过，43 warnings，另有 4 subtests passed，41.16 秒**。迁移服务 `/ok`、`/api/health`、Vue 生产页和样本接口均为 200；GaussDB、Redis 健康为 `ok`。

三个历史线程的 checkpoint、消息数及原中断 ID 保留，未提交恢复；其中新 OBS 任务保留 17 条消息及 `3676a55e09e11d5d196a6bb08e5b0e48` 中断。旧 EML 从新目录返回 1,479,995 字节，SHA-256 为 `fad3298ec8fd3da0e092dfbed0a313be28170073f1e01125195a5dfe9b886e58`；已批准 Excel 正式导出为两条 `CREATE/AP`，金额 20、50。`backend/.env` 前后哈希一致，验证模型端点固定为关闭的本地端口，没有在线模型请求。仅本次创建的服务 PID 39040 被结束，2025 端口已无监听，原 2024 服务继续返回 200。迁移目录及全部日志保留。真实 OBS 上传/OCR 已在原工作目录验证，目录迁移不重复外部请求；原始结果见 [obs-agent-task.json](../backend/tests/reports/obs-agent-task.json)。

本机 `LongPathsEnabled=0`。最初在较深目录使用 .NET 解压时失败；现改用项目 Python `zipfile`、较短的含中文空格目标，并排除 `.sample-check` 诊断缓存。旧版成功目录下最长包内文件的绝对路径为 **222 字符**。这是实际验证边界，不保证任意深目录均可解压；长文件名材料应解压到较短位置，无需修改系统长路径设置。

上述 OBS 版历史报告的 `ArchiveSha256` 对应完成上述验收的 102,877,154 字节候选包（`c8e08c09c4018042d718961be9e446b221ec2421c9b3759bc93ddb1848563a78`）。目录调整前曾收录该迁移报告和说明后重新生成标准名 ZIP；本次新结构候选包已完成独立迁移验收；当时的标准名交付包已收录该阶段文档和报告，最终交付大小与哈希以 `delivery/harbor-bishi1-windows-x64.package.json` 为准，不能把候选包哈希当作最终包哈希。

OBS 接入前的 140 项迁移结果保留在 [app-portability.json](../backend/tests/reports/app-portability.json)，不改写历史报告。本轮仍未完成真实旧 DOC 转换、长材料在线性能、独立真实财务金标或生产级硬崩溃恢复验收，详见 [验收记录](acceptance.md)。
