"""Host payload contracts shared by human approval and export."""


def export_binding(task):
    return dict(revision=task['revision'], action='export', args={'records': task.get('records', [])},
                tool_version='1.0.0', rule_version=task['capability']['version'],
                skill_versions=task['capability']['config']['skills'])
