// 阅卷无忧 - Electron主进程
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow = null;

// 项目根目录
const isPackaged = app.isPackaged;
const PROJECT_DIR = isPackaged
  ? process.resourcesPath
  : path.join(__dirname, '..');

// pipeline.exe 路径
const PIPELINE_EXE = isPackaged
  ? path.join(process.resourcesPath, 'pipeline.exe')
  : path.join(__dirname, 'resources', 'pipeline.exe');

function spawnPipeline(subcommand, args, options = {}) {
  const allArgs = [subcommand, ...args];
  console.log('[Main] Spawning pipeline:', PIPELINE_EXE, allArgs.join(' '));
  return spawn(PIPELINE_EXE, allArgs, {
    cwd: PROJECT_DIR,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    ...options,
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: '阅卷无忧',
    icon: path.join(__dirname, 'renderer', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }
}

// ========== IPC处理 ==========

// 用系统默认程序打开文件
ipcMain.handle('shell:openPath', async (_, filePath) => {
  try {
    const result = await shell.openPath(filePath);
    return { success: result === '', error: result || null };
  } catch (e) {
    return { success: false, error: e.message };
  }
});

// 选择文件
ipcMain.handle('dialog:openFile', async (_, options) => {
  const dialogOptions = {
    title: options?.title || '选择文件',
    filters: options?.filters || [
      { name: 'PDF文件', extensions: ['pdf'] },
      { name: 'JSON配置文件', extensions: ['json'] },
      { name: '所有文件', extensions: ['*'] },
    ],
    properties: options?.properties || ['openFile'],
  };

  if (options?.properties && options.properties.includes('openDirectory')) {
    dialogOptions.properties = ['openDirectory'];
  }

  const result = await dialog.showOpenDialog(mainWindow, dialogOptions);

  if (result.canceled || result.filePaths.length === 0) return null;

  return result.filePaths[0];
});

// 运行扫描判分
ipcMain.handle('pipeline:run', async (_, params) => {
  const { configPath, pdfPath, outputDir, duplex } = params;

  return new Promise((resolve) => {
    const outPath = path.join(outputDir, 'grade_results.json');
    const args = [
      '--config', configPath,
      '--scan', pdfPath,
      '--output', outPath,
      '--resume',
    ];
    if (duplex) args.push('--duplex');

    const proc = spawnPipeline('scan-and-grade', args);

    let stdout = '', stderr = '';

    proc.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('pipeline:progress', text);
      }
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('pipeline:progress', data.toString());
      }
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve({ success: true, output: stdout });
      } else {
        resolve({ success: false, error: stderr || stdout || `exit code ${code}` });
      }
    });

    proc.on('error', (err) => {
      resolve({ success: false, error: `启动失败 (${err.code || err.errno}): ${err.message}` });
    });
  });
});

// 读取JSON结果
ipcMain.handle('pipeline:loadResults', async (_, filePath) => {
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    return { success: true, data };
  } catch (e) {
    return { success: false, error: e.message };
  }
});

// 生成成绩报告
ipcMain.handle('report:generate', async (_, params) => {
  const { resultsPath, configPath, outputPath } = params;
  return new Promise((resolve) => {
    const proc = spawnPipeline('report', [
      '--results', resultsPath,
      '--config', configPath,
      '--output', outputPath,
      '--format', 'pdf',
    ]);

    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      resolve(code === 0
        ? { success: true, output: stdout, path: outputPath }
        : { success: false, error: stdout || `exit code ${code}` });
    });
  });
});

// 错题入库
ipcMain.handle('db:import', async (_, params) => {
  const { resultsPath, configPath, dbPath } = params;
  return new Promise((resolve) => {
    const proc = spawnPipeline('db', [
      '--db', dbPath,
      'import-results',
      '--results', resultsPath,
      '--config', configPath,
    ]);

    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      resolve(code === 0
        ? { success: true, output: stdout }
        : { success: false, error: stdout || `exit code ${code}` });
    });
  });
});

