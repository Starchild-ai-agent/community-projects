const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('petAPI', {
  getConfig: () => ipcRenderer.invoke('config:get'),
  saveConfig: (config) => ipcRenderer.invoke('config:save', config),
  uploadAsset: () => ipcRenderer.invoke('asset:upload'),
  setCurrentAsset: (id) => ipcRenderer.invoke('asset:setCurrent', id),
  deleteAsset: (id) => ipcRenderer.invoke('asset:delete', id),
  openPanel: () => ipcRenderer.invoke('panel:open'),
  onConfigUpdated: (handler) => {
    const listener = (_event, data) => handler(data);
    ipcRenderer.on('config:updated', listener);
    return () => ipcRenderer.removeListener('config:updated', listener);
  }
});
