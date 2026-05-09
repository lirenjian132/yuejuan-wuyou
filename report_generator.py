#!/usr/bin/env python3
"""阅卷无忧 - 成绩报告生成器（支持 Markdown + PDF 双格式）"""
import json, argparse, os
from collections import defaultdict


def analyze_knowledge_points(results, config):
    q_info = {}
    for q in config["questions"]:
        ans = q.get("answer", "")
        if isinstance(ans, list):
            ans = " | ".join(str(a) for a in ans)
        q_info[q["id"]] = {
            "kp": q["knowledge_point"], "type": q["type"],
            "score": q["score"], "correct_answer": str(ans),
        }
    kp_stats = defaultdict(lambda: {"total": 0, "correct": 0, "max_score": 0, "earned_score": 0})
    for r in results:
        for cd in r.get("choice_details", []):
            kp = cd.get("kp", q_info.get(cd["id"], {}).get("kp", "未知"))
            kp_stats[kp]["total"] += 1
            kp_stats[kp]["max_score"] += cd.get("max", 0)
            kp_stats[kp]["earned_score"] += cd.get("score", 0)
            if cd.get("user") == cd.get("correct"):
                kp_stats[kp]["correct"] += 1
        for fd in r.get("fill_details", []):
            kp = fd.get("kp", q_info.get(fd["id"], {}).get("kp", "未知"))
            kp_stats[kp]["total"] += 1
            kp_stats[kp]["max_score"] += fd.get("max", 0)
            kp_stats[kp]["earned_score"] += fd.get("score", 0)
            if fd.get("score", 0) >= fd.get("max", 0) * 0.8:
                kp_stats[kp]["correct"] += 1
            for blank in fd.get("blanks", []):
                kp_stats[kp]["total"] += 1
                kp_stats[kp]["max_score"] += blank.get("max", 0)
                kp_stats[kp]["earned_score"] += blank.get("score", 0)
                if blank.get("score", 0) >= blank.get("max", 0) * 0.8:
                    kp_stats[kp]["correct"] += 1
    return kp_stats


