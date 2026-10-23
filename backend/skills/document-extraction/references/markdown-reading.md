# 按材料规模读取

intake_documents/read_materials的mode=read表示已提供窗口内容；短包直接综合，不为同一正文再调用grep和read_file。mode=search表示超过字符预算，全文仍在原生StateBackend，原生grep定位线索、read_file按行读。grep是字面匹配，不能把A|B当作正则。

read_materials(windows=[{"source_id":"真实ID","start_line":1,"end_line":120}, ...])可一轮读多份材料。返回next_line/truncated时自行判断还需扩读哪些位置。表格注意表头和连续明细、跨页的上下文，不能仅凭搜索首个命中声称读完全单。

原生文件和批量窗口都含[r...]标识，可以直接交给保存工具，无需再read_markdown_evidence。原始Markdown、map与原件保留，显示标识不改原文。无需模型填写逐块完成清单。
