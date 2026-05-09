#!/usr/bin/env python3
"""阅卷无忧 - 多科目综合测试"""
import json, os, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
TMP = "/tmp/yj_multi_test"
os.makedirs(TMP, exist_ok=True)

PASS, FAIL, TOTAL = 0, 0, 0

def check(label, condition):
    global PASS, FAIL
    if condition:
        print(f"  ✅ {label}")
        PASS += 1
    else:
        print(f"  ❌ {label}")
        FAIL += 1

def run(cmd, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE, timeout=timeout)
    return r.returncode == 0, r.stdout, r.stderr

# =======================================================
# CONFIG 1: 初中数学 (8选择 + 6填空)
# =======================================================
math_config = {
    "exam_name": "初二数学一次函数单元测试",
    "subject": "数学",
    "grade": "初二(1)班",
    "date": "2026-05-15",
    "paper_size": "A4",
    "questions": [
        {"id":1,"type":"choice","content":"一次函数y=2x+1的图像经过第几象限？","options":["A. 一、二、三","B. 一、三、四","C. 一、二、四","D. 二、三、四"],"answer":"B","score":3,"knowledge_point":"一次函数图像"},
        {"id":2,"type":"choice","content":"直线y=-3x+2的斜率是？","options":["A. 2","B. -2","C. 3","D. -3"],"answer":"D","score":3,"knowledge_point":"斜率"},
        {"id":3,"type":"choice","content":"点(2,5)在直线y=2x+b上，则b=？","options":["A. 0","B. 1","C. 2","D. 3"],"answer":"B","score":3,"knowledge_point":"待定系数法"},
        {"id":4,"type":"choice","content":"y随x增大而减小的函数是？","options":["A. y=2x","B. y=x+1","C. y=-x+3","D. y=3"],"answer":"C","score":3,"knowledge_point":"函数增减性"},
        {"id":5,"type":"choice","content":"两直线y=2x+1与y=2x-3的位置关系？","options":["A. 相交","B. 平行","C. 重合","D. 垂直"],"answer":"B","score":3,"knowledge_point":"直线位置关系"},
        {"id":6,"type":"choice","content":"函数y=(m-2)x+1是一次函数，则m的取值范围？","options":["A. m>2","B. m<2","C. m=2","D. m≠2"],"answer":"D","score":3,"knowledge_point":"一次函数定义"},
        {"id":7,"type":"choice","content":"直线y=kx+b过(1,3)和(2,5)，则k=？","options":["A. 1","B. 2","C. 3","D. -1"],"answer":"B","score":3,"knowledge_point":"斜率计算"},
        {"id":8,"type":"choice","content":"一次函数y=kx+b中，b表示？","options":["A. 斜率","B. 截距","C. 自变量","D. 因变量"],"answer":"B","score":3,"knowledge_point":"截距概念"},
        {"id":9,"type":"fill","content":"一次函数的一般形式为y=____。","answer":"kx+b","score":4,"knowledge_point":"一次函数定义"},
        {"id":10,"type":"fill","content":"正比例函数是特殊的____函数。","answer":"一次","score":4,"knowledge_point":"正比例函数"},
        {"id":11,"type":"fill","content":"直线y=3x-5与y轴的交点坐标是(0,____)。","answer":"-5","score":4,"knowledge_point":"截距"},
        {"id":12,"type":"fill","content":"若y=(m+1)x+2是正比例函数，则m=____。","answer":"-1","score":4,"knowledge_point":"正比例函数条件"},
        {"id":13,"type":"fill","content":"一次函数y=2x-4与x轴的交点坐标中x=____。","answer":"2","score":4,"knowledge_point":"与x轴交点"},
        {"id":14,"type":"fill","content":"直线y=kx+b中，当k____0时y随x增大而增大。","answer":">","score":4,"knowledge_point":"函数增减性"},
    ]
}

