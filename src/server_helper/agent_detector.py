import os
import re
import shutil
import subprocess
import concurrent.futures

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

def _probe_version(agent):
    """Run `<agent> --version` cross-platform and return the raw output text.

    - POSIX: never use shell=True with a list argv (extra items are swallowed
      as $0/$1 and the agent launches with no args, spinning up an
      interactive REPL that then gets killed by the timeout).
    - Windows: .cmd/.bat shims (claude.cmd, codex.cmd, opencode.cmd, ...)
      cannot be executed by CreateProcess directly, so invoke them through
      `cmd.exe /c`. Native .exe paths run as-is.
    """
    exe_path = agent.get("path")
    if not exe_path:
        return None
    try:
        if os.name == "nt" and str(exe_path).lower().endswith((".cmd", ".bat")):
            argv = ["cmd.exe", "/c", exe_path, "--version"]
        else:
            argv = [exe_path, "--version"]
        res = subprocess.run(argv, capture_output=True, timeout=1.8)
        raw_out = (res.stdout or res.stderr or b"").decode("utf-8", errors="replace").strip()
        return raw_out or None
    except Exception:
        return None


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
        agent['badge'] = 'installed' if exe_path else 'not found'
        detected.append(agent)

    # Probe versions concurrently: sequential probes block startup for up to
    # N * timeout seconds (~10.8s) when agents hang; in parallel the worst
    # case is a single timeout window (~1.8s).
    targets = [a for a in detected if a['installed'] and a.get('path') and a['path'] != 'system default']
    if targets:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(targets))) as ex:
            raw_results = list(ex.map(_probe_version, targets))
        for agent, raw_out in zip(targets, raw_results):
            if raw_out:
                ver = _clean_version(raw_out)
                agent['version'] = ver
                agent['badge'] = ver if ver else 'installed'

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
    info = get_agent_info(agent_id)
    if not info:
        return agent_id
    if info['id'] == 'shell':
        return ''
    if info['id'] == 'goose':
        return 'goose session'
    cmd = info['cmd']
    if model and info.get('supports_model'):
        cmd += f' --model {model}'
    if effort and info.get('supports_effort'):
        cmd += f' --effort {effort}'
    return cmd