def compute_exam_quality(results, config):
    if not results:
        return {}
    total_max = results[0].get("total_max", 0)
    scores = [r.get("total_scored", 0) for r in results]
    choice_scores = [r.get("choice_score", 0) for r in results]
    fill_scores = [r.get("fill_score", 0) for r in results]
    avg = sum(scores) / len(scores)
    std = (sum((s - avg) ** 2 for s in scores) / len(scores)) ** 0.5
    max_s = max(scores) if scores else 0
    min_s = min(scores) if scores else 0
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    if n >= 4:
        discrimination = sum(sorted_scores[n//2:]) / (n - n//2) - sum(sorted_scores[:n//2]) / (n//2)
    else:
        discrimination = 0
    difficulty = 1.0 - avg / total_max if total_max > 0 else 0
    return {
        "total_max": total_max, "avg": round(avg, 1), "std": round(std, 1),
        "max_score": max_s, "min_score": min_s, "range": max_s - min_s,
        "difficulty": round(difficulty, 3), "discrimination": round(discrimination, 1),
        "choice_avg": round(sum(choice_scores) / len(choice_scores), 1) if choice_scores else 0,
        "fill_avg": round(sum(fill_scores) / len(fill_scores), 1) if fill_scores else 0,
    }


def generate_markdown(results, config, quality, kp_stats, output_path):
    lines = []
    lines.append(f"# {config['exam_name']} — 成绩报告")
    lines.append(f"")
    lines.append(f"**科目**: {config['subject']} | **班级**: {config['grade']} | **日期**: {config['date']}")
    lines.append(f"**考生总数**: {len(results)} | **满分**: {config['questions'] and results and results[0].get('total_max', 0)}")
    lines.append(f"")

    lines.append(f"## 一、考试概况")
    lines.append(f"")
    if quality:
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 平均分 | {quality['avg']}/{quality['total_max']} |")
        lines.append(f"| 标准差 | {quality['std']} |")
        lines.append(f"| 最高分 | {quality['max_score']} |")
        lines.append(f"| 最低分 | {quality['min_score']} |")
        diff_label = '偏难' if quality['difficulty'] > 0.6 else ('适中' if quality['difficulty'] > 0.3 else '偏易')
        lines.append(f"| 难度系数 | {quality['difficulty']:.2f} ({diff_label}) |")
        disc_label = '良好' if quality['discrimination'] > quality['total_max'] * 0.25 else '一般'
        lines.append(f"| 区分度 | {quality['discrimination']:.1f} ({disc_label}) |")
        lines.append(f"| 选择题均分 | {quality['choice_avg']} |")
        lines.append(f"| 填空题均分 | {quality['fill_avg']} |")
    lines.append(f"")

    lines.append(f"## 二、知识点掌握情况")
    lines.append(f"")
    if kp_stats:
        lines.append(f"| 知识点 | 题数 | 正确率 | 得分率 | 掌握程度 |")
        lines.append(f"|--------|------|--------|--------|----------|")
        for kp, stats in sorted(kp_stats.items(), key=lambda x: x[1]["earned_score"] / (x[1]["max_score"] or 1)):
            correct_rate = stats["correct"] / stats["total"] * 100 if stats["total"] else 0
            score_rate = stats["earned_score"] / stats["max_score"] * 100 if stats["max_score"] else 0
            level = "良好" if score_rate >= 80 else ("一般" if score_rate >= 60 else "薄弱")
            lines.append(f"| {kp} | {stats['total']} | {correct_rate:.0f}% | {score_rate:.0f}% | {level} |")

        weak = [(kp, s) for kp, s in kp_stats.items()
                if s["max_score"] > 0 and s["earned_score"] / s["max_score"] < 0.6]
        if weak:
            lines.append(f"")
            lines.append(f"### 需重点复习的知识点")
            for kp, s in weak:
                score_rate = s["earned_score"] / s["max_score"] * 100
                lines.append(f"- **{kp}**: 得分率 {score_rate:.0f}%（{s['earned_score']}/{s['max_score']}）")
    lines.append(f"")

    lines.append(f"## 三、学生成绩明细")
    lines.append(f"")
    lines.append(f"| 序号 | 学号 | 选择 | 填空 | 总分 |")
    lines.append(f"|------|------|------|------|------|")
    sorted_results = sorted(results, key=lambda x: x.get("total_scored", 0), reverse=True)
    for rank, r in enumerate(sorted_results, 1):
        cs = r.get("choice_score", 0)
        fs = r.get("fill_score", 0)
        ts = r.get("total_scored", 0)
        sid = r.get("student_id", "???")
        lines.append(f"| {rank} | {sid} | {cs} | {fs} | {ts} |")
    lines.append(f"")

    lines.append(f"## 四、各题得分率")
    lines.append(f"")
    q_scores = defaultdict(lambda: {"earned": 0, "max": 0, "count": 0})
    for r in results:
        for cd in r.get("choice_details", []):
            q_scores[cd["id"]]["earned"] += cd.get("score", 0)
            q_scores[cd["id"]]["max"] += cd.get("max", 0)
            q_scores[cd["id"]]["count"] += 1
        for fd in r.get("fill_details", []):
            q_scores[fd["id"]]["earned"] += fd.get("score", 0)
            q_scores[fd["id"]]["max"] += fd.get("max", 0)
            q_scores[fd["id"]]["count"] += 1
    for q in config["questions"]:
        qid = q["id"]
        qs = q_scores.get(qid, {"earned": 0, "max": q["score"], "count": 0})
        rate = qs["earned"] / qs["max"] * 100 if qs["max"] else 0
        bar = "█" * int(rate / 5) + "░" * (20 - int(rate / 5))
        qtype = "选择" if q["type"] == "choice" else "填空"
        lines.append(f"- Q{qid} [{qtype}] {q['knowledge_point']}: {bar} {rate:.0f}% ({qs['earned']}/{qs['max']})")
    lines.append(f"")

    # 待审阅项目
    review_items = []
    for r in results:
        for fd in r.get("fill_details", []):
            if fd.get("review_flag") and not fd.get("review_confirmed"):
                review_items.append({
                    "student": r.get("student_id", "?"),
                    "qid": fd["id"], "ocr": fd.get("ocr_text", ""),
                    "correct": fd.get("correct", ""),
                    "suggestion": fd.get("ocr_suggestion", ""),
                })
    if review_items:
        lines.append(f"## 五、待教师审阅（OCR疑似误读）")
        lines.append(f"")
        lines.append(f"| 学号 | 题号 | OCR识读 | 标准答案 | 系统建议 |")
        lines.append(f"|------|------|---------|----------|----------|")
        for item in review_items:
            sug = item["suggestion"] if item["suggestion"] else "—"
            lines.append(f"| {item['student']} | Q{item['qid']} | {item['ocr']} | {item['correct']} | {sug} |")
        lines.append(f"")

    # 教学建议
    lines.append(f"## 六、教学建议")
    lines.append(f"")
    if quality:
        if quality["difficulty"] > 0.6:
            lines.append(f"- 试卷整体偏难，建议后续适当降低难度或增加基础题比例")
        elif quality["difficulty"] < 0.3:
            lines.append(f"- 试卷偏易，可适当增加挑战性题目")
        else:
            lines.append(f"- 试卷难度适中")
        if quality["discrimination"] < quality["total_max"] * 0.2:
            lines.append(f"- 区分度偏低，建议增加分层题目以更好区分不同水平学生")
    if kp_stats:
        weak_kps = [(kp, s) for kp, s in kp_stats.items()
                    if s["max_score"] > 0 and s["earned_score"] / s["max_score"] < 0.6]
        if weak_kps:
            lines.append(f"- 重点关注以下薄弱知识点：{', '.join(kp for kp, _ in weak_kps)}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*报告由阅卷无忧自动生成*")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Markdown报告已生成: {output_path} ({len(content)}字)")


def generate_pdf(results, config, kp_stats, output_path):
    """生成精美PDF报告 (HTML+WeasyPrint)"""
    total_max = results[0].get("total_max", 35) if results else 35
    scores = [r.get("total_scored", 0) for r in results]
    avg = sum(scores) / len(scores) if scores else 0
    max_s = max(scores) if scores else 0
    min_s = min(scores) if scores else 0
    pass_count = sum(1 for s in scores if s >= total_max * 0.6)

    dist = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "<60": 0}
    for s in scores:
        pct = s / total_max * 100
        if pct >= 90: dist["90-100"] += 1
        elif pct >= 80: dist["80-89"] += 1
        elif pct >= 70: dist["70-79"] += 1
        elif pct >= 60: dist["60-69"] += 1
        else: dist["<60"] += 1

    colors = ["#ef4444", "#f97316", "#eab308", "#22c55e"]
    kp_rows = ""
    for kp, stats in sorted(kp_stats.items(), key=lambda x: x[1]["earned_score"] / (x[1]["max_score"] or 1)):
        score_rate = stats["earned_score"] / stats["max_score"] * 100 if stats["max_score"] else 0
        correct_rate = stats["correct"] / stats["total"] * 100 if stats["total"] else 0
        level_idx = min(3, max(0, int((100 - score_rate) / 25)))
        color = colors[level_idx]
        level_text = ["优秀", "良好", "一般", "薄弱"][level_idx]
        kp_rows += f"""
        <tr>
            <td>{kp}</td><td>{stats['total']}</td><td>{correct_rate:.0f}%</td><td>{score_rate:.0f}%</td>
            <td><div class="bar-wrap"><div class="bar-fill" style="width:{score_rate:.0f}%;background:{color}"></div></div></td>
            <td><span class="badge" style="background:{color}">{level_text}</span></td>
        </tr>"""

    student_rows = ""
    sorted_results = sorted(results, key=lambda x: x.get("total_scored", 0), reverse=True)
    for rank, r in enumerate(sorted_results, 1):
        ts = r.get("total_scored", 0)
        pct = ts / total_max * 100
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else str(rank)
        color = "#22c55e" if pct >= 80 else "#eab308" if pct >= 60 else "#ef4444"
        student_rows += f"""
        <tr>
            <td>{medal}</td><td>{r.get('student_id', '?')}</td>
            <td>{r.get('choice_score', 0)}</td><td>{r.get('fill_score', 0)}</td>
            <td><strong style="color:{color}">{ts}</strong></td><td>{pct:.0f}%</td>
        </tr>"""

    q_scores = defaultdict(lambda: {"earned": 0, "max": 0})
    for r in results:
        for cd in r.get("choice_details", []):
            q_scores[cd["id"]]["earned"] += cd.get("score", 0)
            q_scores[cd["id"]]["max"] += cd.get("max", 0)
        for fd in r.get("fill_details", []):
            q_scores[fd["id"]]["earned"] += fd.get("score", 0)
            q_scores[fd["id"]]["max"] += fd.get("max", 0)

    q_rows = ""
    for q in config["questions"]:
        qid = q["id"]
        qs = q_scores.get(qid, {"earned": 0, "max": q["score"] * len(results)})
        rate = qs["earned"] / qs["max"] * 100 if qs["max"] else 0
        qtype = "选择" if q["type"] == "choice" else "填空"
        color = "#22c55e" if rate >= 80 else "#eab308" if rate >= 60 else "#ef4444"
        q_rows += f"""
        <tr>
            <td>Q{qid}</td><td>{qtype}</td><td>{q['knowledge_point']}</td>
            <td><div class="bar-wrap"><div class="bar-fill" style="width:{rate:.0f}%;background:{color}"></div></div></td>
            <td><strong style="color:{color}">{rate:.0f}%</strong></td>
        </tr>"""

    weak = [(kp, s) for kp, s in kp_stats.items()
            if s["max_score"] > 0 and s["earned_score"] / s["max_score"] < 0.6]
    weak_html = ""
    if weak:
        weak_html = '<div class="alert"><strong>需重点复习：</strong>'
        weak_html += "、".join(kp for kp, _ in weak) + "</div>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 18mm 16mm 22mm 16mm;
    @bottom-center {{ content: "— " counter(page) " —"; font-size: 9pt; color: #94a3b8; font-family: 'Hei', sans-serif; }}
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Hei', 'WenQuanYi Zen Hei', 'Noto Sans CJK SC', sans-serif; color: #1e293b; font-size: 11pt; line-height: 1.6; }}
  .cover {{ background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #3b82f6 100%); color: white; padding: 32px 36px; border-radius: 12px; margin-bottom: 28px; position: relative; overflow: hidden; }}
  .cover::after {{ content: ""; position: absolute; top: -40px; right: -40px; width: 160px; height: 160px; background: rgba(255,255,255,0.06); border-radius: 50%; }}
  .cover h1 {{ font-size: 26pt; font-weight: 700; margin-bottom: 6px; letter-spacing: 2px; }}
  .cover .subtitle {{ font-size: 11pt; opacity: 0.85; }}
  .cover .meta {{ display: flex; gap: 32px; margin-top: 14px; font-size: 10pt; opacity: 0.8; }}
  .cards {{ display: flex; gap: 14px; margin-bottom: 28px; }}
  .card {{ flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 18px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
  .card .label {{ font-size: 9pt; color: #64748b; margin-bottom: 4px; }}
  .card .value {{ font-size: 22pt; font-weight: 700; color: #1e3a5f; }}
  .card .unit {{ font-size: 10pt; color: #94a3b8; }}
  .section {{ margin-bottom: 26px; }}
  .section h2 {{ font-size: 15pt; color: #1e3a5f; border-left: 4px solid #2563eb; padding-left: 12px; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
  th {{ background: #f1f5f9; color: #475569; font-weight: 600; padding: 9px 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 9.5pt; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }}
  tr:nth-child(even) td {{ background: #f8fafc; }}
  .bar-wrap {{ background: #f1f5f9; border-radius: 4px; height: 8px; width: 100%; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; color: white; font-size: 9pt; font-weight: 600; }}
  .distro {{ display: flex; align-items: flex-end; gap: 10px; height: 140px; padding: 0 8px; }}
  .bar-col {{ flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }}
  .bar-col .bar {{ width: 100%; max-width: 48px; border-radius: 6px 6px 0 0; min-height: 4px; }}
  .bar-col .count {{ font-size: 10pt; font-weight: 700; color: #1e3a5f; }}
  .bar-col .range {{ font-size: 8pt; color: #94a3b8; }}
  .alert {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 12px 16px; font-size: 10pt; color: #92400e; margin-top: 12px; }}
  .suggestions {{ background: #f0f9ff; border-radius: 8px; padding: 16px 20px; border: 1px solid #bae6fd; }}
  .suggestions li {{ margin-bottom: 6px; font-size: 10pt; color: #0c4a6e; }}
  .footer {{ margin-top: 24px; padding-top: 12px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 8.5pt; color: #94a3b8; }}
</style>
</head>
<body>
<div class="cover">
  <h1>{config['exam_name']}</h1>
  <div class="subtitle">成绩分析报告</div>
  <div class="meta">
    <span>{config.get('subject', '')}</span>
    <span>{config.get('grade', '')}</span>
    <span>{config.get('date', '')}</span>
    <span>{len(results)} 人</span>
    <span>满分 {total_max}</span>
  </div>
</div>

<div class="cards">
  <div class="card"><div class="label">平均分</div><div class="value">{avg:.1f}</div><div class="unit">/ {total_max}</div></div>
  <div class="card"><div class="label">最高分</div><div class="value">{max_s}</div></div>
  <div class="card"><div class="label">最低分</div><div class="value">{min_s}</div></div>
  <div class="card"><div class="label">及格率</div><div class="value">{pass_count/len(results)*100:.0f}%</div><div class="unit">{pass_count}/{len(results)} 人</div></div>
  <div class="card"><div class="label">标准差</div><div class="value">{(sum((s-avg)**2 for s in scores)/len(scores))**0.5:.1f}</div></div>
</div>

<div class="section"><h2>分数分布</h2>
  <div class="distro">
    {''.join(f'''
    <div class="bar-col">
      <div class="count">{v}</div>
      <div class="bar" style="height:{v/max(dist.values())*120 if max(dist.values()) else 0}px;background:{c}"></div>
      <div class="range">{k}</div>
    </div>''' for k, v, c in [
      ("90-100", dist["90-100"], "#22c55e"), ("80-89", dist["80-89"], "#3b82f6"),
      ("70-79", dist["70-79"], "#eab308"), ("60-69", dist["60-69"], "#f97316"),
      ("<60", dist["<60"], "#ef4444"),
    ])}
  </div>
</div>

<div class="section"><h2>学生成绩排名</h2>
  <table>
    <thead><tr><th>排名</th><th>学号</th><th>选择题</th><th>填空题</th><th>总分</th><th>得分率</th></tr></thead>
    <tbody>{student_rows}</tbody>
  </table>
</div>

<div class="section"><h2>知识点掌握情况</h2>
  <table>
    <thead><tr><th>知识点</th><th>题数</th><th>正确率</th><th>得分率</th><th style="width:30%">掌握度</th><th>评级</th></tr></thead>
    <tbody>{kp_rows}</tbody>
  </table>
  {weak_html}
</div>

<div class="section"><h2>各题得分率</h2>
  <table>
    <thead><tr><th>题号</th><th>类型</th><th>知识点</th><th style="width:30%">得分率</th><th>数值</th></tr></thead>
    <tbody>{q_rows}</tbody>
  </table>
</div>

<div class="section"><h2>教学建议</h2>
  <div class="suggestions">
    <ul>
      <li>试卷整体难度{'偏难' if avg/total_max < 0.5 else '偏易' if avg/total_max > 0.8 else '适中'}（均分 {avg:.1f}/{total_max}，得分率 {avg/total_max*100:.0f}%）</li>
      {''.join(f'<li><b>{kp}</b> 得分率仅 {s["earned_score"]/s["max_score"]*100:.0f}%，需重点强化</li>' for kp, s in weak)}
      <li>及格率 {pass_count/len(results)*100:.0f}%，{'整体表现良好，继续保持' if pass_count/len(results) >= 0.8 else '需关注不及格学生，建议个别辅导'}</li>
    </ul>
  </div>
</div>

<div class="footer">本报告由阅卷无忧自动生成 · {config.get('date', '')}</div>
</body>
</html>"""

    html_path = output_path.replace(".pdf", ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    import fontTools.ttLib.tables.O_S_2f_2 as os2_module
    _original_set = os2_module.table_O_S_2f_2.setUnicodeRanges
    def _patched_set(self, bits):
        bits = [b for b in bits if 0 <= b <= 122]
        _original_set(self, bits)
    os2_module.table_O_S_2f_2.setUnicodeRanges = _patched_set

    font_config = FontConfiguration()
    HTML(string=html).write_pdf(output_path, font_config=font_config, optimize_size=())
    print(f"PDF报告已生成: {output_path}")
    print(f"   HTML源文件: {html_path}")


def main():
    p = argparse.ArgumentParser(description="阅卷无忧 - 成绩报告生成器")
    p.add_argument("--results", required=True, help="判分结果JSON")
    p.add_argument("--config", required=True, help="考试配置JSON")
    p.add_argument("--output", default="grade_report.md", help="输出文件路径")
    p.add_argument("--format", choices=["md", "pdf"], default="md", help="输出格式 (md=Markdown, pdf=PDF)")
    args = p.parse_args()

    with open(args.results, encoding="utf-8") as f:
        data = json.load(f)
    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    results = data.get("results", [])
    kp_stats = analyze_knowledge_points(results, config)
    quality = compute_exam_quality(results, config)

    if args.format == "pdf":
        generate_pdf(results, config, kp_stats, args.output)
    else:
        generate_markdown(results, config, quality, kp_stats, args.output)

    # 打印摘要
    print(f"\n成绩摘要:")
    print(f"  平均分: {quality.get('avg', 'N/A')}/{quality.get('total_max', 'N/A')}")
    print(f"  最高/最低: {quality.get('max_score', 'N/A')}/{quality.get('min_score', 'N/A')}")
    if kp_stats:
        weak = [(kp, s) for kp, s in kp_stats.items()
                if s["max_score"] > 0 and s["earned_score"] / s["max_score"] < 0.6]
        if weak:
            print(f"  薄弱知识点: {', '.join(kp for kp, _ in weak)}")


if __name__ == "__main__":
    main()
