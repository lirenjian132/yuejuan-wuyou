# 阅卷无忧 (YueJuanWuYou)

自动阅卷系统 — 选择题+填空题全自动批改，零外部依赖，开箱即用。

## 功能

- **答题卡生成** — 生成标准填涂式答题卡（PDF），含学号圈填+选择题+填空区+QR定位
- **选择题判分** — OpenCV 像素统计，准确率 100%（合成测试 30/30）
- **填空题OCR** — RapidOCR (onnxruntime) 轻量中文识别，300DPI + OTSU预处理
- **多空填空** — 支持一题多空（如"大小____、方向____"），按____分割横线，逐空OCR+独立判分
- **语义判分** — jieba分词 + 编辑距离，三道阈值自动判定（满分/半对/零分）
- **混淆词典** — 学科知识点上下文辅助纠错，标记疑似OCR误读供教师确认
- **审阅确认** — Electron界面支持教师修改OCR文本、手动输入分数、一键语义重判
- **流水线** — 一键：生成答题卡 → 模拟填涂 → 扫描判分 → 成绩报告
- **成绩报告** — Markdown + PDF双格式，含考试概况/知识点分析/学生明细/各题得分率/待审阅项
- **错题本** — SQLite存储，按学号/知识点查询，自动入库，支持多空错题明细
- **题库管理** — 考试配置JSON驱动，题目+知识点+答案结构化存储
- **桌面应用** — Electron界面（批改/错题本/分析/设置四页），支持文件选择+进度+结果预览+审阅

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 生成答题卡（示例配置）
python3 generate_sheet.py --config exam_config.json

# 一键批改流水线
python3 run_pipeline.py --config exam_config.json --copies 5 --output-dir ./output
```

## 项目结构

```
├── generate_sheet.py      # 答题卡生成（reportlab + qrcode）
├── scan_and_grade.py      # 判分引擎（OpenCV + RapidOCR + jieba + 多空分割）
├── fill_simulator.py      # 模拟学生填涂（测试用）
├── run_pipeline.py        # 一键流水线
├── report_generator.py    # 成绩报告（Markdown + PDF双格式）
├── database.py            # 错题本 + 题库（SQLite，含批量查询）
├── confusion_dict.py      # 学科混淆词典
├── template_matcher.py    # 模板角标检测+透视矫正
├── export_tool.py         # 成绩/错题CSV导出
├── exam_config.json       # 示例考试配置（含多空填空题）
├── requirements.txt       # Python依赖
└── electron-app/          # 桌面应用（Electron）
```

## 考试配置格式

参见 `exam_config.json`：

```json
{
  "exam_name": "初二物理第三章单元测试",
  "subject": "物理",
  "grade": "初二(3)班",
  "date": "2026-05-12",
  "questions": [
    {
      "id": 1,
      "type": "choice",
      "content": "下列哪个是力的单位？",
      "options": ["A. 千克", "B. 牛顿", "C. 米", "D. 秒"],
      "answer": "B",
      "score": 3,
      "knowledge_point": "力的单位"
    },
    {
      "id": 7,
      "type": "fill",
      "content": "力的国际单位是____，简称____。",
      "answer": ["牛顿", "牛"],
      "score": 4,
      "knowledge_point": "力的单位"
    }
  ]
}
```

多空填空题：`content` 中用 `____` 标记空位，`answer` 为数组对应每个空的标准答案。分数由题目总分按空数均分。

## 判分规则

| 条件 | 结果 |
|------|------|
| 答案完全匹配 | 满分 |
| 语义相似度 > 0.85 | 满分 |
| 语义相似度 0.65-0.85 | 半对 |
| 语义相似度 < 0.65 | 零分 / 标记待审 |

混淆词典触发标记时不影响分数，仅在报告中标注待审供教师确认。教师可在Electron界面中修改OCR文本重新判分或手动输入分数。

## 技术栈

- **OCR**: RapidOCR (onnxruntime, ~88MB)
- **图像**: OpenCV + PyMuPDF (300DPI渲染)
- **语义**: jieba分词 + difflib编辑距离
- **数据库**: SQLite (WAL模式, 外键约束)
- **桌面**: Electron (主进程+IPC+渲染进程，contextIsolation安全隔离)

## 开发阶段

| 阶段 | 状态 | 内容 |
|------|------|------|
| 0 | ✅ | 选择题判分 |
| 1 | ✅ | 填空题OCR + 语义判分 |
| 2 | ✅ | 流水线 + 成绩报告 |
| 3 | ✅ | 错题本 + 题库（SQLite） |
| 4 | ✅ | Electron桌面界面 |
| 4.5 | ✅ | 学科混淆词典 + 审阅标记 |
| 5 | ✅ | 多空填空 + 审阅确认UI + 批量查询优化 + 报告合并 |

## License

MIT
