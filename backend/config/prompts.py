"""Resolve configured default prompts before freezing task capabilities."""
from pathlib import Path


def resolve_agent_prompts(value, root):
    if not isinstance(value, dict):
        raise ValueError('Agent配置必须是对象')
    result = dict(value)
    if 'agents' not in value:
        return result
    definitions = value['agents']
    if not isinstance(definitions, list) or any(not isinstance(item, dict) for item in definitions):
        raise ValueError('agents必须是Agent配置对象列表')
    agents = []
    prompt_root = (Path(root) / 'agents').resolve()
    for definition in definitions:
        agent = dict(definition)
        if 'prompt_file' in agent:
            if 'prompt' in agent:
                raise ValueError('Agent prompt和prompt_file只能提供一个')
            reference = agent.pop('prompt_file')
            if not isinstance(reference, str) or not reference.strip():
                raise ValueError('Agent prompt_file必须是非空相对路径')
            if Path(reference).is_absolute():
                raise ValueError('Agent prompt_file必须是后端内的相对路径')
            path = (Path(root) / reference).resolve()
            if not path.is_relative_to(prompt_root) or not path.is_file():
                raise ValueError('Agent prompt_file须指向agents目录内的文件')
            agent['prompt'] = path.read_text(encoding='utf-8').strip()
        agents.append(agent)
    result['agents'] = agents
    return result
