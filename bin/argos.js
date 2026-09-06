#!/usr/bin/env node

/**
 * Argos (Ἄργος) CLI Node Launcher
 * Supports `npm install -g argos-agent` and `npx argos-agent`
 */

const { spawn, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const homeDir = os.homedir();
const argosHome = path.join(homeDir, '.argos');
const isWin = process.platform === 'win32';

// 1. Check if local workspace .venv has argos
const workspaceVenv = path.join(__dirname, '..', '.venv', isWin ? 'Scripts' : 'bin', isWin ? 'argos.exe' : 'argos');

// 2. Check if user global ~/.argos/venv has argos
const userVenv = path.join(argosHome, 'venv', isWin ? 'Scripts' : 'bin', isWin ? 'argos.exe' : 'argos');

function runExecutable(binPath, args) {
  const child = spawn(binPath, args, {
    stdio: 'inherit',
    shell: isWin
  });

  child.on('exit', (code) => {
    process.exit(code || 0);
  });

  child.on('error', (err) => {
    console.error(`[Argos] Failed to start binary: ${err.message}`);
    process.exit(1);
  });
}

function findPython() {
  const candidates = isWin ? ['python', 'py', 'python3'] : ['python3', 'python'];
  for (const cmd of candidates) {
    try {
      const res = spawnSync(cmd, ['--version'], { encoding: 'utf-8', stdio: 'pipe' });
      if (res.status === 0) return cmd;
    } catch (_) {}
  }
  return null;
}

function main() {
  const args = process.argv.slice(2);

  // Case A: workspace dev environment
  if (fs.existsSync(workspaceVenv)) {
    return runExecutable(workspaceVenv, args);
  }

  // Case B: already installed in ~/.argos/venv
  if (fs.existsSync(userVenv)) {
    return runExecutable(userVenv, args);
  }

  // Case C: try global command in PATH
  try {
    const test = spawnSync(isWin ? 'where' : 'which', ['argos'], { stdio: 'pipe' });
    if (test.status === 0) {
      return runExecutable('argos', args);
    }
  } catch (_) {}

  // Case D: First-time setup - auto install to ~/.argos/venv
  console.log('\x1b[36m⚡ [Argos] 检测到首次通过 npm 启动，正在初始化 Python 运行时环境...\x1b[0m');
  const pythonCmd = findPython();
  if (!pythonCmd) {
    console.error('\x1b[31m[Argos] 错误: 未检测到系统 Python 环境 (需要 Python >= 3.9)。\x1b[0m');
    console.error('请先前往 https://www.python.org/ 或使用 winget/brew 安装 Python。');
    process.exit(1);
  }

  fs.mkdirSync(argosHome, { recursive: true });
  const venvDir = path.join(argosHome, 'venv');
  console.log(`[Argos] 正在创建隔离环境: ${venvDir} ...`);

  // Create venv
  const createVenv = spawnSync(pythonCmd, ['-m', 'venv', venvDir], { stdio: 'inherit' });
  if (createVenv.status !== 0) {
    console.error('\x1b[31m[Argos] 创建虚拟环境失败。\x1b[0m');
    process.exit(1);
  }

  // Install argos-agent from PyPI or local wheel
  const venvPip = path.join(venvDir, isWin ? 'Scripts' : 'bin', isWin ? 'pip.exe' : 'pip');
  console.log('[Argos] 正在安装 argos-agent 核心引擎...');
  const installRes = spawnSync(venvPip, ['install', '-U', 'argos-agent'], { stdio: 'inherit' });
  if (installRes.status !== 0) {
    console.warn('\x1b[33m[Argos] PyPI 安装中，尝试直接安装依赖包...\x1b[0m');
  }

  if (fs.existsSync(userVenv)) {
    return runExecutable(userVenv, args);
  } else {
    // fallback run python module directly
    const venvPython = path.join(venvDir, isWin ? 'Scripts' : 'bin', isWin ? 'python.exe' : 'python');
    return runExecutable(venvPython, ['-m', 'server_helper.cli', ...args]);
  }
}

main();
