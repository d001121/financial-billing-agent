"""Read persisted projections; the pinned financial Skill owns history policy.

Docs MCP /oss/python/langchain/tools: application-scoped database access in
native tools. Reference MCP langchain_core tool conversion; installed
langchain 1.4.6/core 1.6.12, deepagents 0.7.30. No SQL agent or extra model call.
"""
from backend.extensions.skill_versions import function


TASK_FIELDS = ('id', 'revision', 'accounting_entity', 'status', 'deleted_at', 'validation', 'approval')
RECORD_FIELDS = (
    'charge_id', 'revision', 'operation', 'document_info', 'transaction_party',
    'charge_details', 'financial_attributes', 'source_id', 'document_id', 'line_id',
    'creditor', 'debtor', 'bill_of_lading', 'booking_no', 'container_no', 'quantity',
    'unit_price', 'line_role', 'raw_charge_item', 'raw_payment_term', 'raw_amount',
    'raw_currency', 'history_identity', 'history_match',
)


def prepare_history(task, repo):
    """Complete projection query; never silently search only the latest 100."""
    previous = repo.list_projection('task', TASK_FIELDS, arrays={'records': RECORD_FIELDS},
        limit=None, exclude_deleted=True) if task.get('accounting_entity') else []
    return function(task['capability'], 'billing-reconciliation', 'retrieve_history')(
        dict(task=task, historical_tasks=previous))
