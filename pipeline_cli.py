#!/usr/bin/env python3
"""阅卷无忧 - 统一命令行入口（供 Electron 调用，PyInstaller 编译为 pipeline.exe）"""
import argparse, json, sys, os

# 确保脚本所在目录在 sys.path 中，PyInstaller 打包后也能正确导入
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


def cmd_scan_and_grade(args):
    """扫描判分"""
    from scan_and_grade import run as _run
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    _run(args.scan, cfg, args.output, resume=args.resume, duplex=args.duplex, template=args.template)


def cmd_report(args):
    """生成成绩报告"""
    from report_generator import generate_markdown, generate_pdf, analyze_knowledge_points, compute_exam_quality

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

    print(f"\n成绩摘要:")
    print(f"  平均分: {quality.get('avg', 'N/A')}/{quality.get('total_max', 'N/A')}")
    print(f"  最高/最低: {quality.get('max_score', 'N/A')}/{quality.get('min_score', 'N/A')}")
    if kp_stats:
        weak = [(kp, s) for kp, s in kp_stats.items()
                if s["max_score"] > 0 and s["earned_score"] / s["max_score"] < 0.6]
        if weak:
            print(f"  薄弱知识点: {', '.join(kp for kp, _ in weak)}")


def cmd_db(args):
    """数据库操作"""
    from database import Database
    db = Database(args.db)

    if args.db_cmd == "import-results":
        with open(args.config, encoding="utf-8") as f:
            config = json.load(f)
        with open(args.results, encoding="utf-8") as f:
            data = json.load(f)
        results = data if isinstance(data, list) else data.get("results", [])
        exam_id = db.save_exam_results(
            args.exam_name or config.get("exam_name", "未命名考试"),
            args.subject or config.get("subject", ""),
            args.class_name or config.get("class_name", ""),
            args.exam_date or config.get("exam_date", ""),
            config, results
        )
        wrong_count = db.query_wrong_answers(limit=99999)
        print(f"考试ID={exam_id} | 参考人数={len(results)} | 错题数={len(wrong_count)}")

    elif args.db_cmd == "query-wrong":
        rows = db.query_wrong_answers(
            student_id=args.student or None,
            knowledge_point=args.kp or None,
            limit=args.limit
        )
        for r in rows:
            print(f"[{r['knowledge_point']}] 题{r['qid']} 生答={r['user_answer']} 正解={r['correct_answer']} 得分={r['score_earned']}/{r['max_score']} [{r['student_id']}]")
        print(f"\n共 {len(rows)} 条")

    elif args.db_cmd == "wrong-stats":
        stats = db.wrong_answer_stats(args.student or None)
        for s in stats:
            print(f"{s['knowledge_point']}: {s['cnt']}次 总得分{s['earned']}/{s['max_s']}")
        print(f"\n共 {len(stats)} 个知识点有错题")

    elif args.db_cmd == "import-students":
        import csv
        count = 0
        with open(args.file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = [h.strip() for h in (reader.fieldnames or [])]
            id_col = next((h for h in headers if h in ("学号", "id", "student_id", "ID", "编号")), None)
            name_col = next((h for h in headers if h in ("姓名", "name", "学生姓名", "名字")), None)
            class_col = next((h for h in headers if h in ("班级", "class", "class_name", "班")), None)
            if not id_col:
                id_col = headers[0]
            if not name_col and len(headers) > 1:
                name_col = headers[1]
            for row in reader:
                sid = (row.get(id_col) or "").strip()
                name = ((row.get(name_col) or "").strip() if name_col else "")
                cls = ((row.get(class_col) or "").strip() if class_col else "") or args.class_name
                if sid:
                    db.ensure_student(sid, name, cls)
                    count += 1
        print(f"已导入 {count} 名学生")

    elif args.db_cmd == "query-student":
        s = db.get_student(args.id)
        if s:
            print(json.dumps(s, ensure_ascii=False))
        else:
            print("null")

    elif args.db_cmd == "exam-stats":
        stats = db.get_exam_stats(args.exam_id if args.exam_id else None)
        if stats:
            print(json.dumps(stats, ensure_ascii=False))
        else:
            print("null")

    elif args.db_cmd == "list-exams":
        exams = db.get_exam_list()
        print(json.dumps(exams, ensure_ascii=False))

    elif args.db_cmd == "compare-exams":
        ids = [int(x.strip()) for x in args.ids.split(",")]
        stats = db.compare_exams(ids)
        print(json.dumps(stats, ensure_ascii=False))

    elif args.db_cmd == "student-stats":
        stats = db.get_student_stats(args.student_id)
        if stats:
            print(json.dumps(stats, ensure_ascii=False))
        else:
            print("null")

    elif args.db_cmd == "batch-students":
        ids = [x.strip() for x in args.ids.split(",")]
        result = db.batch_get_students(ids)
        print(json.dumps(result, ensure_ascii=False))


def cmd_export(args):
    """导出工具"""
    from export_tool import export_grades, export_wrong_answers

    if args.export_cmd == "export-grades":
        export_grades(args.db, args.output, args.exam_id)
    elif args.export_cmd == "export-wrong-answers":
        export_wrong_answers(args.db, args.output, args.exam_id)


def cmd_pipeline(args):
    """一键批改流水线（直接调用，无subprocess）"""
    import json as _json

    config_path = os.path.abspath(args.config) if not os.path.isabs(args.config) else args.config
    out_dir = os.path.abspath(args.output_dir) if not os.path.isabs(args.output_dir) else args.output_dir
    sheet_path = os.path.join(out_dir, "answer_sheets.pdf")
    filled_path = os.path.join(out_dir, "filled_answers.pdf")
    result_path = os.path.join(out_dir, "grade_results.json")
    report_path = os.path.join(out_dir, "grade_report.md")

    def banner(msg):
        print(f"\n{'='*50}\n  {msg}\n{'='*50}")

    # 步骤1：生成答题卡
    if not args.skip_generate:
        banner("步骤1/5: 生成答题卡")
        from generate_sheet import generate as gen_sheets
        with open(config_path, encoding="utf-8") as f:
            cfg = _json.load(f)
        gen_sheets(cfg, sheet_path, args.copies)
    else:
        print("\n跳过答题卡生成")
        if not os.path.exists(sheet_path):
            print(f"需要已有答题卡: {sheet_path}")
            sys.exit(1)

    # 步骤2：模拟填涂
    if not args.skip_fill:
        banner("步骤2/5: 模拟学生填涂")
        from fill_simulator import sim as sim_fill
        sim_fill(cfg, sheet_path, filled_path, args.seed)
    else:
        print("\n跳过模拟填涂")
        if not os.path.exists(filled_path):
            print(f"需要已有答卷: {filled_path}")
            sys.exit(1)

    # 步骤3：扫描判分
    banner("步骤3/5: 扫描判分")
    with open(config_path, encoding="utf-8") as f:
        cfg = _json.load(f)
    from scan_and_grade import run as scan_run
    scan_run(filled_path, cfg, result_path, resume=True, duplex=False, template=False)

    # 步骤4：生成报告
    if not args.skip_report:
        banner("步骤4/5: 生成成绩报告")
        from report_generator import generate_markdown, analyze_knowledge_points, compute_exam_quality
        with open(result_path, encoding="utf-8") as f:
            data = _json.load(f)
        results = data.get("results", [])
        kp_stats = analyze_knowledge_points(results, cfg)
        quality = compute_exam_quality(results, cfg)
        generate_markdown(results, cfg, quality, kp_stats, report_path)
    else:
        print("\n跳过报告生成")

    # 步骤5：错题入库
    banner("步骤5/5: 错题入库")
    db_path = os.path.join(out_dir, "yuejuan.db")
    from database import Database
    db = Database(db_path)
    with open(result_path, encoding="utf-8") as f:
        data = _json.load(f)
    results = data if isinstance(data, list) else data.get("results", [])
    exam_id = db.save_exam_results(
        cfg.get("exam_name", "未命名考试"),
        cfg.get("subject", ""),
        cfg.get("class_name", ""),
        cfg.get("exam_date", ""),
        cfg, results
    )
    wrong_count = db.query_wrong_answers(limit=99999)
    print(f"考试ID={exam_id} | 参考人数={len(results)} | 错题数={len(wrong_count)}")

    print(f"\n{'='*50}")
    print(f"  流水线完成！")
    print(f"{'='*50}")
    print(f"  答题卡:     {sheet_path}")
    print(f"  答卷:       {filled_path}")
    print(f"  判分结果:   {result_path}")
    if not args.skip_report:
        print(f"  成绩报告:   {report_path}")


def cmd_rejudge(args):
    """语义重判（教师修改OCR文本后重新计算相似度）"""
    from difflib import SequenceMatcher

    ocr_text = args.ocr_text
    correct_answer = args.correct_answer

    if not ocr_text or not correct_answer:
        print(json.dumps({"score": 0, "similarity": 0, "confidence": 0}))
        return

    if ocr_text.strip() == correct_answer.strip():
        print(json.dumps({"score": 1.0, "similarity": 1.0, "confidence": 1.0}))
        return

    try:
        import jieba
        ocr_words = set(jieba.cut(ocr_text))
        ans_words = set(jieba.cut(correct_answer))
        jaccard = len(ocr_words & ans_words) / len(ans_words) if ans_words else 0
    except Exception:
        jaccard = 0

    edit_sim = SequenceMatcher(None, ocr_text, correct_answer).ratio()
    combined = 0.4 * jaccard + 0.6 * edit_sim
    conf = max(jaccard, edit_sim)

    if combined > 0.85:
        score = 1.0
    elif combined > 0.65:
        score = 0.5
    else:
        score = 0.0

    print(json.dumps({"score": score, "similarity": round(combined, 3), "confidence": round(conf, 3)}))


def main():
    ap = argparse.ArgumentParser(description="阅卷无忧 - 统一命令行入口")
    sub = ap.add_subparsers(dest="command")

    # scan-and-grade
    p_scan = sub.add_parser("scan-and-grade", help="扫描判分")
    p_scan.add_argument("--config", required=True, help="考试配置JSON")
    p_scan.add_argument("--scan", required=True, help="扫描PDF路径")
    p_scan.add_argument("--output", default="results.json", help="输出JSON路径")
    p_scan.add_argument("--resume", action="store_true", help="从中断处恢复")
    p_scan.add_argument("--duplex", action="store_true", help="双面扫描模式")
    p_scan.add_argument("--template", action="store_true", help="模板模式(角标检测+透视矫正)")

    # report
    p_rep = sub.add_parser("report", help="生成成绩报告")
    p_rep.add_argument("--results", required=True, help="判分结果JSON")
    p_rep.add_argument("--config", required=True, help="考试配置JSON")
    p_rep.add_argument("--output", default="grade_report.md", help="输出文件路径")
    p_rep.add_argument("--format", choices=["md", "pdf"], default="md", help="输出格式")

    # db
    p_db = sub.add_parser("db", help="数据库操作")
    p_db.add_argument("--db", default="yuejuan.db", help="数据库路径")
    db_sub = p_db.add_subparsers(dest="db_cmd")

    p_import = db_sub.add_parser("import-results", help="导入考试结果")
    p_import.add_argument("--results", required=True)
    p_import.add_argument("--config", required=True)
    p_import.add_argument("--exam-name", default="")
    p_import.add_argument("--subject", default="")
    p_import.add_argument("--class-name", default="")
    p_import.add_argument("--exam-date", default="")

    p_qw = db_sub.add_parser("query-wrong", help="错题查询")
    p_qw.add_argument("--student", default="")
    p_qw.add_argument("--kp", default="")
    p_qw.add_argument("--limit", type=int, default=50)

    p_ws = db_sub.add_parser("wrong-stats", help="错题统计")
    p_ws.add_argument("--student", default="")

    p_is = db_sub.add_parser("import-students", help="导入学生名单")
    p_is.add_argument("--file", required=True)
    p_is.add_argument("--class-name", default="")

    p_qs = db_sub.add_parser("query-student", help="查询学生")
    p_qs.add_argument("--id", required=True)

    p_es = db_sub.add_parser("exam-stats", help="考试统计")
    p_es.add_argument("--exam-id", type=int, default=0)

    db_sub.add_parser("list-exams", help="考试列表")

    p_ce = db_sub.add_parser("compare-exams", help="多考试对比")
    p_ce.add_argument("--ids", required=True)

    p_ss = db_sub.add_parser("student-stats", help="学生个人统计")
    p_ss.add_argument("--student-id", required=True)

    p_bs = db_sub.add_parser("batch-students", help="批量查询学生")
    p_bs.add_argument("--ids", required=True)

    # export
    p_exp = sub.add_parser("export", help="导出工具")
    p_exp.add_argument("--db", required=True, help="数据库路径")
    exp_sub = p_exp.add_subparsers(dest="export_cmd")

    p_eg = exp_sub.add_parser("export-grades", help="导出成绩CSV")
    p_eg.add_argument("--output", required=True)
    p_eg.add_argument("--exam-id", type=int, default=None)

    p_ew = exp_sub.add_parser("export-wrong-answers", help="导出错题CSV")
    p_ew.add_argument("--output", required=True)
    p_ew.add_argument("--exam-id", type=int, default=None)

    # pipeline
    p_pl = sub.add_parser("pipeline", help="一键批改流水线")
    p_pl.add_argument("--config", required=True)
    p_pl.add_argument("--copies", type=int, default=5)
    p_pl.add_argument("--seed", type=int, default=42)
    p_pl.add_argument("--output-dir", default=".")
    p_pl.add_argument("--skip-generate", action="store_true")
    p_pl.add_argument("--skip-fill", action="store_true")
    p_pl.add_argument("--skip-report", action="store_true")

    # rejudge (从 Electron 审阅UI 调用)
    p_rj = sub.add_parser("rejudge", help="语义重判")
    p_rj.add_argument("--ocr-text", required=True, help="OCR识别文本")
    p_rj.add_argument("--correct-answer", required=True, help="正确答案")

    args = ap.parse_args()

    if args.command == "scan-and-grade":
        cmd_scan_and_grade(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "db":
        cmd_db(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "pipeline":
        cmd_pipeline(args)
    elif args.command == "rejudge":
        cmd_rejudge(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
