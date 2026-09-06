/**
 * Terminal Manager
 * Handles xterm.js instances, WebSocket streaming, and auto-resizing.
 */
class TerminalManager {
  constructor() {
    this.instances = {}; // sessionId -> { term, fitAddon, ws, container }
    window.addEventListener('resize', () => this.fitAll());
  }

  create(sessionId, containerEl) {
    if (this.instances[sessionId]) {
      return this.instances[sessionId];
    }

    const term = new Terminal({
      cursorBlink: true,
      cursorStyle: 'block',
      fontSize: 13,
      lineHeight: 1.2,
      fontFamily: "'Consolas', 'Fira Code', 'JetBrains Mono', monospace",
      theme: {
        background: '#0a0d14',
        foreground: '#e2e8f0',
        cursor: '#6366f1',
        selectionBackground: 'rgba(99, 102, 241, 0.3)',
        black: '#000000',
        red: '#ef4444',
        green: '#10b981',
        yellow: '#f59e0b',
        blue: '#3b82f6',
        magenta: '#a855f7',
        cyan: '#06b6d4',
        white: '#ffffff',
        brightBlack: '#64748b',
        brightRed: '#f87171',
        brightGreen: '#34d399',
        brightYellow: '#fbbf24',
        brightBlue: '#60a5fa',
        brightMagenta: '#c084fc',
        brightCyan: '#22d3ee',
        brightWhite: '#f8fafc'
      },
      convertEol: true
    });

    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerEl);

    // Initial fit
    setTimeout(() => {
      try {
        fitAddon.fit();
      } catch (e) {}
    }, 100);

    // Setup WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal/${sessionId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      // Send initial dimensions
      setTimeout(() => {
        try {
          fitAddon.fit();
          ws.send(JSON.stringify({
            type: 'resize',
            cols: term.cols,
            rows: term.rows
          }));
        } catch (e) {}
      }, 150);
    };

    ws.onmessage = (event) => {
      term.write(event.data);
    };

    ws.onerror = (err) => {
      term.write('\r\n\x1b[31m[WebSocket 错误] 无法连接到终端服务。\x1b[0m\r\n');
    };

    ws.onclose = () => {
      term.write('\r\n\x1b[33m[终端连接已关闭]\x1b[0m\r\n');
    };

    // User keystrokes
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    });

    // Terminal resize event
    term.onResize(({ cols, rows }) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols, rows }));
      }
    });

    const instance = { term, fitAddon, ws, container: containerEl };
    this.instances[sessionId] = instance;
    return instance;
  }

  fit(sessionId) {
    const inst = this.instances[sessionId];
    if (inst && inst.fitAddon && inst.container.offsetParent !== null) {
      try {
        inst.fitAddon.fit();
        if (inst.ws.readyState === WebSocket.OPEN) {
          inst.ws.send(JSON.stringify({
            type: 'resize',
            cols: inst.term.cols,
            rows: inst.term.rows
          }));
        }
      } catch (e) {}
    }
  }

  fitAll() {
    for (const id in this.instances) {
      this.fit(id);
    }
  }

  focus(sessionId) {
    const inst = this.instances[sessionId];
    if (inst && inst.term) {
      inst.term.focus();
    }
  }

  sendData(sessionId, data) {
    const inst = this.instances[sessionId];
    if (inst && inst.ws && inst.ws.readyState === WebSocket.OPEN) {
      inst.ws.send(data);
    }
  }

  dispose(sessionId) {
    const inst = this.instances[sessionId];
    if (inst) {
      try {
        inst.ws.close();
      } catch (e) {}
      try {
        inst.term.dispose();
      } catch (e) {}
      delete this.instances[sessionId];
    }
  }
}

window.terminalManager = new TerminalManager();
