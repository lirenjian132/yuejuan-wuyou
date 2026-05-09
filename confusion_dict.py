#!/usr/bin/env python3
"""阅卷无忧 - 学科混淆词典（OCR后处理辅助）
用途：OCR识别结果与标准答案对比时，利用学科知识点上下文辅助判断。
设计原则：
  - 不做自动改分！只标记"疑似OCR误读"供教师确认
  - 所有纠正附带置信度和理由
  - 仅在OCR置信度<0.85且相似度<0.65时触发
"""

# ============================================================
# 物理学科混淆词典
# key: (OCR误读词, 标准答案词)
# value: (知识点上下文, 混淆原因, 置信度)
# ============================================================
PHYSICS_CONFUSION = {
    # 二力平衡 → 相反
    ("相友", "相反"): ("二力平衡", "字形相似: 反↔友", 0.85),
    ("反", "友"):   ("二力平衡", "字形相似: 反↔友", 0.80),

    # 摩擦力 → 压力
    ("压刀", "压力"): ("摩擦力", "字形相似: 力↔刀", 0.85),
    ("压力", "压刀"): ("摩擦力", "字形相似: 力↔刀", 0.80),

    # 惯性
    ("惯", "惯性"):   ("牛顿第一定律", "OCR漏字: 仅识别首字", 0.70),

    # 牛顿
    ("牛", "牛顿"):   ("力的单位", "OCR漏字: 仅识别首字", 0.70),

    # 重力
    ("重", "重力"):   ("重力", "OCR漏字: 仅识别首字", 0.70),

    # 摩擦力 (其他变体)
    ("摩", "摩擦力"): ("摩擦力", "OCR漏字: 仅识别首字", 0.65),
    ("擦", "摩擦力"): ("摩擦力", "OCR漏字: 仅识别首字", 0.65),

    # 匀速直线运动
    ("匀速", "匀速直线运动"): ("牛顿第一定律", "OCR漏字: 仅识别部分", 0.65),
    ("直线", "匀速直线运动"): ("牛顿第一定律", "OCR漏字: 仅识别部分", 0.65),
}

# ============================================================
# 数学学科混淆词典（预置，后续扩展）
# ============================================================
MATH_CONFUSION = {
    # 常见数学符号混淆
    ("2", "Z"):  ("集合", "字形相似", 0.60),
    ("Z", "2"):  ("集合", "字形相似", 0.60),
}

# ============================================================
# 通用混淆词典（跨学科）
# ============================================================
GENERAL_CONFUSION = {
    # 单字混淆
    ("力", "刀"): ("通用", "字形相似: 力↔刀", 0.80),
    ("刀", "力"): ("通用", "字形相似: 力↔刀", 0.80),
    ("反", "友"): ("通用", "字形相似: 反↔友", 0.80),
    ("友", "反"): ("通用", "字形相似: 反↔友", 0.80),

    # 数字混淆
    ("0", "O"): ("通用", "字形相似: 0↔O", 0.70),
    ("O", "0"): ("通用", "字形相似: 0↔O", 0.70),
    ("1", "l"): ("通用", "字形相似: 1↔l", 0.70),
    ("l", "1"): ("通用", "字形相似: 1↔l", 0.70),

    # 括号混淆
    ("（", "("): ("通用", "全角/半角括号", 0.95),
    ("）", ")"): ("通用", "全角/半角括号", 0.95),
}


def check_confusion(ocr_text, correct_answer, knowledge_point="", subject="physics"):
    """
    检查OCR结果是否为已知混淆对。
    返回: dict 或 None
      {
        "suspected_ocr_error": True,
        "suggested_correction": "相反",
        "reason": "字形相似: 反↔友",
        "confidence": 0.85,
        "action": "flag_for_review"  # 不自动纠正，标记教师确认
      }
    """
    # 归一化
    ocr_clean = ocr_text.strip()
    ans_clean = correct_answer.strip()

    # 完全匹配 → 无需检查
    if ocr_clean == ans_clean:
        return None

    # 逐级查词典
    for source in [PHYSICS_CONFUSION, MATH_CONFUSION, GENERAL_CONFUSION]:
        for (ocr_key, ans_key), (ctx, reason, conf) in source.items():
            # 方向1: OCR文本误读为混淆词, 标准答案就是混淆词的纠正方向
            if ocr_clean == ocr_key and ans_clean == ans_key:
                # 知识点匹配检查（通用词典跳过）
                if ctx != "通用" and knowledge_point and ctx not in knowledge_point:
                    continue
                return {
                    "suspected_ocr_error": True,
                    "suggested_correction": ans_key,
                    "ocr_read_as": ocr_key,
                    "reason": reason,
                    "confidence": conf,
                    "action": "flag_for_review",
                }
            # 方向2: 标准答案恰好是混淆词, OCR误读为纠正方向 (罕见但需覆盖)
            if ocr_clean == ans_key and ans_clean == ocr_key:
                if ctx != "通用" and knowledge_point and ctx not in knowledge_point:
                    continue
                return {
                    "suspected_ocr_error": False,
                    "suggested_correction": ocr_clean,
                    "ocr_read_as": ocr_key,
                    "reason": f"答案'{ans_key}'可能被OCR误读为'{ocr_key}': {reason}",
                    "confidence": conf * 0.7,  # 反向匹配置信度打折
                    "action": "flag_for_review",
                }

    return None


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    tests = [
        # (ocr_text, answer, knowledge_point, expected_action)
        ("相友", "相反", "二力平衡", "flag_for_review"),
        ("压刀", "压力", "摩擦力", "flag_for_review"),
        ("惯性", "惯性", "牛顿第一定律", None),      # 完全匹配，不触发
        ("相友", "相反", "", "flag_for_review"),       # 无知识点时通用词典兜底
        ("牛", "牛顿", "力的单位", "flag_for_review"), # 漏字
        ("9.8", "9.8", "重力", None),                  # 完全匹配
        ("ABCD", "相反", "", None),                    # 不在词典中
    ]

    for ocr, ans, kp, expected in tests:
        result = check_confusion(ocr, ans, kp)
        action = result["action"] if result else None
        status = "✅" if action == expected else "❌"
        print(f"{status} OCR='{ocr}' ANS='{ans}' KP='{kp}' → action={action} (expect={expected})")
        if result:
            print(f"   → {result['reason']} conf={result['confidence']}")

    print("\n✅ 混淆词典自测完成")
