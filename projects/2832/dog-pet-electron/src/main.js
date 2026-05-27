const { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage } = require('electron');
const fs = require('fs');
const path = require('path');

let petWindow = null;
let panelWindow = null;
let tray = null;

const PROJECT_ROOT = __dirname;
const ASSETS_DIR = path.join(PROJECT_ROOT, 'assets');
const USER_MEDIA_DIR = path.join(ASSETS_DIR, 'user-media');
const CONFIG_PATH = path.join(ASSETS_DIR, 'config.json');

const ALLOWED_EXTENSIONS = new Set(['.webp', '.webm', '.mp4', '.mov', '.gif']);
const VIDEO_EXTENSIONS = new Set(['.webm', '.mp4', '.mov']);

function ensureDirs() {
  fs.mkdirSync(USER_MEDIA_DIR, { recursive: true });
}

function defaultConfig() {
  return {
    currentAssetId: 'placeholder-dog',
    assets: [
      {
        id: 'placeholder-dog',
        name: '狗狗占位符',
        type: 'placeholder',
        path: ''
      }
    ],
    buttons: ['摸摸头', '握握手', '转圈圈'],
    responses: ['汪！', '好开心！', '再和我玩一会儿吧~'],
    idleMessages: ['我在这儿等你～', '记得喝水和休息哦。'],
    petSize: 220,
    autoLaunch: false
  };
}

function normalizeConfig(parsed) {
  const defaults = defaultConfig();
  return {
    ...defaults,
    ...parsed,
    assets: Array.isArray(parsed.assets) && parsed.assets.length ? parsed.assets : defaults.assets,
    buttons: Array.isArray(parsed.buttons) && parsed.buttons.length ? parsed.buttons : defaults.buttons,
    responses: Array.isArray(parsed.responses) && parsed.responses.length ? parsed.responses : defaults.responses,
    idleMessages: Array.isArray(parsed.idleMessages) && parsed.idleMessages.length ? parsed.idleMessages : defaults.idleMessages,
    petSize: Number(parsed.petSize) > 0 ? Number(parsed.petSize) : defaults.petSize,
    autoLaunch: Boolean(parsed.autoLaunch)
  };
}

function readConfig() {
  ensureDirs();
  if (!fs.existsSync(CONFIG_PATH)) {
    const config = defaultConfig();
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf-8');
    return config;
  }

  try {
    const raw = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const parsed = JSON.parse(raw);
    const config = normalizeConfig(parsed || {});
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf-8');
    return config;
  } catch {
    const config = defaultConfig();
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf-8');
    return config;
  }
}

function saveConfig(config) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf-8');
}

function applyAutoLaunch(enabled) {
  if (process.platform === 'darwin' || process.platform === 'win32') {
    app.setLoginItemSettings({ openAtLogin: Boolean(enabled) });
  }
}

