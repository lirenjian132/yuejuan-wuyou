// ============================================================
// 阅卷无忧 — 渲染进程主逻辑
// ============================================================

// 安全桥接引用（通过 preload.js 注入）
const api = window.yuejuan;

// ========== 全局状态 ==========
const state = {
  configPath: '',
  pdfPath: '',
  outputDir: '',
  resultsPath: '',
  lastResults: null,
  progressCleanup: null,
  activeTab: 'grade',
  duplex: false,  // 双面扫描
};

// ========== DOM引用缓存 ==========
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initFilePickers();
  initButtons();
  loadSettings();
});

// ========== 标签切换 ==========
function initTabs() {
  $$('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      switchTab(tab);
    });
  });
}

function switchTab(tab) {
  state.activeTab = tab;
  $$('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  $$('.tab-content').forEach(s => s.classList.toggle('active', s.id === `tab-${tab}`));
  if (tab === 'analysis') loadExamList();
}

// ========== 文件选择器 ==========
function initFilePickers() {
  // 批改页
  bindFilePicker('btnPickConfig', 'configPath', {
    title: '选择考试配置文件',
    filters: [{ name: 'JSON配置文件', extensions: ['json'] }],
  });
  bindFilePicker('btnPickPdf', 'pdfPath', {
    title: '选择答题卡/试卷PDF',
    filters: [{ name: 'PDF文件', extensions: ['pdf'] }],
  });
  bindDirPicker('btnPickOutput', 'outputDir', { title: '选择输出目录' });

  // 设置页
  bindDirPicker('btnSetOutput', 'setOutputDir', { title: '选择默认输出目录' });
  bindFilePicker('btnSetDb', 'setDbPath', {
    title: '选择或输入数据库文件',
    filters: [{ name: 'SQLite数据库或任意文件', extensions: ['db', 'sqlite', 'sqlite3', '*'] }],
  });
}

function bindFilePicker(btnId, inputId, options) {
  const btn = $(`#${btnId}`);
  const input = $(`#${inputId}`);
  if (!btn || !input) return;
  btn.addEventListener('click', async () => {
    const path = await api.openFile(options);
    if (path) {
      input.value = path;
      syncState(inputId, path);
    }
  });
}

function bindDirPicker(btnId, inputId, options) {
  const btn = $(`#${btnId}`);
  const input = $(`#${inputId}`);
  if (!btn || !input) return;
  btn.addEventListener('click', async () => {
    // Electron dialog with openDirectory property
    const path = await api.openFile({
      ...options,
      properties: ['openDirectory'],
      filters: [],
    });
    if (path) {
      input.value = path;
      syncState(inputId, path);
    }
  });
}

function syncState(inputId, value) {
  if (inputId === 'configPath') state.configPath = value;
  if (inputId === 'pdfPath') state.pdfPath = value;
  if (inputId === 'outputDir') state.outputDir = value;
}

// ========== 按钮事件 ==========
function initButtons() {
  // 批改
  $('#btnStart')?.addEventListener('click', startGrading);
  $('#btnReport')?.addEventListener('click', generateReport);
  $('#btnImportDB')?.addEventListener('click', importToDatabase);
  // 导出
  $('#btnExportGrades')?.addEventListener('click', exportGrades);
  $('#btnExportWrong')?.addEventListener('click', exportWrong);
  // 错题本
  $('#btnQueryWrong')?.addEventListener('click', queryWrongBook);
  // 设置
  $('#btnSaveSettings')?.addEventListener('click', saveSettings);
  $('#btnImportRoster')?.addEventListener('click', importRoster);
  bindFilePicker('btnPickRoster', 'rosterPath', {
    title: '选择学生名单CSV',
    filters: [{ name: 'CSV文件', extensions: ['csv'] }],
  });
  // 数据分析
  $('#btnLoadAnalysis')?.addEventListener('click', loadAnalysis);
}

// ========== 批改流程 ==========
async function startGrading() {
  // 同步输入框的值
  syncState('configPath', $('#configPath').value);
  syncState('pdfPath', $('#pdfPath').value);
  syncState('outputDir', $('#outputDir').value);
  state.duplex = $('#chkDuplex')?.checked || false;

  if (!state.configPath) return alert('请选择考试配置文件');
  if (!state.pdfPath) return alert('请选择答题卡/试卷PDF');
  if (!state.outputDir) return alert('请选择输出目录');

  // 检查是否有中断的进度
  try {
    const check = await api.checkResume({ outputDir: state.outputDir });
    if (check.canResume) {
      const ok = confirm(
        `检测到上次批改中断！\n已完成 ${check.donePages}/${check.totalPages} 页。\n是否从中断处继续？\n\n（点"确定"继续批改，"取消"将从头开始）`
      );
      if (!ok) {
        // 用户选择从头开始，需要手动清理进度文件
        // Python的--resume会检测config_hash变化自动处理
        // 但为安全起见，提示用户
        if (!confirm('确定要重新批改吗？已完成的结果将丢失。')) return;
      }
    }
  } catch (e) { /* 检查失败，继续正常流程 */ }

  setStatus('⏳ 批改中...', 'busy');
  $('#btnStart').disabled = true;
  $('#btnReport').disabled = true;
  $('#btnImportDB').disabled = true;
  $('#btnExportGrades').disabled = true;
  $('#btnExportWrong').disabled = true;

  // 显示进度面板
  const pp = $('#progressPanel');
  pp.style.display = 'block';
  $('#progressFill').style.width = '0%';
  $('#progressLog').textContent = '';

  // 注册进度回调
  if (state.progressCleanup) state.progressCleanup();
  state.progressCleanup = api.onProgress((text) => {
    $('#progressLog').textContent += text;
    // 自动滚动
    const log = $('#progressLog');
    log.scrollTop = log.scrollHeight;
    // 尝试从输出推断进度
    guessProgress(text);
  });

  try {
    const resultsPath = state.outputDir + '/grade_results.json';
    state.resultsPath = resultsPath;

    const result = await api.runPipeline({
      configPath: state.configPath,
      pdfPath: state.pdfPath,
      outputDir: state.outputDir,
      duplex: state.duplex || false,
    });

    if (result.success) {
      // 加载并显示结果
      const loadResult = await api.loadResults(resultsPath);
      if (loadResult.success) {
        state.lastResults = loadResult.data;
        // 批量查学生姓名
        await loadStudentNames(loadResult.data);
        renderResults(loadResult.data);
        $('#btnReport').disabled = false;
        $('#btnImportDB').disabled = false;
        $('#btnExportGrades').disabled = false;
        $('#btnExportWrong').disabled = false;
        setStatus('✅ 批改完成', '');
        $('#progressFill').style.width = '100%';
      } else {
        alert('结果文件加载失败: ' + loadResult.error);
        setStatus('⚠️ 结果加载失败', 'error');
      }
    } else {
      alert('批改失败: ' + (result.error || '未知错误'));
      setStatus('❌ 批改失败', 'error');
    }
  } catch (err) {
    alert('批改异常: ' + err.message);
    setStatus('❌ 异常: ' + err.message, 'error');
  } finally {
    $('#btnStart').disabled = false;
  }
}

function guessProgress(text) {
  // 从输出文本推测进度百分比
  const fill = $('#progressFill');
  if (!fill) return;
  if (text.includes('完成') || text.includes('done')) {
    fill.style.width = '90%';
  } else if (text.includes('判分') || text.includes('grading')) {
    fill.style.width = '60%';
  } else if (text.includes('OCR') || text.includes('识别')) {
    fill.style.width = '35%';
  } else if (text.includes('加载') || text.includes('load')) {
    fill.style.width = '15%';
  }
}

// ========== 结果渲染 ==========
function renderResults(data) {
  const tbody = $('#resultTable tbody');
  const results = data.results;
  if (!results || results.length === 0) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="6">无批改结果</td></tr>';
    return;
  }

  const maxScore = results[0].total_max || 100;

  let html = '';
  const names = state.studentNames || {};
  for (const s of results) {
    const total = s.total_scored || 0;
    const pct = maxScore > 0 ? (total / maxScore * 100) : 0;
    const scoreClass = pct >= 90 ? 'score-full' : pct >= 60 ? 'score-half' : 'score-zero';
    const hasReview = s.fill_details && s.fill_details.some(d => d.review_flag);
    const statusTag = hasReview ? '<span class="tag-review">🔍待审</span>' : '<span class="tag-ok">✓</span>';
    const name = names[s.student_id] || '-';

    html += `<tr class="result-row" data-student-id="${s.student_id || ''}">
      <td>${s.student_id || '-'}</td>
      <td>${name}</td>
      <td><span class="${scoreClass}">${s.choice_score || 0} / ${s.choice_max || 0}</span></td>
      <td><span class="${scoreClass}">${s.fill_score || 0} / ${s.fill_max || 0}</span></td>
      <td><span class="${scoreClass}"><strong>${total}</strong> / ${maxScore}</span></td>
      <td>${statusTag}</td>
    </tr>`;
  }
  tbody.innerHTML = html;

  // 汇总信息
  const avg = results.reduce((a, s) => a + (s.total_scored || 0), 0) / results.length;
  $('#resultSummary').textContent = `${data.total_students || results.length} 人 | 选择题均分 ${(data.choice_avg || 0).toFixed(1)} | 填空题均分 ${(data.fill_avg || 0).toFixed(1)} | 总分均分 ${avg.toFixed(1)}`;

  // 点击行查看详情
  $$('.result-row').forEach(row => {
    row.addEventListener('click', () => showStudentDetail(row.dataset.studentId));
  });
}

