#!/usr/bin/env python3
"""阅卷无忧 - 数据库模块（SQLite）
表结构：
  students        - 学生信息
  exams           - 考试记录
  exam_results    - 单次考试结果
  question_bank   - 题库
  wrong_answers   - 错题本
"""

import sqlite3, json, os, datetime
from contextlib import contextmanager


class Database:
    def __init__(self, db_path="yuejuan.db"):
        self.db_path = db_path
        self._init_tables()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS students (
                    id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    class_name TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS exams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT DEFAULT '',
                    class_name TEXT DEFAULT '',
                    exam_date TEXT DEFAULT '',
                    total_score REAL DEFAULT 0,
                    avg_score REAL DEFAULT 0,
                    student_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS exam_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    choice_score REAL DEFAULT 0,
                    fill_score REAL DEFAULT 0,
                    total_score REAL DEFAULT 0,
                    max_score REAL DEFAULT 0,
                    details_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (exam_id) REFERENCES exams(id),
                    FOREIGN KEY (student_id) REFERENCES students(id)
                );

                CREATE TABLE IF NOT EXISTS question_bank (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qid INTEGER DEFAULT 0,
                    exam_id INTEGER,
                    type TEXT DEFAULT 'choice',
                    content TEXT DEFAULT '',
                    options TEXT DEFAULT '',
                    answer TEXT DEFAULT '',
                    score REAL DEFAULT 0,
                    knowledge_point TEXT DEFAULT '',
                    difficulty TEXT DEFAULT 'medium',
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (exam_id) REFERENCES exams(id)
                );

                CREATE TABLE IF NOT EXISTS wrong_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_result_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    qid INTEGER DEFAULT 0,
                    question_type TEXT DEFAULT '',
                    user_answer TEXT DEFAULT '',
                    correct_answer TEXT DEFAULT '',
                    knowledge_point TEXT DEFAULT '',
                    score_earned REAL DEFAULT 0,
                    max_score REAL DEFAULT 0,
                    exam_date TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (exam_result_id) REFERENCES exam_results(id)
                );

                CREATE INDEX IF NOT EXISTS idx_wrong_student ON wrong_answers(student_id);
                CREATE INDEX IF NOT EXISTS idx_wrong_kp ON wrong_answers(knowledge_point);
                CREATE INDEX IF NOT EXISTS idx_results_exam ON exam_results(exam_id);
                CREATE INDEX IF NOT EXISTS idx_results_student ON exam_results(student_id);
            """)

    # ---------- 学生 ----------
    def ensure_student(self, student_id, name="", class_name=""):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO students (id, name, class_name) VALUES (?, ?, ?)",
                (student_id, name, class_name)
            )
            if name or class_name:
                conn.execute(
                    "UPDATE students SET name=?, class_name=? WHERE id=? AND (name='' OR class_name='')",
                    (name, class_name, student_id)
                )

    def batch_get_students(self, student_ids):
        """批量查询学生信息，返回 {id: {name, class_name}, ...}"""
        result = {}
        if not student_ids:
            return result
        with self._conn() as conn:
            placeholders = ",".join("?" for _ in student_ids)
            rows = conn.execute(
                f"SELECT id, name, class_name FROM students WHERE id IN ({placeholders})",
                student_ids
            ).fetchall()
            for row in rows:
                result[row["id"]] = {"name": row["name"], "class_name": row["class_name"]}
        return result
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
            return dict(row) if row else None

    # ---------- 考试 ----------
    def create_exam(self, name, subject="", class_name="", exam_date="", total_score=0):
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO exams (name, subject, class_name, exam_date, total_score) VALUES (?,?,?,?,?)",
                (name, subject, class_name, exam_date, total_score)
            )
            return cur.lastrowid

    def update_exam_stats(self, exam_id, avg_score, student_count):
        with self._conn() as conn:
            conn.execute(
                "UPDATE exams SET avg_score=?, student_count=? WHERE id=?",
                (avg_score, student_count, exam_id)
            )

    # ---------- 考试结果 ----------
    def save_result(self, exam_id, student_id, choice_score, fill_score, total_score, max_score, details_json):
        self.ensure_student(student_id)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO exam_results (exam_id, student_id, choice_score, fill_score, total_score, max_score, details_json) VALUES (?,?,?,?,?,?,?)",
                (exam_id, student_id, choice_score, fill_score, total_score, max_score, details_json)
            )
            return cur.lastrowid

    # ---------- 题库 ----------
    def add_question(self, qid, exam_id, qtype, content, options, answer, score, kp, difficulty="medium"):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO question_bank (qid, exam_id, type, content, options, answer, score, knowledge_point, difficulty) VALUES (?,?,?,?,?,?,?,?,?)",
                (qid, exam_id, qtype, content, options, answer, score, kp, difficulty)
            )

    def import_questions_from_config(self, exam_id, config):
        """从考试配置JSON批量导入题库"""
        for q in config.get("questions", []):
            opts = json.dumps(q.get("options", []), ensure_ascii=False) if q["type"] == "choice" else ""
            answer = q.get("answer", "")
            if isinstance(answer, list):
                answer = " | ".join(str(a) for a in answer)
            self.add_question(
                qid=q["id"],
                exam_id=exam_id,
                qtype=q["type"],
                content=q.get("content", ""),
                options=opts,
                answer=str(answer),
                score=q.get("score", 0),
                kp=q.get("knowledge_point", ""),
            )

    # ---------- 错题本 ----------
    def add_wrong_answer(self, exam_result_id, student_id, qid, qtype, user_answer, correct_answer, kp, score_earned, max_score, exam_date=""):
        """添加错题（仅当答案错误时调用）"""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO wrong_answers (exam_result_id, student_id, qid, question_type, user_answer, correct_answer, knowledge_point, score_earned, max_score, exam_date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (exam_result_id, student_id, qid, qtype, user_answer, correct_answer, kp, score_earned, max_score, exam_date)
            )

    def query_wrong_answers(self, student_id=None, knowledge_point=None, limit=50):
        """查询错题"""
        with self._conn() as conn:
            conds = []
            params = []
            if student_id:
                conds.append("student_id=?")
                params.append(student_id)
            if knowledge_point:
                conds.append("knowledge_point=?")
                params.append(knowledge_point)
            where = "WHERE " + " AND ".join(conds) if conds else ""
            rows = conn.execute(
                f"SELECT * FROM wrong_answers {where} ORDER BY created_at DESC LIMIT ?",
                params + [limit]
            ).fetchall()
            return [dict(r) for r in rows]

    def wrong_answer_stats(self, student_id=None):
        """错题统计：按知识点汇总"""
        with self._conn() as conn:
            cond = "WHERE student_id=?" if student_id else ""
            params = [student_id] if student_id else []
            rows = conn.execute(
                f"SELECT knowledge_point, COUNT(*) as cnt, SUM(score_earned) as earned, SUM(max_score) as max_s FROM wrong_answers {cond} GROUP BY knowledge_point ORDER BY cnt DESC",
                params
            ).fetchall()
            return [dict(r) for r in rows]

    # ---------- 批量导入（流水线集成） ----------
    def save_exam_results(self, exam_name, subject, class_name, exam_date, config, results):
        """一键保存整场考试：创建考试→保存结果→录入错题→导入题库"""
        total_score = sum(q["score"] for q in config.get("questions", []))

        # 1. 创建考试
        exam_id = self.create_exam(exam_name, subject, class_name, exam_date, total_score)

        # 2. 导入题库
        self.import_questions_from_config(exam_id, config)

        # 3. 逐份保存结果和错题
        for r in results:
            sid = r.get("student_id", "unknown")
            self.ensure_student(sid, class_name=class_name)
            details = {
                "choice_details": r.get("choice_details", []),
                "fill_details": r.get("fill_details", []),
            }
            rid = self.save_result(
                exam_id, sid,
                r.get("choice_score", 0), r.get("fill_score", 0),
                r.get("total_scored", 0), r.get("total_max", total_score),
                json.dumps(details, ensure_ascii=False)
            )

            # 错题入库
            for cd in r.get("choice_details", []):
                if cd.get("user") != cd.get("correct"):
                    self.add_wrong_answer(rid, sid, cd["id"], "choice",
                        cd.get("user", "?"), cd.get("correct", ""),
                        cd.get("kp", ""), cd.get("score", 0), cd.get("max", 0), exam_date)
            for fd in r.get("fill_details", []):
                if fd.get("score", 0) < fd.get("max", 0) * 0.8:
                    correct = fd.get("correct", "")
                    ocr_text = fd.get("ocr_text", "?")
                    # 多空题：附加每空详情
                    if fd.get("blanks"):
                        blank_details = " | ".join(
                            f"空{bi+1}: OCR={b['text']} 得分={b['score']}/{b['max']}"
                            for bi, b in enumerate(fd["blanks"])
                            if b["score"] < b["max"] * 0.8
                        )
                        if blank_details:
                            ocr_text = blank_details
                    self.add_wrong_answer(rid, sid, fd["id"], "fill",
                        ocr_text, correct,
                        fd.get("kp", ""), fd.get("score", 0), fd.get("max", 0), exam_date)

        # 4. 更新考试统计
        avg = sum(r.get("total_scored", 0) for r in results) / len(results) if results else 0
        self.update_exam_stats(exam_id, round(avg, 1), len(results))

        return exam_id

    def get_student_stats(self, student_id):
        """返回某个学生的个人统计分析数据，JSON可序列化"""
        if not student_id:
            return None
        with self._conn() as conn:
            # 检查学生是否存在
            student = conn.execute(
                "SELECT * FROM students WHERE id=?", (student_id,)
            ).fetchone()
            if not student:
                return None

            # 1. 历次考试成绩列表（含排名百分比）
            exam_rows = conn.execute("""
                SELECT er.exam_id, er.total_score, er.max_score, er.choice_score, er.fill_score,
                       e.name as exam_name, e.exam_date
                FROM exam_results er
                JOIN exams e ON er.exam_id = e.id
                WHERE er.student_id = ?
                ORDER BY e.id
            """, (student_id,)).fetchall()

            if not exam_rows:
                return None

            exam_list = []
            score_trend = []
            for row in exam_rows:
                # 计算该学生在本次考试中的排名
                rank_row = conn.execute(
                    "SELECT COUNT(*) + 1 as rank FROM exam_results WHERE exam_id=? AND total_score > ?",
                    (row["exam_id"], row["total_score"])
                ).fetchone()
                total_students = conn.execute(
                    "SELECT COUNT(*) as cnt FROM exam_results WHERE exam_id=?",
                    (row["exam_id"],)
                ).fetchone()["cnt"]
                rank = rank_row["rank"] if rank_row else 1
                rank_pct = round(rank / total_students * 100, 1) if total_students > 0 else 0

                exam_list.append({
                    "exam_id": row["exam_id"],
                    "exam_name": row["exam_name"],
                    "score": row["total_score"],
                    "total": row["max_score"],
                    "rank_percent": rank_pct,
                })
                score_trend.append({
                    "exam_id": row["exam_id"],
                    "exam_name": row["exam_name"],
                    "score": row["total_score"],
                })

            # 收集该生参加过的所有考试ID
            student_exam_ids = [e["exam_id"] for e in exam_list]

            # 2. 知识点强弱分析（含全班平均对比）
            # 先取该生各知识点得分
            kp_rows = conn.execute("""
                SELECT qb.knowledge_point,
                       SUM(COALESCE(wa.score_earned, qb.score)) as earned,
                       SUM(qb.score) as total
                FROM exam_results er
                JOIN question_bank qb ON qb.exam_id = er.exam_id
                LEFT JOIN wrong_answers wa
                    ON wa.exam_result_id = er.id AND wa.qid = qb.qid
                WHERE er.student_id = ?
                GROUP BY qb.knowledge_point
            """, (student_id,)).fetchall()

            # 全班平均（仅限该生参加过的考试）
            placeholders = ",".join("?" for _ in student_exam_ids)
            class_avg_rows = []
            if student_exam_ids:
                class_avg_rows = conn.execute(f"""
                    SELECT qb.knowledge_point,
                           CAST(SUM(COALESCE(wa.score_earned, qb.score)) AS REAL)
                           / NULLIF(SUM(qb.score), 0) * 100 as class_avg
                    FROM exam_results er
                    JOIN question_bank qb ON qb.exam_id = er.exam_id
                    LEFT JOIN wrong_answers wa
                        ON wa.exam_result_id = er.id AND wa.qid = qb.qid
                    WHERE er.exam_id IN ({placeholders})
                    GROUP BY qb.knowledge_point
                """, student_exam_ids).fetchall()

            class_avg_map = {
                row["knowledge_point"]: round(row["class_avg"], 1)
                for row in class_avg_rows
            }

            knowledge_points = []
            for row in kp_rows:
                accuracy = round(row["earned"] / row["total"] * 100, 1) if row["total"] > 0 else 0
                class_avg = class_avg_map.get(row["knowledge_point"], 0)

                # 强弱等级判定
                if accuracy >= class_avg + 10:
                    strength = "strong"
                elif accuracy <= class_avg - 10:
                    strength = "weak"
                else:
                    strength = "moderate"

                knowledge_points.append({
                    "knowledge_point": row["knowledge_point"],
                    "accuracy": accuracy,
                    "class_avg": class_avg,
                    "strength_level": strength,
                })

            # 3. 各题型正确率
            type_rows = conn.execute("""
                SELECT qb.type,
                       SUM(COALESCE(wa.score_earned, qb.score)) as earned,
                       SUM(qb.score) as total
                FROM exam_results er
                JOIN question_bank qb ON qb.exam_id = er.exam_id
                LEFT JOIN wrong_answers wa
                    ON wa.exam_result_id = er.id AND wa.qid = qb.qid
                WHERE er.student_id = ?
                GROUP BY qb.type
            """, (student_id,)).fetchall()

            type_accuracy = {}
            for row in type_rows:
                acc = round(row["earned"] / row["total"] * 100, 1) if row["total"] > 0 else 0
                type_accuracy[row["type"]] = acc

            return {
                "student_id": student_id,
                "student_name": student["name"] or "",
                "exams": exam_list,
                "knowledge_points": knowledge_points,
                "choice_accuracy": type_accuracy.get("choice", 0),
                "fill_accuracy": type_accuracy.get("fill", 0),
                "score_trend": score_trend,
            }

    def get_exam_list(self):
        """获取所有考试列表"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, name, subject, class_name, exam_date, total_score, avg_score, student_count FROM exams ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def compare_exams(self, exam_ids):
        """多考试对比：返回各考试的核心指标"""
        result = []
        for eid in exam_ids:
            stats = self.get_exam_stats(eid)
            if stats:
                result.append(stats)
        return result

    def get_exam_stats(self, exam_id=None):
        with self._conn() as conn:
            # 如果没有指定exam_id，取最新的
            if exam_id is None:
                row = conn.execute("SELECT id FROM exams ORDER BY id DESC LIMIT 1").fetchone()
                if not row:
                    return None
                exam_id = row["id"]

            exam = conn.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
            if not exam:
                return None

            # 知识点统计
            kp_sql = """
                SELECT knowledge_point, COUNT(*) as total, 
                       SUM(CASE WHEN w.score_earned >= w.max_score * 0.8 THEN 1 ELSE 0 END) as correct,
                       SUM(w.score_earned) as earned, SUM(w.max_score) as max_s
                FROM wrong_answers w
                JOIN exam_results r ON w.exam_result_id = r.id
                WHERE r.exam_id = ?
                GROUP BY knowledge_point
                ORDER BY total DESC
            """
            kp_rows = conn.execute(kp_sql, (exam_id,)).fetchall()
            kp_stats = []
            for kp in kp_rows:
                rate = round(kp["earned"] / kp["max_s"] * 100, 1) if kp["max_s"] > 0 else 0
                kp_stats.append({
                    "knowledge_point": kp["knowledge_point"],
                    "total": kp["total"],
                    "correct": kp["correct"],
                    "score_rate": rate,
                })

            # 分数分布（按total_score分桶）
            results = conn.execute(
                "SELECT total_score, max_score FROM exam_results WHERE exam_id=?",
                (exam_id,)
            ).fetchall()
            buckets = {"0-20%": 0, "20-40%": 0, "40-60%": 0, "60-80%": 0, "80-100%": 0}
            scores = []
            for r in results:
                pct = r["total_score"] / r["max_score"] * 100 if r["max_score"] > 0 else 0
                scores.append(r["total_score"])
                if pct < 20: buckets["0-20%"] += 1
                elif pct < 40: buckets["20-40%"] += 1
                elif pct < 60: buckets["40-60%"] += 1
                elif pct < 80: buckets["60-80%"] += 1
                else: buckets["80-100%"] += 1

            # 质量指标
            n = len(scores)
            avg = sum(scores) / n if n > 0 else 0
            variance = sum((s - avg) ** 2 for s in scores) / n if n > 0 else 0
            std_dev = variance ** 0.5
            max_s = max(scores) if scores else 0
            min_s = min(scores) if scores else 0
            difficulty = round((1 - avg / (exam["total_score"] or 1)) * 100, 1)

            return {
                "exam": dict(exam),
                "knowledge_points": kp_stats,
                "score_distribution": buckets,
                "quality": {
                    "avg_score": round(avg, 1),
                    "std_dev": round(std_dev, 1),
                    "max_score": max_s,
                    "min_score": min_s,
                    "difficulty": difficulty,
                    "total_students": n,
                }
            }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="阅卷无忧数据库")
    ap.add_argument("--db", default="yuejuan.db", help="数据库路径")
    sub = ap.add_subparsers(dest="cmd")

    # 导入考试结果
    p_import = sub.add_parser("import-results")
    p_import.add_argument("--results", required=True, help="grade_results.json路径")
    p_import.add_argument("--config", required=True, help="exam_config.json路径")
    p_import.add_argument("--exam-name", default="", help="考试名称")
    p_import.add_argument("--subject", default="", help="科目")
    p_import.add_argument("--class-name", default="", help="班级")
    p_import.add_argument("--exam-date", default="", help="考试日期")

    # 错题查询
    p_q = sub.add_parser("query-wrong")
    p_q.add_argument("--student", default="", help="学号")
    p_q.add_argument("--kp", default="", help="知识点")
    p_q.add_argument("--limit", type=int, default=50)

    # 错题统计
    p_s = sub.add_parser("wrong-stats")
    p_s.add_argument("--student", default="", help="学号")

    # 导入学生名单
    p_rs = sub.add_parser("import-students")
    p_rs.add_argument("--file", required=True, help="学生名单CSV文件路径")
    p_rs.add_argument("--class-name", default="", help="班级（CSV无班级列时使用）")

    # 查询学生
    p_qs = sub.add_parser("query-student")
    p_qs.add_argument("--id", required=True, help="学号")

    # 考试统计
    p_es = sub.add_parser("exam-stats")
    p_es.add_argument("--exam-id", type=int, default=0, help="考试ID（0=最新）")

    # 考试列表
    p_le = sub.add_parser("list-exams")

    # 多考试对比
    p_ce = sub.add_parser("compare-exams")
    p_ce.add_argument("--ids", required=True, help="逗号分隔的考试ID，如 1,2,3")

    # 学生个人统计
    p_ss = sub.add_parser("student-stats")
    p_ss.add_argument("--student-id", required=True, help="学号")

    # 批量查询学生
    p_bs = sub.add_parser("batch-students")
    p_bs.add_argument("--ids", required=True, help="逗号分隔的学号列表")

    args = ap.parse_args()

    if args.cmd == "import-results":
        import json as _json
        db = Database(args.db)
        with open(args.config, "r", encoding="utf-8") as f:
            config = _json.load(f)
        with open(args.results, "r", encoding="utf-8") as f:
            data = _json.load(f)

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

    elif args.cmd == "query-wrong":
        db = Database(args.db)
        rows = db.query_wrong_answers(
            student_id=args.student or None,
            knowledge_point=args.kp or None,
            limit=args.limit
        )
        for r in rows:
            print(f"[{r['knowledge_point']}] 题{r['qid']} 生答={r['user_answer']} 正解={r['correct_answer']} 得分={r['score_earned']}/{r['max_score']} [{r['student_id']}]")
        print(f"\n共 {len(rows)} 条")

    elif args.cmd == "wrong-stats":
        db = Database(args.db)
        stats = db.wrong_answer_stats(args.student or None)
        for s in stats:
            print(f"{s['knowledge_point']}: {s['cnt']}次 总得分{s['earned']}/{s['max_s']}")
        print(f"\n共 {len(stats)} 个知识点有错题")

    elif args.cmd == "import-students":
        import csv
        db = Database(args.db)
        count = 0
        with open(args.file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = [h.strip() for h in (reader.fieldnames or [])]
            # 自动匹配列名
            id_col = next((h for h in headers if h in ("学号", "id", "student_id", "ID", "编号")), None)
            name_col = next((h for h in headers if h in ("姓名", "name", "学生姓名", "名字")), None)
            class_col = next((h for h in headers if h in ("班级", "class", "class_name", "班")), None)
            if not id_col:
                id_col = headers[0]  # 兜底：第一列
            if not name_col and len(headers) > 1:
                name_col = headers[1]  # 兜底：第二列
            for row in reader:
                sid = (row.get(id_col) or "").strip()
                name = ((row.get(name_col) or "").strip() if name_col else "")
                cls = ((row.get(class_col) or "").strip() if class_col else "") or args.class_name
                if sid:
                    db.ensure_student(sid, name, cls)
                    count += 1
        print(f"✅ 已导入 {count} 名学生")

    elif args.cmd == "query-student":
        db = Database(args.db)
        s = db.get_student(args.id)
        if s:
            import json as _json
            print(_json.dumps(s, ensure_ascii=False))
        else:
            print("null")

    elif args.cmd == "exam-stats":
        import json as _json
        db = Database(args.db)
        stats = db.get_exam_stats(args.exam_id if args.exam_id else None)
        if stats:
            print(_json.dumps(stats, ensure_ascii=False))
        else:
            print("null")

    elif args.cmd == "list-exams":
        import json as _json
        db = Database(args.db)
        exams = db.get_exam_list()
        print(_json.dumps(exams, ensure_ascii=False))

    elif args.cmd == "compare-exams":
        import json as _json
        db = Database(args.db)
        ids = [int(x.strip()) for x in args.ids.split(",")]
        stats = db.compare_exams(ids)
        print(_json.dumps(stats, ensure_ascii=False))

    elif args.cmd == "student-stats":
        import json as _json
        db = Database(args.db)
        stats = db.get_student_stats(args.student_id)
        if stats:
            print(_json.dumps(stats, ensure_ascii=False))
        else:
            print("null")

    elif args.cmd == "batch-students":
        import json as _json
        db = Database(args.db)
        ids = [x.strip() for x in args.ids.split(",")]
        result = db.batch_get_students(ids)
        print(_json.dumps(result, ensure_ascii=False))

    else:
        # 快速自测
        db = Database(":memory:")
        db.ensure_student("20240001", "张三", "初二(3)班")
        s = db.get_student("20240001")
        print(f"学生: {s}")

        eid = db.create_exam("测试考试", "物理", "初二(3)班", "2026-05-12", 35)
        db.add_question(1, eid, "choice", "问题?", '["A","B"]', "B", 3, "力学")
        db.update_exam_stats(eid, 28.5, 5)
        print(f"考试ID: {eid}")

        rid = db.save_result(eid, "20240001", 15, 12, 27, 35, "{}")
        db.add_wrong_answer(rid, "20240001", 1, "choice", "A", "B", "力学", 0, 3)
        wrongs = db.query_wrong_answers("20240001")
        print(f"错题数: {len(wrongs)}")
        stats = db.wrong_answer_stats("20240001")
        print(f"错题统计: {stats}")
        print("✅ 数据库自测通过")
