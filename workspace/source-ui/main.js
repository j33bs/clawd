const { app, BrowserWindow, Tray, Menu, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let tray = null;
let backendProcess = null;

const SOURCE_UI_URL = 'http://127.0.0.1:18990';
const BACKEND_SCRIPT = path.join(__dirname, 'app.py');

function startBackend() {
    console.log('Starting Source UI backend...');
    backendProcess = spawn('python3', [BACKEND_SCRIPT, '--port', '18990'], {
        cwd: __dirname,
        detached: true,
        stdio: 'ignore'
    });
    
    backendProcess.unref();
    
    // Wait for backend to start
    setTimeout(() => {
        console.log('Backend started');
    }, 2000);
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1024,
        minHeight: 700,
        title: 'Source UI',
        backgroundColor: '#0a0a0f',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        show: false
    });

    // Load the app
    mainWindow.loadURL(SOURCE_UI_URL);

    // Show when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        console.log('Window shown');
    });

    // Handle window close
    mainWindow.on('close', (event) => {
        if (!app.isQuitting) {
            event.preventDefault();
            mainWindow.hide();
        }
    });

    // Open external links in default browser
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });

    // Dev in tools development
    if (process.argv.includes('--dev')) {
        mainWindow.webContents.openDevTools();
    }
}

function createTray() {
    // Use a simple 16x16 icon
    const iconPath = path.join(__dirname, 'icon.png');
    
    tray = new Tray(iconPath);
    
    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Open Source UI',
            click: () => {
                if (mainWindow) {
                    mainWindow.show();
                    mainWindow.focus();
                }
            }
        },
        {
            label: 'Refresh',
            click: () => {
                if (mainWindow) {
                    mainWindow.reload();
                }
            }
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => {
                app.isQuitting = true;
                app.quit();
            }
        }
    ]);
    
    tray.setToolTip('Source UI - OpenClaw Control Center');
    tray.setContextMenu(contextMenu);
    
    tray.on('double-click', () => {
        if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
        }
    });
}

function createMenu() {
    const template = [
        {
            label: 'File',
            submenu: [
                {
                    label: 'Refresh',
                    accelerator: 'CmdOrCtrl+R',
                    click: () => {
                        if (mainWindow) mainWindow.reload();
                    }
                },
                { type: 'separator' },
                {
                    label: 'Quit',
                    accelerator: 'CmdOrCtrl+Q',
                    click: () => {
                        app.isQuitting = true;
                        app.quit();
                    }
                }
            ]
        },
        {
            label: 'View',
            submenu: [
                {
                    label: 'Toggle Full Screen',
                    accelerator: 'F11',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.setFullScreen(!mainWindow.isFullScreen());
                        }
                    }
                },
                {
                    label: 'Toggle Developer Tools',
                    accelerator: 'CmdOrCtrl+Shift+I',
                    click: () => {
                        if (mainWindow) {
                            mainWindow.webContents.toggleDevTools();
                        }
                    }
                }
            ]
        },
        {
            label: 'Window',
            submenu: [
                {
                    label: 'Minimize',
                    accelerator: 'CmdOrCtrl+M',
                    click: () => {
                        if (mainWindow) mainWindow.minimize();
                    }
                },
                {
                    label: 'Close',
                    accelerator: 'CmdOrCtrl+W',
                    click: () => {
                        if (mainWindow) mainWindow.hide();
                    }
                }
            ]
        },
        {
            label: 'Help',
            submenu: [
                {
                    label: 'About Source UI',
                    click: () => {
                        const { dialog } = require('electron');
                        dialog.showMessageBox(mainWindow, {
                            type: 'info',
                            title: 'About Source UI',
                            message: 'Source UI v1.0.0',
                            detail: 'OpenClaw System Management Dashboard\n\nA beautiful control center for OpenClaw.'
                        });
                    }
                }
            ]
        }
    ];
    
    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

// App ready
app.whenReady().then(() => {
    console.log('App ready, starting backend...');
    startBackend();
    createWindow();
    createTray();
    createMenu();
});

// Quit when all windows closed (except on macOS)
app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

// Cleanup on quit
app.on('before-quit', () => {
    app.isQuitting = true;
    
    // Kill backend process
    if (backendProcess) {
        try {
            process.kill(-backendProcess.pid);
        } catch (e) {
            console.log('Could not kill backend');
        }
    }
});

console.log('Source UI Electron app loaded');
