#!/usr/bin/env python3
"""阅卷无忧 - 综合测试（10份答卷，覆盖所有判分场景）"""
import subprocess, json, os, sys, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="yj_test_")
PASS, FAIL = 0, 0

def run(cmd, label):
    global PASS, FAIL
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE, timeout=300)
    if r.returncode == 0:
        print(f"  ✅ {label}")
        PASS += 1
        return r.stdout
    else:
        print(f"  ❌ {label}\n     {r.stderr[-200:]}")
        FAIL += 1
        return None

# ===== 1. 生成答题卡 =====
print("\n" + "="*60)
print("  阶段1: 生成答题卡 (10份)")
run(f"python3 generate_sheet.py --config exam_config.json --copies 10 --output {TMP}/sheets.pdf", "生成10份答题卡")

# ===== 2. 模拟填涂（手动控制答案，覆盖场景） =====
print("\n" + "="*60)
print("  阶段2: 模拟填涂（10份，7种场景）")

# 填充模拟：复制一份Python脚本，手动设置每份答案
# 场景设计：
#   S1: 全对+全对OCR (20240001)
#   S2: 全对+混淆字 (20240002) — Q9/Q10 OCR混淆
#   S3: 选错2题+填空对 (20240003)
#   S4: 选对+填空数值容差 (20240004) — Q8答9.81
#   S5: 选对+填空半错 (20240005) — Q6答错
#   S6: 选错+填空全错 (20240006)
#   S7: 缺考空白 (20240007)
#   S8: 全对+全对OCR (20240008) — 重复S1验证一致性
#   S9: 选对+填空OCR漏字 (20240009) — Q6答"惯"非"惯性"
#   S10: 混合 (20240010)

scenarios = [
    # (学号, 选择题答案[1-5], 填空答案[6-10])
    ("20240001", ["B","C","B","D","B"], ["惯性","牛顿","9.8","相反","压力"]),
    ("20240002", ["B","C","B","D","B"], ["惯性","牛顿","9.8","相友","压刀"]),  # OCR混淆
    ("20240003", ["B","A","D","D","B"], ["惯性","牛顿","9.8","相反","压力"]),  # Q2错A非C, Q3错D非B
    ("20240004", ["B","C","B","D","B"], ["惯性","牛顿","9.81","相反","压力"]), # 数值容差
    ("20240005", ["B","C","B","D","B"], ["重力","牛顿","9.8","相反","压力"]),  # Q6答错
    ("20240006", ["A","A","A","A","A"], ["重力","重量","10","相同","拉力"]),    # 全错
    ("20240007", ["","","","",""], ["","","","",""]),                          # 缺考
    ("20240008", ["B","C","B","D","B"], ["惯性","牛顿","9.8","相反","压力"]),   # 全对
    ("20240009", ["B","C","B","D","B"], ["惯","牛顿","9.8","相反","压力"]),     # OCR漏字
    ("20240010", ["B","C","B","A","B"], ["惯性","牛","9.81","相友","压刀"]),    # 混合
]

# 用Python脚本手动生成填涂
fill_code = f'''
import subprocess, json, sys, os
sys.path.insert(0, "{BASE}")
from fill_simulator import simulate_fill
import json as _json

config = _json.load(open("exam_config.json"))
scenarios = {json.dumps(scenarios, ensure_ascii=False)}

for sid, choices, fills in scenarios:
    sheet_pdf = f"{TMP}/sheets.pdf"
    out_pdf = f"{TMP}/filled_{{sid}}.pdf"
    # We need to use PyMuPDF directly to control answers
    import fitz
    doc = fitz.open(sheet_pdf)
    page = doc[0]
    
    # Get page dimensions
    pw = page.rect.width
    ph = page.rect.height
    
    # Convert to points
    pw_pt = pw
    ph_pt = ph
    
    # Fill choices (circles at known positions from generate_sheet.py)
    # Choice block starts at y=260pt, each question 4 options, 7pt circles
    # Layout from generate_sheet.py: CHOICE_X=72, CHOICE_Y_START=260, CHOICE_ROW_H=28, CHOICE_COL_W=36
    choice_x = 72
    choice_y_start = 260
    choice_row_h = 28
    choice_col_w = 36
    
    for qi, ans in enumerate(choices):
        if not ans:
            continue
        opt_idx = ord(ans) - ord('A')
        cx = choice_x + opt_idx * choice_col_w
        cy = choice_y_start + qi * choice_row_h
        
        # Draw filled circle (black)
        from fitz import Point
        # Fill the circle area
        page.draw_circle(Point(cx, cy), 7, color=(0,0,0), fill=(0,0,0), width=0)
    
    # Fill student ID
    sid_x_start = 72
    sid_y = 180
    sid_col_w = 36
    for di, digit in enumerate(sid):
        if digit == '0':
            continue
        val = int(digit)
        cx_sid = sid_x_start + (di * 10 + val) * sid_col_w / 10
        # Simplified: just fill the correct circle
        page.draw_circle(Point(cx_sid, sid_y), 4, color=(0,0,0), fill=(0,0,0), width=0)
    
    # Fill blanks (text insertion)
    # Blank positions same as fill_simulator: FILL_Y_START=470, FILL_ROW_H=36
    fill_y_start = 470
    fill_row_h = 36
    fill_x = 72
    
    for fi, text in enumerate(fills):
        if not text:
            continue
        fy = fill_y_start + fi * fill_row_h
        try:
            page.insert_text(Point(fill_x, fy), text, fontname="china-s", fontsize=20, color=(0,0,0.3))
        except:
            pass
    
    doc.save(out_pdf, incremental=False, deflate=True)
    doc.close()

print("DONE")
'''

