/**
 * ServerHelper - Lightweight i18n (English / 中文)
 * Static HTML is translated via data-i18n* attributes; dynamic strings in
 * app.js go through window.t(key, vars). Selection persists to localStorage
 * and is mirrored to the backend setting `settings.language`.
 */
(function () {
  const DICT = {
    en: {
      'mem.title': 'Resident memory',
      'sidebar.workspace': 'Task Workspace',
      'sidebar.newTask': '+ New Task',
      'sidebar.servers': '🖥️ Servers',
      'sidebar.agentConfig': '⚙️ Agent Model Config',
      'sidebar.broadcast': '📢 Broadcast to Tasks',
      'sidebar.language': '🌐 中文',

      'toolbar.modeAgent': '🤖 Agent Chat',
      'toolbar.modeTerminal': '🖥️ Terminal',
      'toolbar.modeSplit': '🔲 Split View',
      'toolbar.files': '📁 Remote Files',
      'toolbar.hardware': '⚡ Hardware',
      'toolbar.stopAgent': '⏹️ Stop Agent',
      'toolbar.closeTask': '✕ Close Task',

      'empty.title': 'No active task workspace',
      'empty.desc': 'Click "+ New Task" (top-left) to connect a remote server, then manage multiple project tasks concurrently in this window while your local Coding Agent reasons, reviews and executes.',
      'empty.createFirst': '+ Create your first task',

      'agent.ready': '🤖 Agent ready. Type a request below (e.g. debug the current error, check GPU memory, or run a development task).',
      'agent.chipFiles': '📁 Inspect dir & code',
      'agent.chipFiles.prompt': 'Inspect the file structure and code in the current remote working directory',
      'agent.chipGpu': '⚡ Check GPU / hardware',
      'agent.chipGpu.prompt': 'Show current server GPU memory and CPU/memory usage',
      'agent.chipGit': '🌿 Check Git status',
      'agent.chipGit.prompt': 'Run git status to show the latest branch and changes',
      'agent.inputPlaceholder': 'Send an instruction to this remote task\'s Coding Agent... (Enter to send, Shift+Enter for newline)',
      'agent.send': 'Send',
      'agent.thought': '🤔 Agent reasoning (Step {step})',
      'agent.toolCalling': '⚡ Calling tool:',
      'agent.running': 'Running...',
      'agent.waiting': 'Waiting for remote output...',
      'agent.done': 'Done',
      'agent.noOutput': '(no output)',
      'agent.error': 'Error: ',

      'terminal.clear': 'Clear',

      'files.title': '📁 Remote Files',
      'files.refresh': 'Refresh',
      'files.up': '📁 .. (up one level)',
      'files.readError': 'Cannot read directory: ',
      'files.failed': 'failed',

      'newTask.title': 'New Task Workspace',
      'newTask.nameLabel': 'Task name (identifier)',
      'newTask.namePh': 'Enter a task name',
      'newTask.modeLabel': 'Run mode',
      'newTask.modeRemote': '🌐 Remote SSH & Agent task (direct to server)',
      'newTask.modeLocal': '💻 Local Agent terminal (Claude Code / agy / PowerShell)',
      'newTask.serverLabel': 'Target remote server',
      'newTask.manageServers': '+ Manage servers',
      'newTask.dirLabel': 'Remote working directory (auto cd)',
      'newTask.dirPh': 'e.g. /home/user/workspace/project',
      'newTask.startupLabel': 'Startup command (optional)',
      'newTask.startupPh': 'e.g. conda activate py310',
      'newTask.localCmdLabel': 'Local Agent command line',
      'newTask.localCmdPh': 'claude, agy or powershell',
      'newTask.localCwdLabel': 'Local working directory (optional)',
      'newTask.localCwdPh': 'Leave blank for the default project dir',
      'newTask.submit': 'Create & Connect',
      'newTask.noServer': 'Please select or add a target remote server first!',
      'newTask.createFailed': 'Create failed: ',

      'servers.title': 'Remote Server Management',
      'servers.configured': 'Configured remote servers',
      'servers.add': '+ Add server',
      'servers.formTitleAdd': 'Add new server',
      'servers.formTitleEdit': 'Edit server',
      'servers.nameLabel': 'Server name / label',
      'servers.namePh': 'e.g. Remote training server A',
      'servers.hostLabel': 'Host IP / domain',
      'servers.portLabel': 'Port',
      'servers.userLabel': 'Username',
      'servers.authLabel': 'Auth method',
      'servers.authKey': 'SSH private key',
      'servers.authPassword': 'Password',
      'servers.authKeyShort': 'SSH key',
      'servers.authPasswordShort': 'password',
      'servers.keyPathLabel': 'SSH private key path (blank tries default ~/.ssh/id_rsa)',
      'servers.keyPathPh': 'C:\\Users\\name\\.ssh\\id_rsa',
      'servers.passwordLabel': 'SSH password',
      'servers.passwordPh': 'Enter server password',
      'servers.defaultDirLabel': 'Default remote base directory',
      'servers.save': 'Save server',
      'servers.noneConfigured': 'No servers configured yet.',
      'servers.needNameHost': 'Please fill in the name and host address',

      'settings.title': '⚙️ Agent LLM Configuration',
      'settings.desc': 'Configure an OpenAI-compatible LLM endpoint (DeepSeek, Claude, OpenAI, Qwen, local Ollama, etc.) to drive the built-in remote Coding Agent for autonomous code analysis and multi-step task execution.',
      'settings.modelLabel': 'Model name',
      'settings.save': 'Save config',
      'settings.saved': 'LLM configuration saved!',

      'broadcast.title': '📢 Broadcast to Tasks',
      'broadcast.desc': 'This command will be sent to <strong>all running</strong> task sessions at once:',
      'broadcast.ph': 'e.g. nvidia-smi or git pull',
      'broadcast.send': 'Send broadcast',
      'broadcast.done': 'Broadcast sent to {n} active task(s)!',

      'preview.title': 'File preview',
      'preview.readFailed': 'Read failed: ',

      'tasks.empty': 'No running tasks',
      'task.localProcess': 'Local command-line process',
      'task.localPrefix': 'Local process: ',
      'newTask.defaultName': 'New Task',
      'preview.emptyFile': '(empty file)',
      'terminal.wsError': '[WebSocket error] Cannot connect to terminal service.',
      'terminal.reconnecting': '[Terminal connection closed, reconnecting...]',

      'confirm.closeTask': 'Close this task workspace? The related terminal and session will be released.',
      'confirm.deleteServer': 'Delete this server configuration?',

      'common.cancel': 'Cancel',
      'common.close': 'Close',
      'common.edit': 'Edit',
      'common.delete': 'Delete',
    },

    zh: {
      'mem.title': '应用常驻内存',
      'sidebar.workspace': '任务工作区',
      'sidebar.newTask': '+ 新建任务',
      'sidebar.servers': '🖥️ 服务器管理',
      'sidebar.agentConfig': '⚙️ Agent 模型配置',
      'sidebar.broadcast': '📢 全局多任务广播',
      'sidebar.language': '🌐 English',

      'toolbar.modeAgent': '🤖 Agent 对话',
      'toolbar.modeTerminal': '🖥️ 实时终端',
      'toolbar.modeSplit': '🔲 左右分屏',
      'toolbar.files': '📁 远程文件',
      'toolbar.hardware': '⚡ 硬件状态',
      'toolbar.stopAgent': '⏹️ 停止 Agent',
      'toolbar.closeTask': '✕ 关闭任务',

      'empty.title': '暂无运行中的任务工作区',
      'empty.desc': '点击左上角「+ 新建任务」连接远程服务器，即可在当前窗口中同时并发管理多个项目任务，接入本地 Coding Agent 进行自动化推理、代码审查与执行。',
      'empty.createFirst': '+ 立即创建第一个任务',

      'agent.ready': '🤖 Agent 已就绪。请在下方输入需求（如排查当前代码报错、检查 GPU 显存或执行开发任务）。',
      'agent.chipFiles': '📁 查看目录代码',
      'agent.chipFiles.prompt': '检查当前远程工作目录的文件结构和代码',
      'agent.chipGpu': '⚡ 检查 GPU/硬件负载',
      'agent.chipGpu.prompt': '查看当前服务器显卡 GPU 显存与 CPU 内存占用',
      'agent.chipGit': '🌿 检查 Git 状态',
      'agent.chipGit.prompt': '执行 git status 查看最新代码分支与变动',
      'agent.inputPlaceholder': '向该远程任务的 Coding Agent 下发指令... (按 Enter 发送，Shift+Enter 换行)',
      'agent.send': '发送指令',
      'agent.thought': '🤔 Agent 思考决策 (Step {step})',
      'agent.toolCalling': '⚡ 正在调用工具:',
      'agent.running': '执行中...',
      'agent.waiting': '等待远程返回输出...',
      'agent.done': '完成',
      'agent.noOutput': '(无输出)',
      'agent.error': '错误: ',

      'terminal.clear': '清屏',

      'files.title': '📁 远程文件列表',
      'files.refresh': '刷新',
      'files.up': '📁 .. (返回上一层)',
      'files.readError': '无法读取目录: ',
      'files.failed': '失败',

      'newTask.title': '新建任务工作区',
      'newTask.nameLabel': '任务名称 (识别标识)',
      'newTask.namePh': '输入任务名称',
      'newTask.modeLabel': '任务运行模式',
      'newTask.modeRemote': '🌐 远程 SSH & Agent 任务 (直连服务器)',
      'newTask.modeLocal': '💻 本地 Agent 终端 (Claude Code / agy / PowerShell)',
      'newTask.serverLabel': '目标远程服务器',
      'newTask.manageServers': '+ 管理服务器',
      'newTask.dirLabel': '远程工作目录 (自动 cd 进入)',
      'newTask.dirPh': '例如: /home/user/workspace/project',
      'newTask.startupLabel': '初始化启动指令 (可选)',
      'newTask.startupPh': '例如: conda activate py310',
      'newTask.localCmdLabel': '本地 Agent 命令行',
      'newTask.localCmdPh': 'claude 或 agy 或 powershell',
      'newTask.localCwdLabel': '本地工作目录 (可选)',
      'newTask.localCwdPh': '留空为默认工程目录',
      'newTask.submit': '创建并连接',
      'newTask.noServer': '请先选择或添加一个目标远程服务器！',
      'newTask.createFailed': '创建失败: ',

      'servers.title': '远程服务器管理',
      'servers.configured': '已配置的远程服务器',
      'servers.add': '+ 添加服务器',
      'servers.formTitleAdd': '添加新服务器',
      'servers.formTitleEdit': '编辑服务器',
      'servers.nameLabel': '服务器名称 / 备注',
      'servers.namePh': '例如: 远程训练服务器 A',
      'servers.hostLabel': '主机 IP / 域名',
      'servers.portLabel': '端口',
      'servers.userLabel': '登录用户名',
      'servers.authLabel': '认证方式',
      'servers.authKey': 'SSH 私钥认证',
      'servers.authPassword': '密码认证',
      'servers.authKeyShort': 'SSH私钥',
      'servers.authPasswordShort': '密码认证',
      'servers.keyPathLabel': 'SSH 私钥路径 (留空则尝试默认 ~/.ssh/id_rsa)',
      'servers.keyPathPh': 'C:\\Users\\用户名\\.ssh\\id_rsa',
      'servers.passwordLabel': 'SSH 登录密码',
      'servers.passwordPh': '输入服务器密码',
      'servers.defaultDirLabel': '默认远程基准工作目录',
      'servers.save': '保存服务器',
      'servers.noneConfigured': '尚未配置任何服务器。',
      'servers.needNameHost': '请填写名称与主机地址',

      'settings.title': '⚙️ Agent 大模型配置',
      'settings.desc': '配置 OpenAI 兼容格式的大模型接口（支持 DeepSeek、Claude、OpenAI、Qwen、本地 Ollama 等），用于驱动内置远程 Coding Agent 进行自主代码分析与多步任务执行。',
      'settings.modelLabel': '模型名称 (Model)',
      'settings.save': '保存配置',
      'settings.saved': '大模型配置已保存！',

      'broadcast.title': '📢 全局任务广播',
      'broadcast.desc': '此命令将同时发送给当前<strong>所有运行中</strong>的任务会话：',
      'broadcast.ph': '例如: nvidia-smi 或 git pull',
      'broadcast.send': '发送广播',
      'broadcast.done': '已向 {n} 个活跃任务广播指令！',

      'preview.title': '文件预览',
      'preview.readFailed': '读取失败: ',

      'tasks.empty': '暂无运行中的任务',
      'task.localProcess': '本地命令行进程',
      'task.localPrefix': '本地进程: ',
      'newTask.defaultName': '新任务',
      'preview.emptyFile': '(空文件)',
      'terminal.wsError': '[WebSocket 错误] 无法连接到终端服务。',
      'terminal.reconnecting': '[终端连接已关闭，正在重连...]',

      'confirm.closeTask': '确定关闭此任务工作区吗？相关的终端与会话将一并释放。',
      'confirm.deleteServer': '确定删除该服务器配置？',

      'common.cancel': '取消',
      'common.close': '关闭',
      'common.edit': '编辑',
      'common.delete': '删除',
    }
  };

  const DEFAULT_LANG = 'en';
  let currentLang = DEFAULT_LANG;
  try {
    currentLang = localStorage.getItem('sh_lang') || DEFAULT_LANG;
  } catch (e) {
    currentLang = DEFAULT_LANG;
  }
  if (!DICT[currentLang]) currentLang = DEFAULT_LANG;

  function t(key, vars) {
    const table = DICT[currentLang] || DICT[DEFAULT_LANG];
    let str = table[key];
    if (str === undefined) {
      // Fall back to the other language, then to the key itself.
      const other = currentLang === 'en' ? 'zh' : 'en';
      str = (DICT[other] && DICT[other][key]) !== undefined ? DICT[other][key] : key;
    }
    if (vars && typeof str === 'string') {
      str = str.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined ? vars[k] : m));
    }
    return str;
  }

  function applyI18n(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    scope.querySelectorAll('[data-i18n-html]').forEach(el => {
      el.innerHTML = t(el.getAttribute('data-i18n-html'));
    });
    scope.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      el.setAttribute('placeholder', t(el.getAttribute('data-i18n-placeholder')));
    });
    scope.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
    });
    document.documentElement.lang = currentLang === 'zh' ? 'zh-CN' : 'en';
  }

  function setLang(lang, opts) {
    opts = opts || {};
    if (!DICT[lang]) lang = DEFAULT_LANG;
    currentLang = lang;
    try {
      localStorage.setItem('sh_lang', lang);
      localStorage.setItem('sh_lang_user_set', '1');
    } catch (e) {}
    applyI18n();
    // Re-render dynamic UI that depends on language
    if (window.app && typeof window.app.onLanguageChanged === 'function') {
      try { window.app.onLanguageChanged(); } catch (e) {}
    }
    if (opts.persistBackend !== false && window.app && typeof window.app.persistLanguage === 'function') {
      try { window.app.persistLanguage(lang); } catch (e) {}
    }
  }

  function toggle() {
    setLang(currentLang === 'en' ? 'zh' : 'en');
  }

  // Apply once the DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => applyI18n());
  } else {
    applyI18n();
  }

  window.i18n = {
    get lang() { return currentLang; },
    t, applyI18n, setLang, toggle,
    hasUserChoice() {
      try { return localStorage.getItem('sh_lang_user_set') === '1'; } catch (e) { return false; }
    }
  };
  window.t = t;
})();