function createPetWindow() {
  const config = readConfig();
  const size = Math.max(120, Math.min(600, Number(config.petSize) || 220));

  petWindow = new BrowserWindow({
    width: size,
    height: size + 80,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    webPreferences: {
      preload: path.join(PROJECT_ROOT, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  petWindow.loadFile(path.join(PROJECT_ROOT, 'pet.html'));
}

function createPanelWindow() {
  if (panelWindow && !panelWindow.isDestroyed()) {
    panelWindow.show();
    panelWindow.focus();
    return;
  }

  panelWindow = new BrowserWindow({
    width: 760,
    height: 860,
    minWidth: 640,
    minHeight: 680,
    title: '狗狗桌宠控制面板',
    webPreferences: {
      preload: path.join(PROJECT_ROOT, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  panelWindow.loadFile(path.join(PROJECT_ROOT, 'panel.html'));

  panelWindow.on('closed', () => {
    panelWindow = null;
  });
}

function createTray() {
  if (tray) return;

  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAQAAAC1+jfqAAAAP0lEQVR42mP8z8AARMDwH4j/GRgYGLA0YIYB4j8GBgYGBv4jQyQxMDCQGQx0lQxYgDI6kY4iYAEAb5oN+9oIoS8AAAAASUVORK5CYII='
  );

  tray = new Tray(icon);
  tray.setToolTip('狗狗桌宠');

  const refreshMenu = () => {
    const config = readConfig();
    const contextMenu = Menu.buildFromTemplate([
      {
        label: petWindow && petWindow.isVisible() ? '隐藏狗狗' : '显示狗狗',
        click: () => {
          if (!petWindow || petWindow.isDestroyed()) return;
          if (petWindow.isVisible()) petWindow.hide();
          else petWindow.show();
          refreshMenu();
        }
      },
      {
        label: '打开控制面板',
        click: () => createPanelWindow()
      },
      {
        label: config.autoLaunch ? '关闭开机自启动' : '开启开机自启动',
        click: () => {
          const next = { ...config, autoLaunch: !config.autoLaunch };
          saveConfig(next);
          applyAutoLaunch(next.autoLaunch);
          broadcastConfigUpdated(next);
          refreshMenu();
        }
      },
      { type: 'separator' },
      {
        label: '退出',
        click: () => app.quit()
      }
    ]);
    tray.setContextMenu(contextMenu);
  };

  tray.on('double-click', () => {
    if (petWindow && !petWindow.isDestroyed()) {
      petWindow.show();
      petWindow.focus();
    }
  });

  refreshMenu();
}

function broadcastConfigUpdated(config) {
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.webContents.send('config:updated', config);
  }
  if (panelWindow && !panelWindow.isDestroyed()) {
    panelWindow.webContents.send('config:updated', config);
  }
}

function toAssetType(ext) {
  return VIDEO_EXTENSIONS.has(ext) ? 'video' : 'image';
}

ipcMain.handle('config:get', async () => {
  return readConfig();
});

ipcMain.handle('config:save', async (_event, nextConfig) => {
  const current = readConfig();
  const merged = {
    ...current,
    ...nextConfig,
    buttons: Array.isArray(nextConfig.buttons) ? nextConfig.buttons : current.buttons,
    responses: Array.isArray(nextConfig.responses) ? nextConfig.responses : current.responses,
    idleMessages: Array.isArray(nextConfig.idleMessages) ? nextConfig.idleMessages : current.idleMessages,
    assets: Array.isArray(nextConfig.assets) && nextConfig.assets.length ? nextConfig.assets : current.assets,
    petSize: Number(nextConfig.petSize) > 0 ? Number(nextConfig.petSize) : current.petSize,
    autoLaunch: typeof nextConfig.autoLaunch === 'boolean' ? nextConfig.autoLaunch : current.autoLaunch
  };

  const validCurrent = merged.assets.some((a) => a.id === merged.currentAssetId);
  if (!validCurrent) {
    merged.currentAssetId = merged.assets[0]?.id || 'placeholder-dog';
  }

  saveConfig(merged);
  applyAutoLaunch(merged.autoLaunch);
  broadcastConfigUpdated(merged);

  if (petWindow && !petWindow.isDestroyed()) {
    const size = Math.max(120, Math.min(600, Number(merged.petSize) || 220));
    petWindow.setSize(size, size + 80, true);
  }

  return { ok: true, config: merged };
});

ipcMain.handle('asset:upload', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择狗狗素材',
    properties: ['openFile'],
    filters: [{ name: 'Dog Media', extensions: ['webp', 'webm', 'mp4', 'mov', 'gif'] }]
  });

  if (result.canceled || !result.filePaths.length) {
    return { ok: false, reason: 'canceled' };
  }

  const sourcePath = result.filePaths[0];
  const ext = path.extname(sourcePath).toLowerCase();
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return { ok: false, reason: 'unsupported_type' };
  }

  ensureDirs();
  const id = `asset_${Date.now()}`;
  const safeName = path.basename(sourcePath).replace(/[^a-zA-Z0-9._-\u4e00-\u9fa5]/g, '_');
  const fileName = `${id}_${safeName}`;
  const targetPath = path.join(USER_MEDIA_DIR, fileName);

  fs.copyFileSync(sourcePath, targetPath);

  const relPath = path.relative(PROJECT_ROOT, targetPath).split(path.sep).join('/');
  const config = readConfig();
  const asset = {
    id,
    name: path.basename(sourcePath),
    type: toAssetType(ext),
    path: relPath
  };

  config.assets.push(asset);
  config.currentAssetId = id;
  saveConfig(config);
  broadcastConfigUpdated(config);

  return { ok: true, asset, config };
});

ipcMain.handle('asset:setCurrent', async (_event, id) => {
  const config = readConfig();
  const exists = config.assets.some((a) => a.id === id);
  if (!exists) return { ok: false, reason: 'not_found' };

  config.currentAssetId = id;
  saveConfig(config);
  broadcastConfigUpdated(config);
  return { ok: true, config };
});

ipcMain.handle('asset:delete', async (_event, id) => {
  const config = readConfig();
  const idx = config.assets.findIndex((a) => a.id === id);
  if (idx < 0) return { ok: false, reason: 'not_found' };

  const deleting = config.assets[idx];
  if (deleting.path && deleting.path.startsWith('assets/user-media/')) {
    const abs = path.join(PROJECT_ROOT, deleting.path);
    if (fs.existsSync(abs)) fs.unlinkSync(abs);
  }

  config.assets.splice(idx, 1);
  if (!config.assets.length) {
    config.assets = defaultConfig().assets;
  }

  if (!config.assets.some((a) => a.id === config.currentAssetId)) {
    config.currentAssetId = config.assets[0].id;
  }

  saveConfig(config);
  broadcastConfigUpdated(config);
  return { ok: true, config };
});

ipcMain.handle('panel:open', async () => {
  createPanelWindow();
  return { ok: true };
});

app.whenReady().then(() => {
  ensureDirs();
  const config = readConfig();
  applyAutoLaunch(config.autoLaunch);

  createPetWindow();
  createPanelWindow();
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createPetWindow();
      createPanelWindow();
      createTray();
    }
  });
});

app.on('window-all-closed', () => {
  // macOS 保持应用常驻（托盘/状态栏）
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
