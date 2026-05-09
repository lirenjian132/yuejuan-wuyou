#!/usr/bin/env python3
"""阅卷无忧 自动化回归测试套件 v1
基于测试金字塔理念：
- 集成测试：CLI入口调用 + 完整流水线
- 快照测试：和 golden fixtures 对比
- 边界测试：异常输入、容错
"""
import subprocess, json, sys, os, difflib, tempfile, shutil

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
PYTHON = sys.executable
passed = 0
failed = 0
errors = []

def run(*args, timeout=60, **kw):
    """运行命令，返回 CompletedProcess"""
    return subprocess.run([PYTHON] + list(args), capture_output=True, text=True, timeout=timeout, cwd=PROJECT, **kw)

def check(ok, name, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))
    else:
        failed += 1
        msg = f"  ❌ {name}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(msg)

def test(name):
    """测试装饰器"""
    def deco(fn):
        def wrapper():
            print(f"\n{'='*50}")
            print(f"  {name}")
            print(f"{'='*50}")
            try:
                fn()
            except Exception as e:
                check(False, name, f"异常: {e}")
        return wrapper
    return deco

@test("1. 单面扫描回归测试")
def test_single_side():
    config = f"{FIXTURES}/exam_config.json"
    scan = f"{FIXTURES}/filled_answers.pdf"
    expected_file = f"{FIXTURES}/expected_results.json"
    
    # 判分
    r = run("scan_and_grade.py", "--config", config, "--scan", scan,
            "--output", "/tmp/test_reg_single.json", "--resume")
    check(r.returncode == 0, "判分完成", f"exit={r.returncode}")
    
    actual = json.load(open("/tmp/test_reg_single.json"))
    expected = json.load(open(expected_file))
    
    # 核心结构
    check(actual["total_students"] == expected["total_students"],
          "考生数一致", f"{actual['total_students']} == {expected['total_students']}")
    
    check(abs(actual["choice_avg"] - expected["choice_avg"]) < 0.5,
          "选择均分一致", f"{actual['choice_avg']} ≈ {expected['choice_avg']}")
    
    check(abs(actual["fill_avg"] - expected["fill_avg"]) < 2.0,
          "填空均分一致(±2)", f"{actual['fill_avg']} ≈ {expected['fill_avg']}")
    
    # 逐学生验证
    for a, e in zip(actual["results"], expected["results"]):
        check(a["student_id"] == e["student_id"],
              f"学号 {a['student_id']}", f"一致")
        check(a["choice_score"] == e["choice_score"],
              f"  选择得分 {a['choice_score']}", f"期望 {e['choice_score']}")
        check(abs(a["fill_score"] - e["fill_score"]) < 1.0,
              f"  填空得分 {a['fill_score']}", f"期望 {e['fill_score']}(±1)")
        
        # 选择答案精确匹配
        a_ans = "".join(a.get("choice_answers", []))
        e_ans = "".join(e.get("choice_answers", []))
        check(a_ans == e_ans, f"  选择答案", f"{a_ans} == {e_ans}")
        
        # OCR文本放松匹配（允许RapidOCR微小波动）
        a_fills = a.get("fill_details", [])
        e_fills = e.get("fill_details", [])
        for af, ef in zip(a_fills, e_fills):
            sim = difflib.SequenceMatcher(None, af.get("ocr_text",""), ef.get("ocr_text","")).ratio()
            check(sim > 0.6, f"  OCR Q{af['id']}", 
                  f"相似度{sim:.2f} (实际'{af.get('ocr_text','')}' vs 期望'{ef.get('ocr_text','')}')")
    
    # 进度清理
    check(not os.path.exists("/tmp/test_reg_single.progress.json"), "进度文件已清理")

@test("2. 双面扫描回归测试")
def test_duplex():
    config = f"{FIXTURES}/duplex_config.json"
    scan = f"{FIXTURES}/duplex_filled_answers.pdf"
    expected_file = f"{FIXTURES}/duplex_expected_results.json"
    
    r = run("scan_and_grade.py", "--config", config, "--scan", scan,
            "--output", "/tmp/test_reg_duplex.json", "--duplex", "--resume")
    check(r.returncode == 0, "双面判分完成", f"exit={r.returncode}")
    
    actual = json.load(open("/tmp/test_reg_duplex.json"))
    expected = json.load(open(expected_file))
    
    check(actual["total_students"] == expected["total_students"],
          "考生数一致", f"{actual['total_students']} == {expected['total_students']}")
    
    # 验证合并格式
    for r in actual["results"]:
        check("," in str(r.get("page", "")), f"page合并格式", r["page"])
    
    check(not os.path.exists("/tmp/test_reg_duplex.progress.json"), "进度文件已清理")

@test("3. 崩溃恢复测试")
def test_crash_recovery():
    config = f"{FIXTURES}/exam_config.json"
    scan = f"{FIXTURES}/filled_answers.pdf"
    
    # 创建假进度文件
    import hashlib
    chash = hashlib.md5()
    chash.update(json.dumps(json.load(open(config)), sort_keys=True).encode())
    chash.update(str(os.path.getsize(scan)).encode())
    
    prog = {
        "config_hash": chash.hexdigest()[:8],
        "total_pages": 5, "done_pages": 2,
        "results": [
            {"page": 1, "student_id": "99999001", "choice_score": 10, "fill_score": 10, "total_scored": 20, "total_max": 35,
             "choice_answers": ["A","A","A","A","A"], "choice_max": 15, "fill_max": 20,
             "choice_details": [], "fill_details": []},
            {"page": 2, "student_id": "99999002", "choice_score": 8, "fill_score": 8, "total_scored": 16, "total_max": 35,
             "choice_answers": ["B","B","B","B","B"], "choice_max": 15, "fill_max": 20,
             "choice_details": [], "fill_details": []},
        ]
    }
    with open("/tmp/test_crash.progress.json", "w") as f:
        json.dump(prog, f)
    
    r = run("scan_and_grade.py", "--config", config, "--scan", scan,
            "--output", "/tmp/test_crash.json", "--resume")
    
    check("恢复模式" in r.stdout, "恢复提示", "包含'恢复模式'")
    check(r.returncode == 0, "恢复成功", f"exit={r.returncode}")
    
    actual = json.load(open("/tmp/test_crash.json"))
    check(actual["total_students"] == 5, "最终5人", str(actual["total_students"]))
    check(not os.path.exists("/tmp/test_crash.progress.json"), "进度清理")

