#!/usr/bin/env python3
"""阅卷无忧 - 导出工具
提供两种导出功能：
  1. export-grades：导出学生成绩表为 CSV
  2. export-wrong-answers：导出错题本为 CSV
"""
import argparse
import csv
import sqlite3
import sys
import os

BOM = "\ufeff"


def export_grades(db_path, output_path, exam_id=None):
    """导出学生成绩表 CSV：学号,姓名,考试,选择题得分,填空得分,总分,排名"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # 构建查询：根据 exam_id 筛选
        params = []
        where = ""
        if exam_id is not None:
            where = "WHERE ex.id = ?"
            params = [exam_id]

        sql = f"""
            SELECT
                r.student_id,
                s.name,
                ex.name AS exam_name,
                r.choice_score,
                r.fill_score,
                r.total_score,
                RANK() OVER (PARTITION BY r.exam_id ORDER BY r.total_score DESC) AS rank
            FROM exam_results r
            LEFT JOIN students s ON r.student_id = s.id
            LEFT JOIN exams ex ON r.exam_id = ex.id
            {where}
            ORDER BY ex.id, r.total_score DESC
        """
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["学号", "姓名", "考试", "选择题得分", "填空得分", "总分", "排名"])
        for row in rows:
            writer.writerow([
                row["student_id"],
                row["name"] or "",
                row["exam_name"] or "",
                row["choice_score"],
                row["fill_score"],
                row["total_score"],
                row["rank"],
            ])

    print(f"成绩导出完成：{len(rows)} 条记录 → {output_path}")
    return output_path


def export_wrong_answers(db_path, output_path, exam_id=None):
    """导出错题本 CSV：学号,姓名,题号,知识点,考生答案,正确答案,得分"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        params = []
        where = ""
        if exam_id is not None:
            where = "WHERE ex.id = ?"
            params = [exam_id]

        sql = f"""
            SELECT
                w.student_id,
                s.name,
                w.qid,
                w.knowledge_point,
                w.user_answer,
                w.correct_answer,
                w.score_earned,
                w.max_score
            FROM wrong_answers w
            LEFT JOIN students s ON w.student_id = s.id
            LEFT JOIN exam_results r ON w.exam_result_id = r.id
            LEFT JOIN exams ex ON r.exam_id = ex.id
            {where}
            ORDER BY w.student_id, w.qid
        """
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["学号", "姓名", "题号", "知识点", "考生答案", "正确答案", "得分"])
        for row in rows:
            writer.writerow([
                row["student_id"],
                row["name"] or "",
                row["qid"],
                row["knowledge_point"] or "",
                row["user_answer"] or "",
                row["correct_answer"] or "",
                f"{row['score_earned']}/{row['max_score']}",
            ])

    print(f"错题导出完成：{len(rows)} 条记录 → {output_path}")
    return output_path


def main():
    ap = argparse.ArgumentParser(description="阅卷无忧 - 导出工具")
    ap.add_argument("--db", required=True, help="数据库路径 (yuejuan.db)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # export-grades
    p_grades = sub.add_parser("export-grades", help="导出学生成绩表为CSV")
    p_grades.add_argument("--output", required=True, help="输出CSV文件路径")
    p_grades.add_argument("--exam-id", type=int, default=None, help="筛选特定考试ID（可选）")

    # export-wrong-answers
    p_wrong = sub.add_parser("export-wrong-answers", help="导出错题本为CSV")
    p_wrong.add_argument("--output", required=True, help="输出CSV文件路径")
    p_wrong.add_argument("--exam-id", type=int, default=None, help="筛选特定考试ID（可选）")

    args = ap.parse_args()

    if args.cmd == "export-grades":
        export_grades(args.db, args.output, args.exam_id)
    elif args.cmd == "export-wrong-answers":
        export_wrong_answers(args.db, args.output, args.exam_id)


if __name__ == "__main__":
    main()