function showStudentDetail(studentId) {
  if (!state.lastResults) return;
  const results = state.lastResults.results;
  const s = results.find(st => st.student_id === studentId);
  if (!s) return;

  const names = state.studentNames || {};
  const name = names[studentId] || '';
  const panel = $('#detailPanel');
  panel.style.display = 'block';
  let html = `<h3>学号 ${s.student_id}${name ? ' — ' + name : ''} 答题详情（总分 ${s.total_scored}/${s.total_max}）</h3>`;

  // 选择题详情
  if (s.choice_details && s.choice_details.length > 0) {
    html += '<p style="font-weight:600;margin-top:8px;color:#6c757d">选择题</p>';
    for (const d of s.choice_details) {
      const cls = d.user === d.correct ? '' : 'wrong';
      html += `<div class="detail-item ${cls}">
        <span class="q-num">Q${d.id}</span>
        <span>正确答案: ${d.correct}</span>
        <span> | 学生答案: ${d.user || '未作答'}</span>
        <span> | ${d.user === d.correct ? '✓ 正确' : '✗ 错误'}</span>
      </div>`;
    }
  }

  // 填空题详情
  if (s.fill_details && s.fill_details.length > 0) {
    html += '<p style="font-weight:600;margin-top:8px;color:#6c757d">填空题</p>';
    for (const [di, d] of s.fill_details.entries()) {
      let cls = '';
      if (d.score === 0) cls = 'wrong';
      else if (d.score < d.max) cls = 'partial';
      if (d.review_flag) cls = 'review';
      const statusIcon = d.score >= d.max * 0.8 ? '✓' : (d.score > 0 ? '△' : '✗');

      html += `<div class="detail-item ${cls}" id="fill-item-${di}">
        <span class="q-num">Q${d.id}</span>
        <span>正确答案: ${d.correct}</span>`;

      if (d.review_flag) {
        // 可编辑审阅项
        const ocrVal = escapeAttr(d.ocr_text || '');
        html += `<span> | OCR识别: <input type="text" class="review-input" id="review-ocr-${di}" value="${ocrVal}" style="width:120px;padding:2px 6px;border:1px solid #e2b93b;border-radius:4px;font-size:12px;"></span>
        <span> | 得分: <span id="review-score-${di}">${d.score}/${d.max}</span></span>
        <span> | 相似度: <span id="review-sim-${di}">${d.similarity != null ? (d.similarity * 100).toFixed(0) + '%' : '-'}</span></span>
        <button class="btn btn-sm btn-review" data-di="${di}" data-correct="${escapeAttr(d.correct)}" data-max="${d.max}" data-student-id="${studentId}">🔄 重判</button>
        <span> | <input type="number" id="review-manual-${di}" placeholder="手动分数" min="0" max="${d.max}" step="0.5" style="width:60px;padding:2px 6px;border:1px solid #ccc;border-radius:4px;font-size:12px;">
        <button class="btn btn-sm btn-review-manual" data-di="${di}" data-student-id="${studentId}">✏️ 确认</button></span>
        ${d.ocr_suggestion ? '<span> | 🔍建议: ' + d.ocr_suggestion + '</span>' : ''}`;
      } else {
        html += `<span> | OCR识别: ${d.ocr_text || '未识别'}</span>
        <span> | 相似度: ${d.similarity != null ? (d.similarity * 100).toFixed(0) + '%' : '-'}</span>
        <span> | 得分: ${d.score}/${d.max} ${statusIcon}</span>`;
      }

      // 多空详情
      if (d.blanks && d.blanks.length > 0) {
        html += '<div style="margin-left:24px;font-size:11px;color:#6c757d;margin-top:4px;">';
        for (const [bi, b] of d.blanks.entries()) {
          const bIcon = b.score >= b.max * 0.8 ? '✓' : (b.score > 0 ? '△' : '✗');
          html += `空${bi+1}: OCR="${b.text}" 得分=${b.score}/${b.max} ${bIcon}<br>`;
        }
        html += '</div>';
      }

      html += '</div>';
    }
  }

  if ((!s.choice_details || s.choice_details.length === 0) && (!s.fill_details || s.fill_details.length === 0)) {
    html += '<p style="color:#6c757d">无详细答题记录</p>';
  }

  panel.innerHTML = html;

  // 绑定审阅按钮事件
  panel.querySelectorAll('.btn-review').forEach(btn => {
    btn.addEventListener('click', async () => {
      const di = parseInt(btn.dataset.di);
      const correct = btn.dataset.correct;
      const maxScore = parseFloat(btn.dataset.max);
      const sid = btn.dataset.studentId;
      const ocrInput = $(`#review-ocr-${di}`);
      if (!ocrInput) return;

      const newOcr = ocrInput.value.trim();
      if (!newOcr) return;

      btn.disabled = true;
      btn.textContent = '⏳';
      try {
        const result = await api.rejudge({ ocrText: newOcr, correctAnswer: correct });
        if (result.success && result.data) {
          const { score, similarity } = result.data;
          const newScore = Math.round(maxScore * score * 10) / 10;
          $(`#review-score-${di}`).textContent = `${newScore}/${maxScore}`;
          $(`#review-sim-${di}`).textContent = `${(similarity * 100).toFixed(0)}%`;

          // 更新内存中的结果
          updateResultScore(sid, di, newScore, newOcr, similarity);
        }
      } catch (e) { alert('重判失败: ' + e.message); }
      btn.disabled = false;
      btn.textContent = '🔄 重判';
    });
  });

  // 绑定手动分数按钮
  panel.querySelectorAll('.btn-review-manual').forEach(btn => {
    btn.addEventListener('click', () => {
      const di = parseInt(btn.dataset.di);
      const sid = btn.dataset.studentId;
      const manualInput = $(`#review-manual-${di}`);
      if (!manualInput) return;
      const manualScore = parseFloat(manualInput.value);
      if (isNaN(manualScore)) return;

      $(`#review-score-${di}`).textContent = `${manualScore}/${$( `#review-score-${di}`).textContent.split('/')[1]}`;
      updateResultScore(sid, di, manualScore, null, null);
    });
  });
}