# =======================================================
# CONFIG 2: 初中英语词汇 (10选择 + 5填空)
# =======================================================
english_config = {
    "exam_name": "初二英语Unit 5词汇测试",
    "subject": "英语",
    "grade": "初二(3)班",
    "date": "2026-05-16",
    "paper_size": "A4",
    "questions": [
        {"id":1,"type":"choice","content":"The weather is _____ today. Let's go out.","options":["A. rain","B. rainy","C. sunny","D. sun"],"answer":"C","score":2,"knowledge_point":"形容词辨析"},
        {"id":2,"type":"choice","content":"She _____ to school by bus every day.","options":["A. go","B. goes","C. going","D. went"],"answer":"B","score":2,"knowledge_point":"一般现在时"},
        {"id":3,"type":"choice","content":"There _____ some milk in the glass.","options":["A. is","B. are","C. have","D. has"],"answer":"A","score":2,"knowledge_point":"There be句型"},
        {"id":4,"type":"choice","content":"I have two _____.","options":["A. pen","B. a pen","C. pens","D. the pen"],"answer":"C","score":2,"knowledge_point":"名词复数"},
        {"id":5,"type":"choice","content":"_____ is your favorite subject?","options":["A. What","B. Who","C. When","D. Where"],"answer":"A","score":2,"knowledge_point":"疑问词"},
        {"id":6,"type":"choice","content":"He can _____ English well.","options":["A. speak","B. speaks","C. speaking","D. spoke"],"answer":"A","score":2,"knowledge_point":"情态动词"},
        {"id":7,"type":"choice","content":"My mother is a _____. She works in a hospital.","options":["A. teacher","B. doctor","C. farmer","D. driver"],"answer":"B","score":2,"knowledge_point":"职业词汇"},
        {"id":8,"type":"choice","content":"Don't _____ in the library.","options":["A. talk","B. talks","C. talking","D. talked"],"answer":"A","score":2,"knowledge_point":"祈使句"},
        {"id":9,"type":"choice","content":"Tom is _____ than Jim.","options":["A. tall","B. taller","C. tallest","D. the tallest"],"answer":"B","score":2,"knowledge_point":"比较级"},
        {"id":10,"type":"choice","content":"Would you like _____ cup of tea?","options":["A. a","B. an","C. the","D. /"],"answer":"A","score":2,"knowledge_point":"冠词"},
        {"id":11,"type":"fill","content":"Please _____ (打开) the window.","answer":"open","score":3,"knowledge_point":"动词词汇"},
        {"id":12,"type":"fill","content":"The opposite of 'hot' is _____.","answer":"cold","score":3,"knowledge_point":"反义词"},
        {"id":13,"type":"fill","content":"I _____ (喜欢) playing basketball.","answer":"like","score":3,"knowledge_point":"动词词汇"},
        {"id":14,"type":"fill","content":"Monday is the _____ (第二) day of the week.","answer":"second","score":3,"knowledge_point":"序数词"},
        {"id":15,"type":"fill","content":"We should _____ (保护) the environment.","answer":"protect","score":3,"knowledge_point":"动词词汇"},
    ]
}

# =======================================================
# CONFIG 3: 初中化学 (6选择 + 8填空)  
# =======================================================
chemistry_config = {
    "exam_name": "初三化学物质构成单元测试",
    "subject": "化学",
    "grade": "初三(2)班",
    "date": "2026-05-17",
    "paper_size": "A4",
    "questions": [
        {"id":1,"type":"choice","content":"下列属于纯净物的是？","options":["A. 空气","B. 食盐水","C. 蒸馏水","D. 石油"],"answer":"C","score":2,"knowledge_point":"纯净物与混合物"},
        {"id":2,"type":"choice","content":"水的化学式是？","options":["A. H2O2","B. H2O","C. HO","D. O2H"],"answer":"B","score":2,"knowledge_point":"化学式"},
        {"id":3,"type":"choice","content":"原子核由什么组成？","options":["A. 电子和质子","B. 质子和中子","C. 电子和中子","D. 只有质子"],"answer":"B","score":2,"knowledge_point":"原子结构"},
        {"id":4,"type":"choice","content":"下列变化属于化学变化的是？","options":["A. 水结成冰","B. 铁生锈","C. 酒精挥发","D. 玻璃破碎"],"answer":"B","score":2,"knowledge_point":"物理变化与化学变化"},
        {"id":5,"type":"choice","content":"氧元素的符号是？","options":["A. O","B. O2","C. O3","D. Oh"],"answer":"A","score":2,"knowledge_point":"元素符号"},
        {"id":6,"type":"choice","content":"地壳中含量最多的金属元素是？","options":["A. 铁","B. 铝","C. 钙","D. 钠"],"answer":"B","score":2,"knowledge_point":"元素含量"},
        {"id":7,"type":"fill","content":"分子是保持物质____性质的最小粒子。","answer":"化学","score":3,"knowledge_point":"分子定义"},
        {"id":8,"type":"fill","content":"原子序数=____数=核外电子数。","answer":"质子","score":3,"knowledge_point":"原子结构"},
        {"id":9,"type":"fill","content":"相对原子质量的单位是____。","answer":"1","score":3,"knowledge_point":"相对原子质量"},
        {"id":10,"type":"fill","content":"二氧化碳的化学式是____。","answer":"CO2","score":3,"knowledge_point":"化学式"},
        {"id":11,"type":"fill","content":"元素周期表中，同一周期的元素具有相同的____数。","answer":"电子层","score":3,"knowledge_point":"元素周期表"},
        {"id":12,"type":"fill","content":"氯化钠的化学式是____。","answer":"NaCl","score":3,"knowledge_point":"化学式"},
        {"id":13,"type":"fill","content":"原子中，质子带____电。","answer":"正","score":3,"knowledge_point":"原子结构"},
        {"id":14,"type":"fill","content":"氧气由____元素组成。","answer":"氧","score":3,"knowledge_point":"元素组成"},
    ]
}