// 错题查询
ipcMain.handle('db:queryWrongBook', async (_, params) => {
  const { dbPath, studentId, kp } = params;
  return new Promise((resolve) => {
    const args = ['--db', dbPath, 'query-wrong'];
    if (studentId) args.push('--student', studentId);
    if (kp) args.push('--kp', kp);

    const proc = spawnPipeline('db', args);

    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      resolve(code === 0
        ? { success: true, output: stdout }
        : { success: false, error: stdout || `exit code ${code}` });
    });
  });
});

// 导入学生名单
ipcMain.handle('roster:import', async (_, params) => {
  const { dbPath, csvPath, className } = params;
  return new Promise((resolve) => {
    const args = ['--db', dbPath, 'import-students', '--file', csvPath];
    if (className) args.push('--class-name', className);

    const proc = spawnPipeline('db', args);
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      resolve(code === 0
        ? { success: true, output: stdout }
        : { success: false, error: stdout || `exit code ${code}` });
    });
  });
});

// 查询学生姓名
ipcMain.handle('student:lookup', async (_, params) => {
  const { dbPath, studentId } = params;
  return new Promise((resolve) => {
    const proc = spawnPipeline('db', ['--db', dbPath, 'query-student', '--id', studentId]);
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0 && stdout.trim()) {
        try {
          const data = JSON.parse(stdout.trim());
          resolve({ success: true, data });
        } catch (e) {
          resolve({ success: true, data: null });
        }
      } else {
        resolve({ success: true, data: null });
      }
    });
  });
});

// 批量查询学生
ipcMain.handle('student:batchLookup', async (_, params) => {
  const { dbPath, studentIds } = params;
  if (!studentIds || studentIds.length === 0) return { success: true, data: {} };

  return new Promise((resolve) => {
    const proc = spawnPipeline('db', [
      '--db', dbPath, 'batch-students', '--ids', studentIds.join(','),
    ]);
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0 && stdout.trim()) {
        try { resolve({ success: true, data: JSON.parse(stdout.trim()) }); }
        catch (e) { resolve({ success: false, error: '解析失败' }); }
      } else {
        resolve({ success: true, data: {} });
      }
    });
    proc.on('error', (e) => { resolve({ success: false, error: e.message }); });
  });
});

// 考试列表
ipcMain.handle('stats:listExams', async (_, params) => {
  const { dbPath } = params;
  return new Promise((resolve) => {
    const proc = spawnPipeline('db', ['--db', dbPath, 'list-exams']);
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0 && stdout.trim()) {
        try { resolve({ success: true, data: JSON.parse(stdout.trim()) }); }
        catch (e) { resolve({ success: false, error: '解析失败' }); }
      } else {
        resolve({ success: false, error: stdout || `exit code ${code}` });
      }
    });
  });
});

// 检查是否有中断的批改进度
ipcMain.handle('pipeline:checkResume', async (_, params) => {
  const { outputDir } = params;
  const progressPath = path.join(outputDir, 'grade_results.progress.json');
  try {
    if (fs.existsSync(progressPath)) {
      const data = JSON.parse(fs.readFileSync(progressPath, 'utf-8'));
      return {
        success: true,
        canResume: true,
        donePages: data.done_pages || 0,
        totalPages: data.total_pages || 0,
      };
    }
    return { success: true, canResume: false };
  } catch (e) {
    return { success: true, canResume: false };
  }
});

ipcMain.handle('stats:examStats', async (_, params) => {
  const { dbPath, examId } = params;
  return new Promise((resolve) => {
    const args = ['--db', dbPath, 'exam-stats'];
    if (examId) args.push('--exam-id', String(examId));

    const proc = spawnPipeline('db', args);
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0 && stdout.trim() && stdout.trim() !== 'null') {
        try { resolve({ success: true, data: JSON.parse(stdout.trim()) }); }
        catch (e) { resolve({ success: false, error: '解析失败' }); }
      } else {
        resolve({ success: true, data: null });
      }
    });
  });
});

