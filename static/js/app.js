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
    this.agentRetryDelay = {}; // sessionId -> current backoff (ms)
    this.currentRemotePath = '';
    this._pollTimer = null;

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
      // Adopt the backend-configured language only if the user hasn't already
      // made an explicit choice in this browser.
      if (window.i18n && this.settings.language && !window.i18n.hasUserChoice()) {
        window.i18n.setLang(this.settings.language, { persistBackend: false });
      }
      this.renderServerDropdown();
    }
  }

  /* ---------------- Language ---------------- */

  // Called by i18n after a language change so dynamic (JS-rendered) UI updates.
  onLanguageChanged() {
    this.renderServerDropdown();
    this.renderSidebarTasks();
    if (document.getElementById('modal-servers').classList.contains('show')) {
      this.renderServersList();
    }
  }

  // Best-effort mirror of the language choice into the backend setting.
  async persistLanguage(lang) {
    try {
      await this.fetchJson('/api/config', {
        method: 'POST',
        body: JSON.stringify({ settings: { language: lang } })
      });
    } catch (e) {}
  }

  // Prompt chip click: fill the input with the localized prompt text.
  fillPromptI18n(el) {
    const key = el && el.getAttribute ? el.getAttribute('data-prompt') : null;
    if (key) this.fillPrompt(window.t(key));
  }

  renderServerDropdown() {
    const select = document.getElementById('task-server-id');
    if (!select) return;
    select.innerHTML = '';
    if (this.servers.length === 0) {
      const emptyOpt = document.createElement('option');
      emptyOpt.value = '';
      emptyOpt.textContent = window.t('servers.noneConfigured');
      select.appendChild(emptyOpt);
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
      alert(window.t('settings.saved'));
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
      const empty = document.createElement('div');
      empty.style.cssText = 'color: var(--text-muted); font-size: 12px; padding: 8px 4px;';
      empty.textContent = window.t('tasks.empty');
      list.appendChild(empty);
      return;
    }

    this.sessions.forEach(s => {
      const item = document.createElement('div');
      item.className = `task-item ${s.session_id === this.activeSessionId ? 'active' : ''}`;
      item.onclick = () => this.selectTask(s.session_id);

      const isSSH = s.session_type === 'remote_ssh';
      const desc = isSSH ? `${s.server_name} | ${s.remote_dir || '/'}` : window.t('task.localProcess');
      const statusClass = String(s.status || 'running').replace(/[^a-z0-9_-]/gi, '');

      item.innerHTML = `
        <div class="task-item-top">
          <div class="task-item-title">
            <div class="status-dot status-${statusClass}"></div>
            <span>${this.escapeHtml(s.name)}</span>
          </div>
          <span style="font-size: 10px; color: var(--text-muted);">${isSSH ? 'SSH' : 'LOCAL'}</span>
        </div>
        <div class="task-item-desc" title="${this.escapeHtml(desc)}">${this.escapeHtml(desc)}</div>
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
      : `${window.t('task.localPrefix')}${session.command || 'PowerShell'}`;
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
    if (!confirm(window.t('confirm.closeTask'))) return;

    const id = this.activeSessionId;
    await this.fetchJson(`/api/sessions/${id}/close`, { method: 'POST' });

    window.terminalManager.dispose(id);
    const pane = document.getElementById(`pane-${id}`);
    if (pane) pane.remove();

    if (this.agentSockets[id]) {
      this.agentSockets[id]._intentionalClose = true;
      this.agentSockets[id].close();
      delete this.agentSockets[id];
    }
    delete this.agentRetryDelay[id];

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
    const name = document.getElementById('task-name').value.trim() || window.t('newTask.defaultName');
    const mode = document.getElementById('task-mode').value;

    let payload = { session_type: mode, name: name };

    if (mode === 'remote_ssh') {
      const serverId = document.getElementById('task-server-id').value;
      if (!serverId) {
        alert(window.t('newTask.noServer'));
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
      alert(window.t('newTask.createFailed') + ((res && res.error) || window.t('files.failed')));
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

    ws.onopen = () => {
      this.agentRetryDelay[sessionId] = 1000; // reset backoff on success
    };

    ws.onclose = () => {
      if (this.agentSockets[sessionId] === ws) {
        delete this.agentSockets[sessionId];
      }
      if (ws._intentionalClose) return;
      // Auto-reconnect with exponential backoff while the session still exists.
      const delay = this.agentRetryDelay[sessionId] || 1000;
      this.agentRetryDelay[sessionId] = Math.min(delay * 2, 30000);
      setTimeout(() => {
        if (!ws._intentionalClose && this.sessions.some(s => s.session_id === sessionId)) {
          this.connectAgentSocket(sessionId);
        }
      }, delay);
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
      this.appendStatusNotice(window.t('agent.error') + data.message, 'error');
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
    const label = this.escapeHtml(window.t('agent.thought', { step: step || 1 }));
    card.innerHTML = `<div style="font-weight: 600; font-size: 11px; color: var(--warning); margin-bottom: 4px;">${label}</div><div>${this.escapeHtml(text)}</div>`;
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
        <span>${this.escapeHtml(window.t('agent.toolCalling'))} <strong>${this.escapeHtml(toolName)}</strong></span>
        <span style="font-size: 11px; color: var(--warning);">${this.escapeHtml(window.t('agent.running'))}</span>
      </div>
      <div class="agent-tool-body">
        <div style="color: var(--info);">${this.escapeHtml(argPreview)}</div>
        <div class="tool-out" style="margin-top: 6px; color: var(--text-muted); font-size: 11px;">${this.escapeHtml(window.t('agent.waiting'))}</div>
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
        headerStatus.textContent = window.t('agent.done');
        headerStatus.style.color = 'var(--success)';
      }
      const outDiv = card.querySelector('.tool-out');
      if (outDiv) {
        outDiv.textContent = result || window.t('agent.noOutput');
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
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
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
    this.fillPrompt(window.t('agent.chipGpu.prompt'));
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
        upItem.textContent = window.t('files.up');
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
            <span>${this.escapeHtml(f.name)}</span>
          </div>
          <span style="font-size: 11px; color: var(--text-muted);">${this.escapeHtml(sizeStr)}</span>
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
      const errMsg = this.escapeHtml((res && res.error) || window.t('files.failed'));
      list.innerHTML = `<div style="color: var(--danger); padding: 12px; font-size: 12px;">${this.escapeHtml(window.t('files.readError'))}${errMsg}</div>`;
    }
  }

  async previewFile(path, name) {
    const res = await this.fetchJson('/api/sftp/read', {
      method: 'POST',
      body: JSON.stringify({ session_id: this.activeSessionId, path })
    });
    if (res && res.success) {
      document.getElementById('preview-filename').textContent = `📄 ${name} (${path})`;
      document.getElementById('preview-content').textContent = res.content || window.t('preview.emptyFile');
      this.openModal('modal-preview');
    } else {
      alert(window.t('preview.readFailed') + ((res && res.error) || window.t('files.failed')));
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
      const none = document.createElement('div');
      none.style.cssText = 'color: var(--text-muted); font-size: 12px;';
      none.textContent = window.t('servers.noneConfigured');
      container.appendChild(none);
      return;
    }
    this.servers.forEach(s => {
      const item = document.createElement('div');
      item.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: 10px; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 6px; margin-bottom: 8px; font-size: 13px;';
      const authLabel = s.auth_type === 'key' ? window.t('servers.authKeyShort') : window.t('servers.authPasswordShort');
      item.innerHTML = `
        <div>
          <strong style="color: #fff;">${this.escapeHtml(s.name)}</strong>
          <div style="font-size: 12px; color: var(--text-muted);">${this.escapeHtml(s.username)}@${this.escapeHtml(s.host)}:${this.escapeHtml(s.port)} (${authLabel})</div>
        </div>
        <div style="display: flex; gap: 6px;"></div>
      `;
      // Build buttons with listeners (no inline onclick string interpolation,
      // which would allow JS injection if an id ever contained a quote).
      const btnWrap = item.lastElementChild;
      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-secondary btn-sm';
      editBtn.textContent = window.t('common.edit');
      editBtn.onclick = () => this.editServer(s.id);
      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-secondary btn-sm';
      delBtn.style.color = 'var(--danger)';
      delBtn.textContent = window.t('common.delete');
      delBtn.onclick = () => this.deleteServer(s.id);
      btnWrap.appendChild(editBtn);
      btnWrap.appendChild(delBtn);
      container.appendChild(item);
    });
  }

  showAddServerForm() {
    document.getElementById('server-form-title').textContent = window.t('servers.formTitleAdd');
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
    document.getElementById('server-form-title').textContent = window.t('servers.formTitleEdit');
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
      alert(window.t('servers.needNameHost'));
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
    if (!confirm(window.t('confirm.deleteServer'))) return;
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
      alert(window.t('broadcast.done', { n: res.broadcasted_to }));
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
      const el = document.getElementById('stat-mem');
      if (data && data.success && el) {
        el.textContent = `${data.memory_mb} MB`;
      }
    };
    poll();
    if (this._pollTimer) clearInterval(this._pollTimer);
    this._pollTimer = setInterval(poll, 3000);
  }

  stopStatusPolling() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }
}

window.app = new App();