# =======================================================
# CONFIG 4: 边缘案例压测 (5选择 + 5填空, 含各种陷阱)
# =======================================================
edge_config = {
    "exam_name": "边缘场景压力测试",
    "subject": "综合",
    "grade": "测试班",
    "date": "2026-05-20",
    "paper_size": "A4",
    "questions": [
        {"id":1,"type":"choice","content":"测试题1（正确答案A）","options":["A","B","C","D"],"answer":"A","score":5,"knowledge_point":"基础"},
        {"id":2,"type":"choice","content":"测试题2（正确答案B）","options":["A","B","C","D"],"answer":"B","score":5,"knowledge_point":"基础"},
        {"id":3,"type":"choice","content":"测试题3（正确答案C）","options":["A","B","C","D"],"answer":"C","score":5,"knowledge_point":"基础"},
        {"id":4,"type":"choice","content":"测试题4（正确答案D）","options":["A","B","C","D"],"answer":"D","score":5,"knowledge_point":"基础"},
        {"id":5,"type":"choice","content":"测试题5（正确答案A）","options":["A","B","C","D"],"answer":"A","score":5,"knowledge_point":"基础"},
        # 填空：各种边缘情况
        {"id":6,"type":"fill","content":"纯数字答案____。","answer":"123","score":5,"knowledge_point":"数字"},
        {"id":7,"type":"fill","content":"带小数____。","answer":"3.14","score":5,"knowledge_point":"小数"},
        {"id":8,"type":"fill","content":"英文字母____。","answer":"ABC","score":5,"knowledge_point":"字母"},
        {"id":9,"type":"fill","content":"中英文混合____。","answer":"pH值","score":5,"knowledge_point":"混合"},
        {"id":10,"type":"fill","content":"超短单字____。","answer":"力","score":5,"knowledge_point":"单字"},
    ]
}

configs = [
    ("math", math_config, 25),
    ("english", english_config, 25),
    ("chemistry", chemistry_config, 25),
    ("edge", edge_config, 20),
]

all_pass = True
total_tests = 0
total_pass = 0

for name, config, copies in configs:
    print(f"\n{'='*60}")
    print(f"  测试: {config['exam_name']} ({copies}份)")
    print(f"{'='*60}")
    
    cfg_path = f"{TMP}/{name}_config.json"
    sheet_path = f"{TMP}/{name}_sheets.pdf"
    filled_path = f"{TMP}/{name}_filled.pdf"
    result_path = f"{TMP}/{name}_results.json"
    report_path = f"{TMP}/{name}_report.md"
    db_path = f"{TMP}/{name}.db"
    
    with open(cfg_path, "w") as f:
        json.dump(config, f, ensure_ascii=False)
    
    # Step 1: Generate
    ok, out, err = run(f"python3 generate_sheet.py --config {cfg_path} --copies {copies} --output {sheet_path}")
    check(f"{name}: 生成答题卡", ok and "已生成" in out)
    
    # Step 2: Fill
    ok, out, err = run(f"python3 fill_simulator.py --config {cfg_path} --sheet {sheet_path} --output {filled_path} --copies {copies} --seed {hash(name)%1000}")
    check(f"{name}: 模拟填涂", ok)
    
    # Step 3: Grade
    ok, out, err = run(f"python3 scan_and_grade.py --config {cfg_path} --scan {filled_path} --output {result_path}", timeout=180)
    check(f"{name}: 扫描判分", ok and "判分完成" in out)
    
    # Verify results
    if ok:
        with open(result_path) as f:
            data = json.load(f)
        results = data.get("results", [])
        check(f"{name}: 结果数={len(results)} (期望{copies})", len(results) == copies)
        
        # All choices should have valid scores
        for r in results:
            cs = r.get("choice_score", -1)
            check(f"{name}: 选择得分合理({cs})", cs >= 0)
        
        # Fill should have review flags if applicable
        review_count = sum(1 for r in results for fd in r.get("fill_details",[]) if fd.get("review_flag"))
        print(f"      ℹ️ 审阅标记: {review_count}")
    
    # Step 4: Report
    ok, out, err = run(f"python3 report_generator.py --results {result_path} --config {cfg_path} --output {report_path}")
    check(f"{name}: 成绩报告", ok)
    
    # Step 5: Database
    ok, out, err = run(f"python3 database.py --db {db_path} import-results --results {result_path} --config {cfg_path}")
    check(f"{name}: 错题入库", ok and "考试ID" in out)
    
    total_tests += 10  # 5 steps + 2 verifications + some extras
    # Count actual tests

print(f"\n{'='*60}")
print(f"  最终结果: {PASS}/{PASS+FAIL} 通过")
if FAIL > 0:
    print(f"  ⚠️ {FAIL} 项失败!")
else:
    print(f"  🎉 全部通过！")
print(f"  输出目录: {TMP}")