function updateResultScore(studentId, fillIdx, newScore, newOcr, newSimilarity) {
  const s = state.lastResults.results.find(st => st.student_id === studentId);
  if (!s || !s.fill_details || !s.fill_details[fillIdx]) return;

  const fd = s.fill_details[fillIdx];
  const oldScore = fd.score;
  fd.score = newScore;
  fd.review_confirmed = true;
  fd.review_flag = false;
  if (newOcr !== null) fd.ocr_text = newOcr;
  if (newSimilarity !== null) fd.similarity = newSimilarity;

  // 更新总分
  s.fill_score = s.fill_details.reduce((sum, d) => sum + (d.score || 0), 0);
  s.fill_score = Math.round(s.fill_score * 10) / 10;
  s.total_scored = (s.choice_score || 0) + s.fill_score;

  // 刷新显示
  renderResults(state.lastResults);
}

function escapeAttr(str) {
  return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ========== 成绩报告 ==========
async function generateReport() {
  if (!state.lastResults || !state.resultsPath) return alert('请先完成批改');
  setStatus('📄 生成报告中...', 'busy');

  try {
    const reportPath = state.outputDir + '/grade_report.pdf';
    const result = await api.generateReport({
      resultsPath: state.resultsPath,
      configPath: state.configPath,
      outputPath: reportPath,
    });
    if (result.success) {
      setStatus(`✅ 报告已生成: ${reportPath}`, '');
      // 用系统默认程序打开PDF
      try {
        await api.openPath(reportPath);
      } catch(e) { /* ignore */ }
    } else {
      alert('报告生成失败: ' + (result.error || '未知错误'));
      setStatus('⚠️ 报告生成失败', 'error');
    }
  } catch (err) {
    alert('报告生成异常: ' + err.message);
    setStatus('❌ 异常', 'error');
  }
}

// ========== 导入错题本 ==========
async function importToDatabase() {
  if (!state.lastResults || !state.resultsPath) return alert('请先完成批改');
  const dbPath = $('#setDbPath').value || (state.outputDir + '/wrong_book.db');

  setStatus('💾 导入错题本...', 'busy');
  try {
    const result = await api.importToDB({
      resultsPath: state.resultsPath,
      configPath: state.configPath,
      dbPath: dbPath,
    });
    if (result.success) {
      setStatus('✅ 错题已入库', '');
      alert('错题数据已导入数据库');
    } else {
      alert('导入失败: ' + (result.error || '未知错误'));
      setStatus('⚠️ 导入失败', 'error');
    }
  } catch (err) {
    alert('导入异常: ' + err.message);
    setStatus('❌ 异常', 'error');
  }
}

// ========== 导出功能 ==========
async function exportGrades() {
  const dbPath = $('#setDbPath').value;
  if (!dbPath) return alert('请先在设置中配置数据库路径');

  // 默认输出到批改输出目录
  const outputDir = state.outputDir || $('#setOutputDir').value;
  if (!outputDir) return alert('请先设置输出目录');

  const outputPath = outputDir.replace(/\\/g, '/').replace(/\/$/, '') + '/成绩表.csv';

  setStatus('📥 导出成绩...', 'busy');
  try {
    const result = await api.exportGrades({ dbPath, outputPath });
    if (result.success) {
      setStatus('✅ 成绩已导出', '');
      alert('成绩表已导出:\n' + result.path);
    } else {
      alert('导出失败: ' + (result.error || '未知错误'));
      setStatus('⚠️ 导出失败', 'error');
    }
  } catch (err) {
    alert('导出异常: ' + err.message);
    setStatus('❌ 异常', 'error');
  }
}

async function exportWrong() {
  const dbPath = $('#setDbPath').value;
  if (!dbPath) return alert('请先在设置中配置数据库路径');

  const outputDir = state.outputDir || $('#setOutputDir').value;
  if (!outputDir) return alert('请先设置输出目录');

  const outputPath = outputDir.replace(/\\/g, '/').replace(/\/$/, '') + '/错题本.csv';

  setStatus('📥 导出错题...', 'busy');
  try {
    const result = await api.exportWrong({ dbPath, outputPath });
    if (result.success) {
      setStatus('✅ 错题已导出', '');
      alert('错题本已导出:\n' + result.path);
    } else {
      alert('导出失败: ' + (result.error || '未知错误'));
      setStatus('⚠️ 导出失败', 'error');
    }
  } catch (err) {
    alert('导出异常: ' + err.message);
    setStatus('❌ 异常', 'error');
  }
}

// ========== 错题本查询 ==========
async function queryWrongBook() {
  const studentId = $('#wbStudentId').value.trim();
  const kp = $('#wbKnowledgePoint').value.trim();

  if (!studentId && !kp) return alert('请填写学号或知识点至少一项');

  setStatus('🔍 查询错题...', 'busy');
  const tbody = $('#wrongTable tbody');

  try {
    const dbPath = $('#setDbPath').value;
    if (!dbPath) return alert('请先在设置中配置数据库路径');

    const result = await api.queryWrongBook({
      dbPath: dbPath,
      studentId: studentId || undefined,
      kp: kp || undefined,
    });

    if (result.success) {
      // 解析输出（Python脚本 stdout）
      renderWrongResults(result.output, tbody);
      setStatus('✅ 查询完成', '');
    } else {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="7">查询失败: ${result.error || '未知错误'}</td></tr>`;
      setStatus('⚠️ 查询失败', 'error');
    }
  } catch (err) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">异常: ${err.message}</td></tr>`;
    setStatus('❌ 异常', 'error');
  }
}

function renderWrongResults(output, tbody) {
  if (!output || output.trim() === '') {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="7">无错题记录</td></tr>';
    return;
  }

  // 尝试解析 JSON
  try {
    const data = JSON.parse(output);
    if (Array.isArray(data) && data.length > 0) {
      let html = '';
      for (const row of data) {
        html += `<tr>
          <td>${row.student_id || '-'}</td>
          <td>${row.question_id || row.qid || '-'}</td>
          <td>${row.question_content || '-'}</td>
          <td>${row.correct_answer || '-'}</td>
          <td>${row.student_answer || row.user_answer || '-'}</td>
          <td>${row.knowledge_point || '-'}</td>
          <td>${row.score != null ? row.score : (row.score_earned != null ? row.score_earned + '/' + row.max_score : '-')}</td>
        </tr>`;
      }
      tbody.innerHTML = html;
      return;
    }
  } catch (e) {
    // 非JSON，尝试解析文本格式
  }

  // 解析文本格式：[知识点] 题{id} 生答={ans} 正解={correct} 得分={score}/{max} [学号]
  const lines = output.trim().split('\n').filter(l => l.startsWith('['));
  if (lines.length > 0) {
    let html = '';
    for (const line of lines) {
      const m = line.match(/^\[(.+?)\]\s*题(\d+)\s*生答=(.+?)\s*正解=(.+?)\s*得分=([\d.]+)\/([\d.]+)\s*\[(.+?)\]$/);
      if (m) {
        const [, kp, qid, userAns, correctAns, score, max, sid] = m;
        html += `<tr>
          <td>${sid}</td>
          <td>Q${qid}</td>
          <td>-</td>
          <td>${correctAns}</td>
          <td>${userAns}</td>
          <td>${kp}</td>
          <td>${score}/${max}</td>
        </tr>`;
      }
    }
    if (html) {
      tbody.innerHTML = html;
      return;
    }
  }

  // 兜底：显示原始文本
  tbody.innerHTML = `<tr><td colspan="7"><pre style="font-family:monospace;font-size:12px;white-space:pre-wrap;margin:0">${escapeHtml(output)}</pre></td></tr>`;
}

// ========== 设置 ==========
function loadSettings() {
  try {
    const saved = localStorage.getItem('yuejuanSettings');
    if (saved) {
      const settings = JSON.parse(saved);
      if (settings.outputDir) {
        $('#setOutputDir').value = settings.outputDir;
        $('#outputDir').value = settings.outputDir;
        state.outputDir = settings.outputDir;
      }
      if (settings.dbPath) {
        $('#setDbPath').value = settings.dbPath;
      }
    }
    // 加载缓存的姓名
    const cachedNames = localStorage.getItem('yuejuanNames');
    if (cachedNames) {
      state.studentNames = JSON.parse(cachedNames);
    }
  } catch (e) { /* ignore */ }
}

function saveSettings() {
  const settings = {
    outputDir: $('#setOutputDir').value.trim(),
    dbPath: $('#setDbPath').value.trim(),
  };
  localStorage.setItem('yuejuanSettings', JSON.stringify(settings));
  // 同步到批改页
  if (settings.outputDir) {
    $('#outputDir').value = settings.outputDir;
    state.outputDir = settings.outputDir;
  }
  setStatus('✅ 设置已保存', '');
  setTimeout(() => setStatus('🟢 就绪', ''), 2000);
}

// ========== 学生名单 ==========
async function importRoster() {
  const csvPath = $('#rosterPath').value.trim();
  if (!csvPath) return alert('请选择学生名单CSV文件');

  const dbPath = $('#setDbPath').value;
  if (!dbPath) return alert('请先在设置中配置数据库路径');

  setStatus('👥 导入名单中...', 'busy');
  $('#btnImportRoster').disabled = true;
  try {
    const result = await api.importRoster({ dbPath, csvPath });
    if (result.success) {
      $('#rosterStatus').textContent = result.output.trim();
      // 从数据库重新加载姓名缓存
      await refreshNameCache(dbPath);
      setStatus('✅ 名单导入完成', '');
    } else {
      $('#rosterStatus').textContent = '导入失败: ' + (result.error || '未知');
      setStatus('⚠️ 导入失败', 'error');
    }
  } catch (err) {
    $('#rosterStatus').textContent = '异常: ' + err.message;
    setStatus('❌ 异常', 'error');
  } finally {
    $('#btnImportRoster').disabled = false;
  }
}

async function loadStudentNames(data) {
  const dbPath = $('#setDbPath').value;
  if (!dbPath) return;

  // 收集所有学号
  const ids = [...new Set((data.results || []).map(r => r.student_id).filter(Boolean))];
  if (ids.length === 0) return;

  // 先检查缓存
  const names = state.studentNames || {};
  const missing = ids.filter(id => !names[id]);
  if (missing.length === 0) return;

  try {
    const result = await api.batchLookupStudents({ dbPath, studentIds: missing });
    if (result.success && result.data) {
      for (const [id, info] of Object.entries(result.data)) {
        names[id] = info.name || '';
      }
      state.studentNames = names;
      localStorage.setItem('yuejuanNames', JSON.stringify(names));
    }
  } catch (e) {
    // 数据库不可用时静默降级
  }
}

async function refreshNameCache(dbPath) {
  try {
    state.studentNames = {};
    localStorage.removeItem('yuejuanNames');
  } catch (e) { /* ignore */ }
}

// ========== 数据分析 ==========
async function loadExamList() {
  const dbPath = $('#setDbPath').value;
  if (!dbPath) {
    $('#examSelect').innerHTML = '<option value="">请先在设置中配置数据库路径</option>';
    return;
  }
  try {
    const result = await api.listExams({ dbPath });
    const sel = $('#examSelect');
    if (result.success && result.data && result.data.length > 0) {
      sel.innerHTML = result.data.map(e =>
        `<option value="${e.id}">${e.name} (${e.exam_date || '未标注日期'} | ${e.student_count}人 | 均分${e.avg_score})</option>`
      ).join('');
      // 自动加载最新
      loadAnalysis();
    } else {
      sel.innerHTML = '<option value="">暂无考试记录</option>';
    }
  } catch (e) {
    $('#examSelect').innerHTML = '<option value="">加载失败</option>';
  }
}

async function loadAnalysis() {
  const dbPath = $('#setDbPath').value;
  if (!dbPath) return;
  const examId = $('#examSelect').value || undefined;
  
  setStatus('📊 加载分析数据...', 'busy');
  try {
    const result = await api.examStats({ dbPath, examId });
    if (result.success && result.data) {
      renderAnalysis(result.data);
      setStatus('✅ 分析完成', '');
    } else {
      setStatus('⚠️ 无分析数据', 'error');
    }
  } catch (e) {
    setStatus('❌ 加载失败: ' + e.message, 'error');
  }
}

function renderAnalysis(data) {
  // 质量指标
  const q = data.quality;
  $('#qualityCards').style.display = 'block';
  $('#qualityGrid').innerHTML = `
    <div class="quality-item"><div class="q-value">${q.avg_score}</div><div class="q-label">平均分</div></div>
    <div class="quality-item"><div class="q-value">${q.max_score}</div><div class="q-label">最高分</div></div>
    <div class="quality-item"><div class="q-value">${q.min_score}</div><div class="q-label">最低分</div></div>
    <div class="quality-item"><div class="q-value">${q.std_dev}</div><div class="q-label">标准差</div></div>
    <div class="quality-item"><div class="q-value">${q.difficulty}%</div><div class="q-label">难度系数</div></div>
    <div class="quality-item"><div class="q-value">${q.total_students}</div><div class="q-label">参考人数</div></div>
  `;

  // 雷达图
  drawRadar(data.knowledge_points);
  // 柱状图
  drawBar(data.score_distribution);
}

function drawRadar(kpStats) {
  const canvas = $('#radarChart');
  if (!canvas || !kpStats || kpStats.length === 0) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2, r = 150;
  const n = kpStats.length;
  if (n < 3) return; // 至少3个才能画多边形

  ctx.clearRect(0, 0, W, H);

  // 背景网格
  for (let level = 1; level <= 4; level++) {
    ctx.beginPath();
    ctx.strokeStyle = '#e1e4e8';
    ctx.lineWidth = 1;
    for (let i = 0; i < n; i++) {
      const angle = (Math.PI * 2 / n) * i - Math.PI / 2;
      const lr = r * level / 4;
      const x = cx + Math.cos(angle) * lr;
      const y = cy + Math.sin(angle) * lr;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();
  }

  // 轴线
  ctx.strokeStyle = '#dee2e6';
  ctx.lineWidth = 1;
  for (let i = 0; i < n; i++) {
    const angle = (Math.PI * 2 / n) * i - Math.PI / 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(angle) * r, cy + Math.sin(angle) * r);
    ctx.stroke();
  }

  // 数据多边形
  ctx.beginPath();
  ctx.fillStyle = 'rgba(52, 152, 219, 0.2)';
  ctx.strokeStyle = '#3498db';
  ctx.lineWidth = 2;
  for (let i = 0; i < n; i++) {
    const angle = (Math.PI * 2 / n) * i - Math.PI / 2;
    const rate = Math.max(kpStats[i].score_rate, 5) / 100; // 最小5%可见
    const x = cx + Math.cos(angle) * r * rate;
    const y = cy + Math.sin(angle) * r * rate;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  // 标签
  ctx.fillStyle = '#2c3e50';
  ctx.font = '12px "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'center';
  for (let i = 0; i < n; i++) {
    const angle = (Math.PI * 2 / n) * i - Math.PI / 2;
    const lr = r + 28;
    const x = cx + Math.cos(angle) * lr;
    const y = cy + Math.sin(angle) * lr;
    const label = kpStats[i].knowledge_point;
    ctx.fillText(label.length > 5 ? label.slice(0, 5) + '..' : label, x, y);
    // 百分比
    ctx.fillStyle = '#3498db';
    ctx.font = 'bold 10px "Microsoft YaHei", sans-serif';
    const pr = r + 12;
    ctx.fillText(kpStats[i].score_rate + '%', cx + Math.cos(angle) * pr, cy + Math.sin(angle) * pr);
    ctx.fillStyle = '#2c3e50';
    ctx.font = '12px "Microsoft YaHei", sans-serif';
  }
}

function drawBar(distribution) {
  const canvas = $('#barChart');
  if (!canvas || !distribution) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const keys = Object.keys(distribution);
  const values = Object.values(distribution);
  const maxVal = Math.max(...values, 1);
  const barW = 60, gap = 25, startX = 60, bottomY = H - 40;
  const chartH = H - 80;

  // Y轴
  ctx.strokeStyle = '#dee2e6';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(startX - 10, 20);
  ctx.lineTo(startX - 10, bottomY);
  ctx.lineTo(W - 20, bottomY);
  ctx.stroke();

  // Y轴刻度
  ctx.fillStyle = '#6c757d';
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const y = bottomY - chartH * i / 4;
    const val = Math.round(maxVal * i / 4);
    ctx.fillText(val, startX - 14, y + 4);
  }

  // 柱子
  const colors = ['#e74c3c', '#e67e22', '#f39c12', '#2ecc71', '#27ae60'];
  for (let i = 0; i < keys.length; i++) {
    const barH = values[i] / maxVal * chartH;
    const x = startX + i * (barW + gap);
    const y = bottomY - barH;

    ctx.fillStyle = colors[i] || '#3498db';
    ctx.fillRect(x, y, barW, barH);

    // 数值
    ctx.fillStyle = '#2c3e50';
    ctx.font = 'bold 13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(values[i], x + barW / 2, y - 6);

    // 标签
    ctx.fillStyle = '#6c757d';
    ctx.font = '11px sans-serif';
    ctx.fillText(keys[i], x + barW / 2, bottomY + 16);
  }
}

// ========== 工具函数 ==========
function setStatus(text, className) {
  const el = $('#statusText');
  el.textContent = text;
  el.className = 'status-text ' + (className || '');
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