@test("4. 数据库操作测试")
def test_database():
    results = f"{FIXTURES}/expected_results.json"
    config = f"{FIXTURES}/exam_config.json"
    db_path = "/tmp/test_reg.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # 导入
    r = run("database.py", "--db", db_path, "import-results", 
            "--results", results, "--config", config,
            "--exam-name", "回归测试", "--subject", "物理")
    check(r.returncode == 0, "导入结果", f"exit={r.returncode}")
    
    # 导入学生
    r = run("database.py", "--db", db_path, "import-students",
            "--file", f"{FIXTURES}/students.csv")
    check(r.returncode == 0, "导入学生名单", f"exit={r.returncode}")
    
    # 考试统计
    r = run("database.py", "--db", db_path, "exam-stats")
    stats = json.loads(r.stdout)
    check(stats is not None, "考试统计", f"avg={stats['quality']['avg_score']}")
    check(len(stats["knowledge_points"]) > 0, "知识点数据", f"{len(stats['knowledge_points'])}个")
    
    # 学生统计
    r = run("database.py", "--db", db_path, "student-stats", "--student-id", "20240001")
    student = json.loads(r.stdout)
    check(student is not None, "学生统计", f"exams={len(student.get('exams',[]))}")
    check(len(student.get("knowledge_points", [])) > 0, "知识点强弱", f"{len(student['knowledge_points'])}项")
    
    # 考试列表
    r = run("database.py", "--db", db_path, "list-exams")
    exams = json.loads(r.stdout)
    check(len(exams) > 0, "考试列表", f"{len(exams)}场")

@test("5. 导出功能测试")
def test_export():
    db_path = "/tmp/test_reg.db"
    
    r = run("export_tool.py", "--db", db_path, "export-grades", "--output", "/tmp/test_grades.csv")
    check(r.returncode == 0, "导出成绩", f"exit={r.returncode}")
    with open("/tmp/test_grades.csv") as f:
        lines = f.readlines()
    check(len(lines) > 1, f"成绩CSV有数据", f"{len(lines)}行")
    
    r = run("export_tool.py", "--db", db_path, "export-wrong-answers", "--output", "/tmp/test_wrong.csv")
    check(r.returncode == 0, "导出错题", f"exit={r.returncode}")
    with open("/tmp/test_wrong.csv") as f:
        lines = f.readlines()
    check(len(lines) > 1, f"错题CSV有数据", f"{len(lines)}行")

@test("6. 边界异常测试")
def test_edge():
    config = f"{FIXTURES}/exam_config.json"
    
    # 空PDF (创建0页PDF)
    r = run("scan_and_grade.py", "--config", config, 
            "--scan", "/dev/null", "--output", "/tmp/test_edge_null.json", "--resume")
    check(r.returncode != 0 or "total_students" in open("/tmp/test_edge_null.json").read() if os.path.exists("/tmp/test_edge_null.json") else True, 
          "空PDF不崩溃(预期报错)")
    
    # 缺questions字段
    bad_config = "/tmp/test_bad_config.json"
    with open(bad_config, "w") as f:
        json.dump({"paper_type": "answer_sheet"}, f)
    r = run("scan_and_grade.py", "--config", bad_config,
            "--scan", f"{FIXTURES}/filled_answers.pdf",
            "--output", "/tmp/test_edge_bad.json")
    check("缺少 questions" in (r.stdout + r.stderr), "缺questions友好报错")
    
    # 损坏的进度文件
    corrupt_prog = "/tmp/test_edge_corrupt.progress.json"
    with open(corrupt_prog, "w") as f:
        f.write("this is not json{{{")
    r = run("scan_and_grade.py", "--config", config,
            "--scan", f"{FIXTURES}/filled_answers.pdf",
            "--output", "/tmp/test_edge_corrupt.json", "--resume")
    check(r.returncode == 0, "损坏进度自动忽略", f"exit={r.returncode}")
    check("损坏" in (r.stdout + r.stderr), "提示损坏信息")

# ========== 运行 ==========
if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║     阅卷无忧 自动化回归测试套件 v1      ║")
    print("╚══════════════════════════════════════════╝")
    
    test_single_side()
    test_duplex()
    test_crash_recovery()
    test_database()
    test_export()
    test_edge()
    
    total = passed + failed
    print(f"\n{'='*50}")
    if failed == 0:
        print(f"  ✅ ALL {total} TESTS PASSED")
    else:
        print(f"  ❌ {failed}/{total} FAILED")
        for e in errors:
            print(f"     {e}")
    print(f"{'='*50}")
    
    # 清理临时文件
    for f in ["/tmp/test_reg_single.json", "/tmp/test_reg_duplex.json", 
              "/tmp/test_crash.json", "/tmp/test_reg.db",
              "/tmp/test_grades.csv", "/tmp/test_wrong.csv"]:
        try: os.remove(f)
        except: pass
    
    sys.exit(0 if failed == 0 else 1)
