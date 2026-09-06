/**
 * ServerHelper - Frontend State & Agent Loop Controller
 */

class App {
  constructor() {
    this.sessions = [];
    this.activeSessionId = null;
    this.servers = [];
    this.settings = {};
    this.viewMode = 'terminal'; // 'agent', 'terminal', 'split'
    this.agentSockets = {};    // sessionId -> WebSocket
    this.currentRemotePath = '';

    this.init();
  }

  async init() {
    await this.loadConfig();
    await this.loadSessions();
    this.startStatusPolling();
    this.bindGlobalEvents();
  }

  bindGlobalEvents() {
    // Input enter to send
    const input = document.getElementById('agent-input');
    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendAgentPrompt();
        }
      });
    }
  }

  /* ---------------- API Helpers ---------------- */

  async fetchJson(url, options = {}) {
    try {
      const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options
      });
      return await res.json();
    } catch (err) {
      console.error('API Error:', err);
      return { success: false, error: err.message };
    }
  }

  /* ---------------- Config & Settings ---------------- */

  async loadConfig() {
    const data = await this.fetchJson('/api/config');
    if (data) {
      this.servers = data.servers || [];
      this.settings = data.settings || {};
      this.renderServerDropdown();
    }
  }

  renderServerDropdown() {
    const select = document.getElementById('task-server-id');
    if (!select) return;
    select.innerHTML = '';
    if (this.servers.length === 0) {
      select.innerHTML = '<option value="">(尚未添加服务器，请先点击管理服务器)</option>';
      return;
    }
    this.servers.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = `${s.name} (${s.username}@${s.host}:${s.port})`;
      select.appendChild(opt);
    });
  }

  openSettingsModal() {
    document.getElementById('cfg-api-base').value = this.settings.api_base || 'https://api.deepseek.com/v1';
    document.getElementById('cfg-api-key').value = this.settings.api_key || '';
    document.getElementById('cfg-model').value = this.settings.model || 'deepseek-chat';
    this.openModal('modal-settings');
  }

  async saveSettings() {
    const api_base = document.getElementById('cfg-api-base').value.trim();
    const api_key = document.getElementById('cfg-api-key').value.trim();
    const model = document.getElementById('cfg-model').value.trim();

    const res = await this.fetchJson('/api/config', {
      method: 'POST',
      body: JSON.stringify({
        settings: { api_base, api_key, model }
      })
    });

    if (res && res.success) {
      this.settings = res.config.settings;
      this.closeModal('modal-settings');
      alert('大模型配置已保存！');
    }
  }

  /* ---------------- Task Sessions ---------------- */

  async loadSessions() {
    const res = await this.fetchJson('/api/sessions');
    if (res && res.success) {
      this.sessions = res.sessions || [];
      this.renderSidebarTasks();
      if (this.sessions.length > 0 && !this.activeSessionId) {
        this.selectTask(this.sessions[0].session_id);
      } else if (this.sessions.length === 0) {
        this.activeSessionId = null;
        this.updateViewVisibility();
      }
    }
  }

  renderSidebarTasks() {
    const list = document.getElementById('task-list');
    list.innerHTML = '';

    if (this.sessions.length === 0) {
      list.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 8px 4px;">暂无运行中的任务</div>';
      return;
    }

    this.sessions.forEach(s => {
      const item = document.createElement('div');
      item.className = `task-item ${s.session_id === this.activeSessionId ? 'active' : ''}`;
      item.onclick = () => this.selectTask(s.session_id);

      const isSSH = s.session_type === 'remote_ssh';
      const desc = isSSH ? `${s.server_name} | ${s.remote_dir || '/'}` : '本地命令行进程';

      item.innerHTML = `
        <div class="task-item-top">
          <div class="task-item-title">
            <div class="status-dot status-${s.status || 'running'}"></div>
            <span>${s.name}</span>
          </div>
          <span style="font-size: 10px; color: var(--text-muted);">${isSSH ? 'SSH' : 'LOCAL'}</span>
        </div>
        <div class="task-item-desc" title="${desc}">${desc}</div>
      `;
      list.appendChild(item);
    });
  }

  selectTask(sessionId) {
    this.activeSessionId = sessionId;
    const session = this.sessions.find(s => s.session_id === sessionId);
    this.renderSidebarTasks();

    if (!session) {
      this.updateViewVisibility();
      return;
    }

    // Top Toolbar meta
    document.getElementById('top-toolbar').style.display = 'flex';
    document.getElementById('active-task-name').textContent = session.name;
    const pathText = session.session_type === 'remote_ssh'
      ? `${session.server_name} : ${session.remote_dir || '/'}`
      : `本地进程: ${session.command || 'PowerShell'}`;
    document.getElementById('active-task-path').textContent = pathText;

    // Show/hide file drawer button
    const btnFiles = document.getElementById('btn-open-files');
    if (btnFiles) {
      btnFiles.style.display = session.session_type === 'remote_ssh' ? 'inline-flex' : 'none';
    }

    // Ensure Terminal Pane exists & activate
    this.activateTerminalPane(sessionId);

    // Connect Agent WebSocket
    this.connectAgentSocket(sessionId);

    this.updateViewVisibility();
  }

  activateTerminalPane(sessionId) {
    const stage = document.getElementById('terminals-stage');
    let pane = document.getElementById(`pane-${sessionId}`);
    if (!pane) {
      pane = document.createElement('div');
      pane.id = `pane-${sessionId}`;
      pane.className = 'term-container';
      stage.appendChild(pane);
      window.terminalManager.create(sessionId, pane);
    }

    document.querySelectorAll('.term-container').forEach(el => {
      el.classList.toggle('active', el.id === `pane-${sessionId}`);
    });

    setTimeout(() => {
      window.terminalManager.fit(sessionId);
      if (this.viewMode === 'terminal' || this.viewMode === 'split') {
        window.terminalManager.focus(sessionId);
      }
    }, 100);
  }

  updateViewVisibility() {
    const placeholder = document.getElementById('empty-placeholder');
    const toolbar = document.getElementById('top-toolbar');
    const canvas = document.getElementById('workspace-canvas');

    if (!this.activeSessionId || this.sessions.length === 0) {
      placeholder.style.display = 'flex';
      toolbar.style.display = 'none';
      canvas.className = 'workspace-canvas';
      return;
    }

    placeholder.style.display = 'none';
    toolbar.style.display = 'flex';
    canvas.className = `workspace-canvas mode-${this.viewMode}`;
    setTimeout(() => window.terminalManager.fitAll(), 80);
  }

  setViewMode(mode) {
    this.viewMode = mode;
    document.getElementById('btn-mode-agent').classList.toggle('active', mode === 'agent');
    document.getElementById('btn-mode-terminal').classList.toggle('active', mode === 'terminal');
    document.getElementById('btn-mode-split').classList.toggle('active', mode === 'split');
    this.updateViewVisibility();
  }

  async closeCurrentTask() {
    if (!this.activeSessionId) return;
    if (!confirm('确定关闭此任务工作区吗？相关的终端与会话将一并释放。')) return;

    const id = this.activeSessionId;
    await this.fetchJson(`/api/sessions/${id}/close`, { method: 'POST' });

    window.terminalManager.dispose(id);
    const pane = document.getElementById(`pane-${id}`);
    if (pane) pane.remove();

    if (this.agentSockets[id]) {
      this.agentSockets[id].close();
      delete this.agentSockets[id];
    }

    this.sessions = this.sessions.filter(s => s.session_id !== id);
    this.activeSessionId = this.sessions.length > 0 ? this.sessions[0].session_id : null;

    this.renderSidebarTasks();
    if (this.activeSessionId) {
      this.selectTask(this.activeSessionId);
    } else {
      this.updateViewVisibility();
    }
  }

  /* ---------------- Create Task ---------------- */

  openNewTaskModal() {
    document.getElementById('task-name').value = '';
    document.getElementById('task-remote-dir').value = '';
    document.getElementById('task-startup-cmd').value = '';
    this.renderServerDropdown();
    this.openModal('modal-new-task');
  }

  toggleTaskMode() {
    const mode = document.getElementById('task-mode').value;
    document.getElementById('group-remote-fields').style.display = mode === 'remote_ssh' ? 'block' : 'none';
    document.getElementById('group-local-fields').style.display = mode === 'local_pty' ? 'block' : 'none';
  }

  async submitCreateTask() {
    const name = document.getElementById('task-name').value.trim() || '新任务';
    const mode = document.getElementById('task-mode').value;

    let payload = { session_type: mode, name: name };

    if (mode === 'remote_ssh') {
      const serverId = document.getElementById('task-server-id').value;
      if (!serverId) {
        alert('请先选择或添加一个目标远程服务器！');
        return;
      }
      payload.server_id = serverId;
      payload.remote_dir = document.getElementById('task-remote-dir').value.trim();
      payload.startup_cmd = document.getElementById('task-startup-cmd').value.trim();
    } else {
      payload.local_cmd = document.getElementById('task-local-cmd').value.trim() || 'claude';
      payload.cwd = document.getElementById('task-local-cwd').value.trim();
    }

    this.closeModal('modal-new-task');

    const res = await this.fetchJson('/api/sessions', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    if (res && res.success) {
      const newSession = res.session;
      this.sessions.push(newSession);
      this.renderSidebarTasks();
      this.selectTask(newSession.session_id);
    } else {
      alert('创建失败: ' + (res.error || '无法连接服务器'));
    }
  }

  /* ---------------- Agent Engine WebSocket & Chat ---------------- */

  connectAgentSocket(sessionId) {
    if (this.agentSockets[sessionId]) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/agent/${sessionId}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        this.handleAgentEvent(sessionId, payload);
      } catch (e) {}
    };

    ws.onclose = () => {
      delete this.agentSockets[sessionId];
    };

    this.agentSockets[sessionId] = ws;
  }

  sendAgentPrompt() {
    const input = document.getElementById('agent-input');
    const prompt = input.value.trim();
    if (!prompt || !this.activeSessionId) return;

    const ws = this.agentSockets[this.activeSessionId];
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      this.connectAgentSocket(this.activeSessionId);
      setTimeout(() => this.sendAgentPrompt(), 200);
      return;
    }

    // Append user bubble to UI
    this.appendAgentMessage('user', prompt);
    input.value = '';

    // Switch to agent view if in terminal mode
    if (this.viewMode === 'terminal') {
      this.setViewMode('split');
    }

    ws.send(JSON.stringify({ type: 'prompt', prompt }));
  }

  fillPrompt(text) {
    const input = document.getElementById('agent-input');
    input.value = text;
    input.focus();
  }

  stopCurrentAgent() {
    if (!this.activeSessionId) return;
    const ws = this.agentSockets[this.activeSessionId];
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'stop' }));
    }
  }

  handleAgentEvent(sessionId, event) {
    if (sessionId !== this.activeSessionId) return;

    const type = event.event;
    const data = event.data;

    if (type === 'message' && data.role === 'user') {
      // User message already rendered or sync
    } else if (type === 'thought') {
      this.appendThoughtCard(data.content, data.step);
    } else if (type === 'tool_call') {
      this.appendToolCallCard(data.tool_name, data.arguments, data.step);
    } else if (type === 'tool_result') {
      this.updateToolResult(data.tool_name, data.result, data.step);
    } else if (type === 'status_change') {
      this.appendStatusNotice(data.message, data.status);
    } else if (type === 'error') {
      this.appendStatusNotice('错误: ' + data.message, 'error');
    }
  }

  appendAgentMessage(role, text) {
    const container = document.getElementById('agent-messages');
    const div = document.createElement('div');
    div.className = role === 'user' ? 'agent-msg-user' : 'agent-msg-bot';
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  appendThoughtCard(text, step) {
    const container = document.getElementById('agent-messages');
    const card = document.createElement('div');
    card.className = 'agent-thought-card';
    card.innerHTML = `<div style="font-weight: 600; font-size: 11px; color: var(--warning); margin-bottom: 4px;">🤔 Agent 思考决策 (Step ${step || 1})</div><div>${this.escapeHtml(text)}</div>`;
    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
  }

  appendToolCallCard(toolName, args, step) {
    const container = document.getElementById('agent-messages');
    const card = document.createElement('div');
    card.className = 'agent-tool-card';
    card.id = `tool-step-${step}-${toolName}`;

    let argPreview = '';
    if (toolName === 'run_command') {
      argPreview = `$ ${args.command || ''}`;
    } else if (toolName === 'read_file' || toolName === 'write_file' || toolName === 'edit_file') {
      argPreview = `${args.path || ''}`;
    } else {
      argPreview = JSON.stringify(args);
    }

    card.innerHTML = `
      <div class="agent-tool-header">
        <span>⚡ 正在调用工具: <strong>${toolName}</strong></span>
        <span style="font-size: 11px; color: var(--warning);">执行中...</span>
      </div>
      <div class="agent-tool-body">
        <div style="color: var(--info);">${this.escapeHtml(argPreview)}</div>
        <div class="tool-out" style="margin-top: 6px; color: var(--text-muted); font-size: 11px;">等待远程返回输出...</div>
      </div>
    `;
    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
  }

  updateToolResult(toolName, result, step) {
    const card = document.getElementById(`tool-step-${step}-${toolName}`);
    if (card) {
      const headerStatus = card.querySelector('.agent-tool-header span:last-child');
      if (headerStatus) {
        headerStatus.textContent = '完成';
        headerStatus.style.color = 'var(--success)';
      }
      const outDiv = card.querySelector('.tool-out');
      if (outDiv) {
        outDiv.textContent = result || '(无输出)';
        outDiv.style.color = '#cbd5e1';
      }
    }
  }

  appendStatusNotice(msg, status) {
    const container = document.getElementById('agent-messages');
    const notice = document.createElement('div');
    notice.style.cssText = 'font-size: 12px; color: var(--text-muted); text-align: center; margin: 4px 0;';
    notice.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    container.appendChild(notice);
    container.scrollTop = container.scrollHeight;
  }

  escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* ---------------- Terminal Controls ---------------- */

  sendTermCmd(cmd) {
    if (!this.activeSessionId) return;
    window.terminalManager.sendData(this.activeSessionId, cmd + '\r\n');
  }

  sendTermCtrlC() {
    if (!this.activeSessionId) return;
    window.terminalManager.sendData(this.activeSessionId, '\x03');
  }

  clearCurrentTerm() {
    if (!this.activeSessionId) return;
    window.terminalManager.sendData(this.activeSessionId, 'clear\r\n');
  }

  checkGPU() {
    this.fillPrompt('查看当前服务器显卡 GPU 显存与 CPU 内存占用');
    this.sendAgentPrompt();
  }

  /* ---------------- SFTP File Drawer ---------------- */

  async openFileDrawer() {
    const session = this.sessions.find(s => s.session_id === this.activeSessionId);
    if (!session || session.session_type !== 'remote_ssh') return;

    this.currentRemotePath = session.remote_dir || '.';
    document.getElementById('drawer-path').textContent = this.currentRemotePath;
    document.getElementById('file-drawer').classList.add('open');
    await this.refreshFiles();
  }

  closeFileDrawer() {
    document.getElementById('file-drawer').classList.remove('open');
  }

  async refreshFiles() {
    if (!this.activeSessionId) return;
    const res = await this.fetchJson('/api/sftp/list', {
      method: 'POST',
      body: JSON.stringify({
        session_id: this.activeSessionId,
        path: this.currentRemotePath
      })
    });

    const list = document.getElementById('file-list');
    list.innerHTML = '';

    if (res && res.success && Array.isArray(res.files)) {
      if (this.currentRemotePath !== '/' && this.currentRemotePath !== '') {
        const upItem = document.createElement('div');
        upItem.className = 'file-item';
        upItem.innerHTML = '<div>📁 .. (返回上一层)</div>';
        upItem.onclick = () => {
          const parts = this.currentRemotePath.replace(/\/$/, '').split('/');
          parts.pop();
          this.currentRemotePath = parts.join('/') || '/';
          document.getElementById('drawer-path').textContent = this.currentRemotePath;
          this.refreshFiles();
        };
        list.appendChild(upItem);
      }

      res.files.forEach(f => {
        if (f.error) return;
        const item = document.createElement('div');
        item.className = 'file-item';
        const icon = f.is_dir ? '📁' : '📄';
        const sizeStr = f.is_dir ? '' : this.formatBytes(f.size);

        item.innerHTML = `
          <div style="display: flex; align-items: center; gap: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            <span>${icon}</span>
            <span>${f.name}</span>
          </div>
          <span style="font-size: 11px; color: var(--text-muted);">${sizeStr}</span>
        `;

        if (f.is_dir) {
          item.onclick = () => {
            this.currentRemotePath = this.currentRemotePath.replace(/\/$/, '') + '/' + f.name;
            document.getElementById('drawer-path').textContent = this.currentRemotePath;
            this.refreshFiles();
          };
        } else {
          item.onclick = () => this.previewFile(this.currentRemotePath.replace(/\/$/, '') + '/' + f.name, f.name);
        }
        list.appendChild(item);
      });
    } else {
      list.innerHTML = `<div style="color: var(--danger); padding: 12px; font-size: 12px;">无法读取目录: ${res.error || '失败'}</div>`;
    }
  }

  async previewFile(path, name) {
    const res = await this.fetchJson('/api/sftp/read', {
      method: 'POST',
      body: JSON.stringify({ session_id: this.activeSessionId, path })
    });
    if (res && res.success) {
      document.getElementById('preview-filename').textContent = `📄 ${name} (${path})`;
      document.getElementById('preview-content').textContent = res.content || '(空文件)';
      this.openModal('modal-preview');
    } else {
      alert('读取失败: ' + (res.error || '未知错误'));
    }
  }

  formatBytes(b) {
    if (!b) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(b) / Math.log(k));
    return parseFloat((b / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  /* ---------------- Server Management ---------------- */

  openServerModal() {
    this.renderServersList();
    this.openModal('modal-servers');
  }

  renderServersList() {
    const container = document.getElementById('servers-list');
    container.innerHTML = '';
    if (this.servers.length === 0) {
      container.innerHTML = '<div style="color: var(--text-muted); font-size: 12px;">尚未配置任何服务器。</div>';
      return;
    }
    this.servers.forEach(s => {
      const item = document.createElement('div');
      item.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: 10px; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 6px; margin-bottom: 8px; font-size: 13px;';
      item.innerHTML = `
        <div>
          <strong style="color: #fff;">${s.name}</strong>
          <div style="font-size: 12px; color: var(--text-muted);">${s.username}@${s.host}:${s.port} (${s.auth_type === 'key' ? 'SSH私钥' : '密码认证'})</div>
        </div>
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-secondary btn-sm" onclick="app.editServer('${s.id}')">编辑</button>
          <button class="btn btn-secondary btn-sm" style="color: var(--danger);" onclick="app.deleteServer('${s.id}')">删除</button>
        </div>
      `;
      container.appendChild(item);
    });
  }

  showAddServerForm() {
    document.getElementById('server-form-title').textContent = '添加新服务器';
    document.getElementById('srv-id').value = '';
    document.getElementById('srv-name').value = '';
    document.getElementById('srv-host').value = '';
    document.getElementById('srv-port').value = '22';
    document.getElementById('srv-user').value = 'root';
    document.getElementById('srv-auth-type').value = 'key';
    document.getElementById('srv-key-path').value = '';
    document.getElementById('srv-password').value = '';
    document.getElementById('srv-default-dir').value = '';
    this.toggleAuthType();
    document.getElementById('server-form-card').style.display = 'block';
  }

  editServer(id) {
    const s = this.servers.find(x => x.id === id);
    if (!s) return;
    document.getElementById('server-form-title').textContent = '编辑服务器';
    document.getElementById('srv-id').value = s.id;
    document.getElementById('srv-name').value = s.name;
    document.getElementById('srv-host').value = s.host;
    document.getElementById('srv-port').value = s.port;
    document.getElementById('srv-user').value = s.username;
    document.getElementById('srv-auth-type').value = s.auth_type || 'key';
    document.getElementById('srv-key-path').value = s.key_path || '';
    document.getElementById('srv-password').value = s.password || '';
    document.getElementById('srv-default-dir').value = s.default_dir || '';
    this.toggleAuthType();
    document.getElementById('server-form-card').style.display = 'block';
  }

  hideServerForm() {
    document.getElementById('server-form-card').style.display = 'none';
  }

  toggleAuthType() {
    const type = document.getElementById('srv-auth-type').value;
    document.getElementById('srv-key-group').style.display = type === 'key' ? 'block' : 'none';
    document.getElementById('srv-pwd-group').style.display = type === 'password' ? 'block' : 'none';
  }

  async saveServer() {
    const id = document.getElementById('srv-id').value;
    const name = document.getElementById('srv-name').value.trim();
    const host = document.getElementById('srv-host').value.trim();
    if (!name || !host) {
      alert('请填写名称与主机地址');
      return;
    }

    const payload = {
      id: id || undefined,
      name,
      host,
      port: parseInt(document.getElementById('srv-port').value) || 22,
      username: document.getElementById('srv-user').value.trim() || 'root',
      auth_type: document.getElementById('srv-auth-type').value,
      key_path: document.getElementById('srv-key-path').value.trim(),
      password: document.getElementById('srv-password').value,
      default_dir: document.getElementById('srv-default-dir').value.trim()
    };

    const res = await this.fetchJson('/api/config/server', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    if (res && res.success) {
      await this.loadConfig();
      this.renderServersList();
      this.hideServerForm();
    }
  }

  async deleteServer(id) {
    if (!confirm('确定删除该服务器配置？')) return;
    const res = await this.fetchJson('/api/config/server', {
      method: 'DELETE',
      body: JSON.stringify({ id })
    });
    if (res && res.success) {
      await this.loadConfig();
      this.renderServersList();
    }
  }

  /* ---------------- Broadcast ---------------- */

  openBroadcastModal() {
    document.getElementById('broadcast-cmd').value = '';
    this.openModal('modal-broadcast');
  }

  async submitBroadcast() {
    const cmd = document.getElementById('broadcast-cmd').value.trim();
    if (!cmd) return;
    this.closeModal('modal-broadcast');

    const res = await this.fetchJson('/api/broadcast', {
      method: 'POST',
      body: JSON.stringify({ command: cmd })
    });

    if (res && res.success) {
      alert(`已向 ${res.broadcasted_to} 个活跃任务广播指令！`);
    }
  }

  /* ---------------- Modals ---------------- */

  openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('show');
  }

  closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('show');
  }

  /* ---------------- Polling ---------------- */

  startStatusPolling() {
    const poll = async () => {
      const data = await this.fetchJson('/api/status');
      if (data && data.success) {
        document.getElementById('stat-mem').textContent = `${data.memory_mb} MB`;
      }
    };
    poll();
    setInterval(poll, 3000);
  }
}

window.app = new App();
