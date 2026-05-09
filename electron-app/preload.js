// 阅卷无忧 - 安全桥接（contextBridge）
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('yuejuan', {
  // 文件选择
  openFile: (options) => ipcRenderer.invoke('dialog:openFile', options),
  // 系统默认程序打开文件
  openPath: (filePath) => ipcRenderer.invoke('shell:openPath', filePath),

  // 流水线
  runPipeline: (params) => ipcRenderer.invoke('pipeline:run', params),
  checkResume: (params) => ipcRenderer.invoke('pipeline:checkResume', params),
  onProgress: (callback) => {
    const handler = (_, data) => callback(data);
    ipcRenderer.on('pipeline:progress', handler);
    return () => ipcRenderer.removeListener('pipeline:progress', handler);
  },
  loadResults: (path) => ipcRenderer.invoke('pipeline:loadResults', path),

  // 报告
  generateReport: (params) => ipcRenderer.invoke('report:generate', params),

  // 数据库
  importToDB: (params) => ipcRenderer.invoke('db:import', params),
  queryWrongBook: (params) => ipcRenderer.invoke('db:queryWrongBook', params),

  // 学生管理
  importRoster: (params) => ipcRenderer.invoke('roster:import', params),
  lookupStudent: (params) => ipcRenderer.invoke('student:lookup', params),
  batchLookupStudents: (params) => ipcRenderer.invoke('student:batchLookup', params),

  // 统计
  listExams: (params) => ipcRenderer.invoke('stats:listExams', params),
  examStats: (params) => ipcRenderer.invoke('stats:examStats', params),
  compareExams: (params) => ipcRenderer.invoke('stats:compareExams', params),
  studentStats: (params) => ipcRenderer.invoke('stats:studentStats', params),

  // 导出
  exportGrades: (params) => ipcRenderer.invoke('export:exportGrades', params),
  exportWrong: (params) => ipcRenderer.invoke('export:exportWrong', params),

  // 审阅
  rejudge: (params) => ipcRenderer.invoke('review:rejudge', params),
});
