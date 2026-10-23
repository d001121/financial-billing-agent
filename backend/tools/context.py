"""Expose only the current task context through a native LangChain tool."""
from langchain.tools import tool
from backend.infrastructure.repository import repository
from backend.config.transactions import read_config
from .artifacts import verification_summary


def context_tool(task_id):
    @tool
    def read_task_context() -> dict:
        """读取当前任务、revision、材料清单、已有产物及问题。文件正文通过提取分块读取。"""
        task = repository().get('task', task_id)
        keys = ('id', 'revision', 'accounting_entity', 'instructions', 'asset_ids', 'existing_records',
                'charges', 'records', 'coverage', 'issues', 'update_instructions', 'usage', 'control',
                'source_urls', 'ocr_text_pointer', 'documents', 'feedback', 'history_mode', 'history_lookup')
        context = {k: task.get(k) for k in keys}
        context['assets'] = [repository().get('asset', a) for a in task['asset_ids']]
        context['sources'] = [{k: s.get(k) for k in ('source_id', 'name', 'status', 'format', 'parent_source_id')}
                              for s in task.get('sources', [])]
        bundle = (task.get('preparation') or {}).get('material_bundle')
        if bundle and any(s.get('markdown') for s in task.get('sources', [])):
            bundle = {k: v for k, v in bundle.items() if k != 'shared_context'}
        context['material_bundle'] = bundle
        context['capability_version'] = task['capability']['version']
        context['experience_references_enabled'] = (
            task['capability']['config']['runtime'].get('use_reviewed_experiences', True) and
            read_config('runtime').get('use_reviewed_experiences', True))
        context['experience_reference_count'] = sum(
            ' '.join(str(item.get('accounting_entity') or '').split()).casefold() ==
            ' '.join(str(task.get('accounting_entity') or '').split()).casefold()
            for item in task['capability'].get('experiences', [])) if context['experience_references_enabled'] else 0
        context['verification'] = verification_summary(task.get('validation') or {})
        if task['capability']['config']['runtime'].get('agent_style') == 'codex':
            # Archive/provenance trees stay in artifacts; reviewers receive values
            # plus usable citations, rather than several copies of every check.
            for key in ('charges', 'records', 'existing_records', 'documents'):
                rows = []
                for row in context.get(key) or []:
                    item = {k: v for k, v in row.items() if k not in (
                        'provenance', 'field_support', 'audit_trail', 'source_links', 'issues')}
                    if 'evidence' in item:
                        item['evidence'] = [{k: v for k, v in ref.items() if k in (
                            'ref_id', 'field', 'fields', 'source_id', 'anchor', 'quote')}
                            for ref in item['evidence']]
                    rows.append(item)
                context[key] = rows
            context.pop('coverage', None)
            context['artifact'] = f'/api/tasks/{task_id}/artifacts'
        return context
    return read_task_context