# Write and run the fill script
fill_path = os.path.join(TMP, "fill_controlled.py")
with open(fill_path, "w") as f:
    f.write(fill_code)

out = run(f"python3 {fill_path}", "生成10份受控答卷")
if out:
    # Merge into single PDF
    pdfs = " ".join([f"{TMP}/filled_{s[0]}.pdf" for s in scenarios])
    run(f"python3 -c \"import fitz; d=fitz.open(); [d.insert_pdf(fitz.open('{TMP}/filled_{s[0]}.pdf')) for s in {scenarios}]; d.save('{TMP}/all_filled.pdf')\"",
        "合并10份答卷")

# ===== 3. 判分 =====
print("\n" + "="*60)
print("  阶段3: 扫描判分")
out = run(f"python3 scan_and_grade.py --config exam_config.json --scan {TMP}/all_filled.pdf --output {TMP}/results.json",
          "判分10份答卷")
results = None
if out:
    with open(f"{TMP}/results.json") as f:
        data = json.load(f)
        results = data.get("results", [])

# ===== 4. 逐份验证 =====
print("\n" + "="*60)
print("  阶段4: 逐份验证判分正确性")

expected = [
    # (sid, choice_score/15, fill_score/20, total/35, 期望场景)
    ("20240001", 15, 20, 35, "S1: 全对"),
    ("20240002", 15, 12, 27, "S2: 混淆字→Q9/Q10零分"),
    ("20240003", 9, 20, 29, "S3: Q2错A非C,Q3错D非B"),
    ("20240004", 15, 19.4, 34.4, "S4: Q8数值容差9.81→3.4分"),
    ("20240005", 15, 16, 31, "S5: Q6答错'重力'→0分"),
    ("20240006", 0, 0, 0, "S6: 全错"),
    ("20240007", None, None, None, "S7: 缺考(可能0分或异常)"),
    ("20240008", 15, 20, 35, "S8: 全对"),
    ("20240009", 15, 16, 31, "S9: Q6漏字'惯'→可能半对或零分"),
    ("20240010", 12, 7.4, 19.4, "S10: 混合"),
]

for i, (sid, exp_c, exp_f, exp_t, desc) in enumerate(expected):
    r = results[i] if results and i < len(results) else {}
    actual_c = r.get("choice_score", -1)
    actual_f = r.get("fill_score", -1)
    actual_t = r.get("total_scored", -1)
    
    c_ok = exp_c is None or abs(actual_c - exp_c) < 0.5
    f_ok = exp_f is None or abs(actual_f - exp_f) < 1.0  # 填空浮点容差1分
    t_ok = exp_t is None or abs(actual_t - exp_t) < 1.0
    
    status = "✅" if (c_ok and f_ok and t_ok) else "❌"
    print(f"  {status} {desc} | 选择={actual_c}(期{exp_c}) 填空={actual_f}(期{exp_f}) 总分={actual_t}(期{exp_t})")

# ===== 5. 混淆词典验证 =====
print("\n" + "="*60)
print("  阶段5: 验证混淆词典审阅标记")
review_count = 0
for r in (results or []):
    for fd in r.get("fill_details", []):
        if fd.get("review_flag"):
            review_count += 1
            print(f"  🔍 {r['student_id']} Q{fd['id']}: OCR='{fd['ocr_text']}' → 建议='{fd.get('ocr_suggestion','')}'")
            
if review_count >= 4:  # S2有2个 + S10有2个
    print(f"  ✅ 审阅标记数={review_count} (期望>=4)")
    PASS += 1
else:
    print(f"  ❌ 审阅标记数={review_count} (期望>=4)")
    FAIL += 1

# ===== 6. 报告生成 =====
print("\n" + "="*60)
print("  阶段6: 成绩报告")
out = run(f"python3 report_generator.py --results {TMP}/results.json --config exam_config.json --output {TMP}/report.md",
          "生成成绩报告")
if out:
    # 检查报告是否包含审阅章节
    with open(f"{TMP}/report.md") as f:
        report = f.read()
    if "待教师审阅" in report and "🔍" in report:
        print(f"  ✅ 报告包含审阅章节")
        PASS += 1
    else:
        print(f"  ❌ 报告缺少审阅章节")
        FAIL += 1

# ===== 7. 数据库 =====
print("\n" + "="*60)
print("  阶段7: 数据库错题入库+查询")
out = run(f"python3 database.py --db {TMP}/yuejuan.db import-results --results {TMP}/results.json --config exam_config.json",
          "错题入库")
if out:
    out2 = run(f"python3 database.py --db {TMP}/yuejuan.db query-wrong --student 20240006 --limit 10",
               "查询全错学生错题")
    if out2 and "共 " in out2:
        print(f"  ✅ 数据库查询正常")
        PASS += 1
    else:
        FAIL += 1

# ===== 汇总 =====
print("\n" + "="*60)
total = PASS + FAIL
print(f"  测试结果: {PASS}/{total} 通过, {FAIL} 失败")
if FAIL == 0:
    print(f"  🎉 全部通过！")
else:
    print(f"  ⚠️ 有 {FAIL} 项失败，需排查")
print(f"  临时文件: {TMP}")
print(f"  判分结果: {TMP}/results.json")
print(f"  成绩报告: {TMP}/report.md")