// 导出成绩
ipcMain.handle('export:exportGrades', async (_, params) => {
  const { dbPath, outputPath, examId } = params;
  return new Promise((resolve) => {
    const args = ['--db', dbPath, 'export-grades', '--output', outputPath];
    if (examId) args.push('--exam-id', String(examId));

    const proc = spawnPipeline('export', args);
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      resolve(code === 0
        ? { success: true, output: stdout.trim(), path: outputPath }
        : { success: false, error: stdout.trim() || `exit code ${code}` });
    });
    proc.on('error', (e) => { resolve({ success: false, error: e.message }); });
  });
});

// 导出错题
ipcMain.handle('export:exportWrong', async (_, params) => {
  const { dbPath, outputPath, examId } = params;
  return new Promise((resolve) => {
    const args = ['--db', dbPath, 'export-wrong-answers', '--output', outputPath];
    if (examId) args.push('--exam-id', String(examId));

    const proc = spawnPipeline('export', args);
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      resolve(code === 0
        ? { success: true, output: stdout.trim(), path: outputPath }
        : { success: false, error: stdout.trim() || `exit code ${code}` });
    });
    proc.on('error', (e) => { resolve({ success: false, error: e.message }); });
  });
});

// 多考试对比
ipcMain.handle('stats:compareExams', async (_, params) => {
  const { dbPath, examIds } = params;
  return new Promise((resolve) => {
    const args = ['--db', dbPath, 'compare-exams', '--ids', examIds.join(',')];

    const proc = spawnPipeline('db', args);
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      try { resolve({ success: true, data: JSON.parse(stdout.trim()) }); }
      catch (e) { resolve({ success: false, error: stderr || stdout }); }
    });
    proc.on('error', (e) => { resolve({ success: false, error: e.message }); });
  });
});

// 学生个人统计
ipcMain.handle('stats:studentStats', async (_, params) => {
  const { dbPath, studentId } = params;
  return new Promise((resolve) => {
    const proc = spawnPipeline('db', [
      '--db', dbPath, 'student-stats', '--student-id', studentId,
    ]);
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0 && stdout.trim() && stdout.trim() !== 'null') {
        try { resolve({ success: true, data: JSON.parse(stdout.trim()) }); }
        catch (e) { resolve({ success: false, error: '解析失败' }); }
      } else {
        resolve({ success: true, data: null });
      }
    });
    proc.on('error', (e) => { resolve({ success: false, error: e.message }); });
  });
});

// 审阅：语义重判
ipcMain.handle('review:rejudge', async (_, params) => {
  const { ocrText, correctAnswer } = params;
  return new Promise((resolve) => {
    const proc = spawnPipeline('rejudge', [
      '--ocr-text', ocrText,
      '--correct-answer', correctAnswer,
    ]);
    let stdout = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0 && stdout.trim()) {
        try { resolve({ success: true, data: JSON.parse(stdout.trim()) }); }
        catch (e) { resolve({ success: false, error: '解析失败' }); }
      } else {
        resolve({ success: false, error: stdout || `exit code ${code}` });
      }
    });
    proc.on('error', (e) => { resolve({ success: false, error: e.message }); });
  });
});

// ========== 应用生命周期 ==========
app.whenReady().then(() => {
  try {
    console.log('[Main] Project dir:', PROJECT_DIR);
    console.log('[Main] Pipeline exe:', PIPELINE_EXE);
    createWindow();
  } catch (e) {
    console.error('[Main] CRASH:', e.message, e.stack);
    dialog.showErrorBox('启动失败', e.message + '\n' + (e.stack || ''));
    app.quit();
  }
});

app.on('window-all-closed', () => {
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
