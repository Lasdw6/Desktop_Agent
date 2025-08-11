// Electron main process (ESM)
import { app, BrowserWindow, ipcMain, screen } from 'electron';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let mainWindow /**: BrowserWindow | null */ = null;

function createWindow() {
  const { bounds } = screen.getPrimaryDisplay();
  const win = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    frame: false,
    transparent: true,
    hasShadow: false,
    alwaysOnTop: true,
    fullscreen: false,
    autoHideMenuBar: true,
    skipTaskbar: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#00000000',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, 'preload.cjs')
    },
    title: 'Desktop Assistant Overlay'
  });

  const isDev = !app.isPackaged;

  if (isDev) {
    // Vite dev server (updated port)
    win.loadURL('http://localhost:5174');
  } else {
    // Load built files
    const indexPath = path.join(__dirname, '..', 'dist', 'index.html');
    win.loadFile(indexPath);
  }

  // Make the overlay click-through by default, but allow forwarding to underlying apps
  win.setIgnoreMouseEvents(true, { forward: true });

  mainWindow = win;
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC to toggle click-through behavior
ipcMain.on('overlay:setInteractive', (event, interactive) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win) return;
  if (interactive) {
    win.setIgnoreMouseEvents(false);
    win.setAlwaysOnTop(true, 'screen-saver');
  } else {
    win.setIgnoreMouseEvents(true, { forward: true });
    win.setAlwaysOnTop(true, 'screen-saver');
  }
});

// Hide/show window for clean screenshots
ipcMain.handle('overlay:hide', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.hide();
    return true;
  }
  return false;
});

ipcMain.handle('overlay:show', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.setAlwaysOnTop(true, 'screen-saver');
    return true;
  }
  return false;
});


