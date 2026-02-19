const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
    // Platform info
    platform: process.platform,
    
    // Window controls
    minimize: () => ipcRenderer.send('window-minimize'),
    maximize: () => ipcRenderer.send('window-maximize'),
    close: () => ipcRenderer.send('window-close'),
    
    // App info
    getVersion: () => ipcRenderer.invoke('get-version'),
    
    // Open external
    openExternal: (url) => ipcRenderer.invoke('open-external', url)
});

// Log that preload is ready
console.log('Preload script loaded');
