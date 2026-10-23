# 保存实际结果

save_document_extraction的result.charges是逐费用候选，包含题目字段及可用来源：charge_item、amount、currency、payment_term、reference_no、document_type、document_date、issuer、recipient、creditor、debtor和运输编号等。未提供的值为null。

引用采用evidence=[{"ref_id":"阅读返回的r标识","fields":["charge_item","amount"]}]；原文与偏移自动解析，也兼容真实source_id/anchor/quote。不同字段可对应不同引用。不要自造引用。

documents/totals只在有帮助时提供，不要求无费用附件的所有运输头字段。coverage是兼容字段，不参与逐块门禁。主控save默认返回当前版本核对结果，读完即可答复，由宿主保存题目JSON建议；不要求额外prepare_export。疑点和原文定位独立保存。
