import os
import re
import shutil
import subprocess

KNOWN_AGENTS = [
    {
        'id': 'agy',
        'name': 'Antigravity (agy)',
        'cmd': 'agy',
        'desc': 'Google Antigravity CLI',
        'category': 'Google',
        'supports_model': True,
        'supports_effort': True,
    },
    {
        'id': 'claude',
        'name': 'Claude Code',
        'cmd': 'claude',
        'desc': 'Anthropic Claude Code CLI',
        'category': 'Anthropic',
        'supports_model': True,
        'supports_effort': False,
    },
    {
        'id': 'opencode',
        'name': 'OpenCode',
        'cmd': 'opencode',
        'desc': 'OpenCode Terminal Agent',
        'category': 'Open Source',
        'supports_model': True,
        'supports_effort': False,
    },
    {
        'id': 'codex',
        'name': 'Codex CLI',
        'cmd': 'codex',
        'desc': 'Codex Coding Agent CLI',
        'category': 'OpenAI',
        'supports_model': True,
        'supports_effort': False,
    },
    {
        'id': 'aider',
        'name': 'Aider',
        'cmd': 'aider',
        'desc': 'Aider AI Pair Programming CLI',
        'category': 'Open Source',
        'supports_model': True,
        'supports_effort': False,
    },
    {
        'id': 'goose',
        'name': 'Goose',
        'cmd': 'goose',
        'desc': 'Goose Autonomous Developer Agent',
        'category': 'Block',
        'supports_model': False,
        'supports_effort': False,
    },
    {
        'id': 'shell',
        'name': 'Raw Shell',
        'cmd': 'shell',
        'desc': 'Direct interactive terminal shell (no agent)',
        'category': 'System',
        'supports_model': False,
        'supports_effort': False,
    },
]

_CACHE = None

def _clean_version(raw_text):
    if not raw_text:
        return ''
    m = re.search(r'\b(\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9.]+)?)\b', raw_text)
    if m:
        return 'v' + m.group(1)
    return raw_text.splitlines()[0].strip()[:16]

def detect_local_agents(force_refresh=False):
    global _CACHE
    if _CACHE is not None and not force_refresh:
        return _CACHE

    detected = []
    for spec in KNOWN_AGENTS:
        agent = dict(spec)
        if agent['id'] == 'shell':
            agent['installed'] = True
            agent['path'] = 'system default'
            agent['version'] = 'system'
            agent['badge'] = 'system'
            detected.append(agent)
            continue

        exe_path = shutil.which(agent['cmd'])
        agent['installed'] = bool(exe_path)
        agent['path'] = exe_path
        agent['version'] = None
        agent['badge'] = 'not found'

        if exe_path:
            try:
                res = subprocess.run(
                    [agent['cmd'], '--version'],
                    capture_output=True,
                    timeout=1.8,
                    shell=True
                )
                raw_out = (res.stdout or res.stderr or b'').decode('utf-8', errors='replace').strip()
                if raw_out:
                    ver = _clean_version(raw_out)
                    agent['version'] = ver
                    agent['badge'] = ver if ver else 'installed'
                else:
                    agent['badge'] = 'installed'
            except Exception:
                agent['badge'] = 'installed'

        detected.append(agent)

    detected.sort(key=lambda a: (0 if a['installed'] else 1))
    _CACHE = detected
    return detected

def get_installed_agents():
    return [a for a in detect_local_agents() if a['installed']]

def get_agent_info(agent_id):
    agent_id = (agent_id or '').lower().strip()
    for a in detect_local_agents():
        if a['id'] == agent_id:
            return a
    return None

def is_agent_installed(agent_id):
    info = get_agent_info(agent_id)
    return bool(info and info.get('installed'))

def build_startup_command(agent_id, model=None, effort=None):
    agent_id = (agent_id or 'agy').lower().strip()
    if agent_id == 'agy':
        cmd = 'agy'
        if model:
            cmd += f' --model {model}'
        if effort:
            cmd += f' --effort {effort}'
        return cmd
    elif agent_id == 'claude':
        cmd = 'claude'
        if model:
            cmd += f' --model {model}'
        return cmd
    elif agent_id == 'opencode':
        cmd = 'opencode'
        if model:
            cmd += f' --model {model}'
        return cmd
    elif agent_id == 'codex':
        cmd = 'codex'
        if model:
            cmd += f' --model {model}'
        return cmd
    elif agent_id == 'aider':
        cmd = 'aider'
        if model:
            cmd += f' --model {model}'
        return cmd
    elif agent_id == 'goose':
        return 'goose session'
    elif agent_id == 'shell':
        return ''
    return agent_id
