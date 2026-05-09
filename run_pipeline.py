#!/usr/bin/env python3
"""阅卷无忧 - 一键流水线（生成→判分→报告）"""
import subprocess, json, sys, os, argparse

BASE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, step_name):
    print(f"\n{'='*50}")
    print(f"  {step_name}")
    print(f"{'='*50}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE)
    print(result.stdout)
    if result.returncode != 0:
        print(f"❌ 失败:\n{result.stderr}")
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="阅卷无忧 - 一键批改流水线")
    p.add_argument("--config", required=True, help="考试配置JSON")
    p.add_argument("--copies", type=int, default=5, help="模拟答卷份数")
    p.add_argument("--seed", type=int, default=42, help="随机种子")
    p.add_argument("--output-dir", default=".", help="输出目录")
    p.add_argument("--skip-generate", action="store_true", help="跳过答题卡生成")
    p.add_argument("--skip-fill", action="store_true", help="跳过模拟填涂")
    p.add_argument("--skip-report", action="store_true", help="跳过报告生成")
    args = p.parse_args()

    config_path = os.path.abspath(args.config) if not os.path.isabs(args.config) else args.config
    out_dir = os.path.abspath(args.output_dir) if not os.path.isabs(args.output_dir) else args.output_dir
    sheet_path = os.path.join(out_dir, "answer_sheets.pdf")
    filled_path = os.path.join(out_dir, "filled_answers.pdf")
    result_path = os.path.join(out_dir, "grade_results.json")
    report_path = os.path.join(out_dir, "grade_report.md")

    # 步骤1：生成答题卡
    if not args.skip_generate:
        run(f"python3 generate_sheet.py --config '{config_path}' --copies {args.copies} --output '{sheet_path}'",
            "步骤1/5: 生成答题卡")
    else:
        print("\n⏭ 跳过答题卡生成")
        if not os.path.exists(sheet_path):
            print(f"❌ 需要已有答题卡: {sheet_path}")
            sys.exit(1)

    # 步骤2：模拟填涂
    if not args.skip_fill:
        run(f"python3 fill_simulator.py --config '{config_path}' --sheet '{sheet_path}' --output '{filled_path}' --seed {args.seed} --copies {args.copies}",
            "步骤2/5: 模拟学生填涂")
    else:
        print("\n⏭ 跳过模拟填涂")
        if not os.path.exists(filled_path):
            print(f"❌ 需要已有答卷: {filled_path}")
            sys.exit(1)

    # 步骤3：扫描判分
    run(f"python3 scan_and_grade.py --config '{config_path}' --scan '{filled_path}' --output '{result_path}' --resume",
        "步骤3/5: 扫描判分")

    # 步骤4：生成报告
    if not args.skip_report:
        run(f"python3 report_generator.py --results '{result_path}' --config '{config_path}' --output '{report_path}' --format md",
            "步骤4/5: 生成成绩报告")
    else:
        print("\n⏭ 跳过报告生成")

    # 步骤5：错题入库
    db_path = os.path.join(out_dir, "yuejuan.db")
    run(f"python3 database.py --db '{db_path}' import-results --results '{result_path}' --config '{config_path}'",
        "步骤5/5: 错题入库")

    print(f"\n{'='*50}")
    print(f"  ✅ 流水线完成！")
    print(f"{'='*50}")
    print(f"  答题卡:     {sheet_path}")
    print(f"  答卷:       {filled_path}")
    print(f"  判分结果:   {result_path}")
    if not args.skip_report:
        print(f"  成绩报告:   {report_path}")


if __name__ == "__main__":
    main()
