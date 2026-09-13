const { app, BrowserWindow, Menu, shell } = require('electron')
const path = require('node:path')

const DEFAULT_DEV_PORT = 5188
const DEV_URL = process.env.VITE_DEV_SERVER_URL || `http://127.0.0.1:${DEFAULT_DEV_PORT}`
const isDev = process.env.ELECTRON_DEV === '1' && !app.isPackaged

function isAllowedUrl(url) {
  if (url.startsWith('file:')) return true
  if (!isDev) return false
  try {
    const incoming = new URL(url)
    const allowed = new URL(DEV_URL)
    const hosts = new Set(['127.0.0.1', 'localhost', allowed.hostname])
    const port = allowed.port || String(DEFAULT_DEV_PORT)
    return (
      (incoming.protocol === 'http:' || incoming.protocol === 'https:') &&
      hosts.has(incoming.hostname) &&
      incoming.port === port
    )
  } catch {
    return false
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 720,
    minHeight: 560,
    title: 'Econ Trainer',
    backgroundColor: '#f3ead8',
    autoHideMenuBar: process.platform !== 'darwin',
    icon: path.join(__dirname, '../build/icon.png'),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  win.once('ready-to-show', () => win.show())

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  win.webContents.on('will-navigate', (event, url) => {
    if (!isAllowedUrl(url)) {
      event.preventDefault()
      shell.openExternal(url)
    }
  })

  if (isDev) {
    win.loadURL(DEV_URL)
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

function installMenu() {
  if (process.platform !== 'darwin') {
    Menu.setApplicationMenu(null)
    return
  }

  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      {
        label: app.name,
        submenu: [
          { role: 'about' },
          { type: 'separator' },
          { role: 'hide' },
          { role: 'hideOthers' },
          { role: 'unhide' },
          { type: 'separator' },
          { role: 'quit' },
        ],
      },
      { role: 'editMenu' },
      { role: 'windowMenu' },
    ]),
  )
}

app.setName('Econ Trainer')

app.whenReady().then(() => {
  installMenu()
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
