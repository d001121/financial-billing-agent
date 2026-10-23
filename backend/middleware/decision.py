"""One bounded structured decision for a free-text human reply.

The model owns intent understanding; the host owns validation and application.
This module only builds the request and the strict response schema.
"""

import json
from typing import Literal

from langchain.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class FieldEdit(BaseModel):
    charge_id: str | None = Field(default=None, description='当前记录的真实费用ID，多笔费用时必须逐笔指定')
    field: Literal['currency', 'payment_term', 'reference_no', 'amount',
                   'charge_item', 'posting_type', 'creditor', 'debtor',
                   'quantity', 'unit_price']
    value: str | float | None = None


class ReplyDecision(BaseModel):
    action: Literal['apply', 'confirm', 'defer', 'ask']
    fields: list[FieldEdit] = Field(default_factory=list)
    accounting_entity: str | None = None
    question: str | None = None
    reasoning: str = ''


SYSTEM = """你是账单人工回复的意图判定器。只输出一个结构化判断，不要调用工具。
规则：
- 用户明确修改字段或指定记账主体 → action=apply；fields 只列用户明确给出的字段，主体用 accounting_entity。
- 用户明确确认当前结果 → action=confirm。
- 用户表示暂缓、跳过、不需要主体、先不指定 → action=defer。
- 无法判断或缺少必要信息 → action=ask，并在 question 写一个具体问题。
- 用户明确表示某个字段没有、不存在或不适用时，该字段 value 返回 null，不要把这句话写进字段。
- 用户没有提到的字段不要出现在 fields 中；不要用 null 占位表示“未提及”或“待系统推断”。
- 每项字段修改带对应当前记录的charge_id；同一修改明确适用多笔时逐笔列出，不省略ID或猜测目标。
- 不编造用户没说的值；币种用三位代码，付款方式用 PP/CC，金额用数字。
"""


def decision_messages(task, reply):
    review = task.get('review_request') or {}
    payload = {
        'reply': reply.get('text'),
        'pending_question': review.get('question') or reply.get('question'),
        'choices': review.get('choices') or [],
        'revision': task.get('revision'),
        'accounting_entity': task.get('accounting_entity'),
        'records': [
            {
                'charge_id': record.get('charge_id'),
                'charge_item': (record.get('charge_details') or {}).get('charge_item'),
                'amount': (record.get('charge_details') or {}).get('amount'),
                'currency': (record.get('charge_details') or {}).get('currency'),
                'payment_term': (record.get('charge_details') or {}).get('payment_term'),
                'reference_no': (record.get('document_info') or {}).get('reference_no'),
                'posting_type': (record.get('financial_attributes') or {}).get('posting_type'),
                'quantity': record.get('quantity'),
                'unit_price': record.get('unit_price'),
            }
            for record in (task.get('records') or [])[:5]
        ],
    }
    return [SystemMessage(content=SYSTEM),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, default=str))]
