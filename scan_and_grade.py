#!/usr/bin/env python3
"""阅卷无忧 - 统一判分引擎 v9（崩溃恢复 + generate_sheet精确坐标）"""
import argparse, json, sys, os, hashlib, numpy as np, cv2, fitz, re, jieba
from difflib import SequenceMatcher
from template_matcher import detect_markers, warp_perspective

DPI = 300
MARGIN_PT = 36
DIGIT_WIDTH = 28; DIGIT_GAP = 36; CIRCLE_RADIUS = 3; CIRCLE_GAP = 6
CHOICE_CIRCLE_RADIUS = 7; CHOICE_OPTION_GAP = 16; CHOICE_ROW_GAP = 48; CHOICE_COLS_PER_ROW = 5
FILL_LINE_GAP = 36
PAPER_SIZES = {"A4": (595, 842), "B4": (709, 1006)}
ID_DETECT = 0.80; CH_DETECT = 0.75
THRESH_FILL = 0.40; THRESH_GAP = 0.12

def p2p(pt):
    return int(pt * DPI / 72)

def cfill(img, cx, cy, r):
    h, w = img.shape
    x1, y1 = max(0, cx-r), max(0, cy-r)
    x2, y2 = min(w, cx+r), min(h, cy+r)
    if x1 >= x2 or y1 >= y2:
        return 0.0
    reg = img[y1:y2, x1:x2]; rr, rc = reg.shape
    mask = np.zeros_like(reg, np.uint8)
    cv2.circle(mask, (rc//2, rr//2), r, 255, -1)
    mask = mask[:rr, :rc]
    t = np.count_nonzero(mask)
    return np.count_nonzero((reg < 128) & (mask > 0)) / t if t else 0.0

def read_sid(norm, pw_pt, ph_pt):
    mp = p2p(MARGIN_PT); h, w = norm.shape[:2]
    cw, ch = pw_pt - 2*MARGIN_PT, ph_pt - 2*MARGIN_PT
    sx = (w - 2*mp) / cw; sy = (h - 2*mp) / ch
    x0 = MARGIN_PT + 10; iy = ph_pt - MARGIN_PT - 78
    dr = p2p(CIRCLE_RADIUS * ID_DETECT)
    d = []
    for di in range(8):
        dx = x0 + di * (DIGIT_WIDTH + DIGIT_GAP)
        fills = []
        for v in range(10):
            if v < 5:
                cx, cy = dx + v*CIRCLE_GAP, iy - 5
            else:
                cx, cy = dx + (v-5)*CIRCLE_GAP, iy - 5 - CIRCLE_GAP - 2
            px = int(mp + (cx + CIRCLE_RADIUS - MARGIN_PT) * sx)
            py = int(mp + (ph_pt - (cy + CIRCLE_RADIUS) - MARGIN_PT) * sy)
            fills.append((v, cfill(norm, px, py, dr)))
        best = max(fills, key=lambda x: x[1])
        d.append(str(best[0]) if best[1] > 0.3 else "?")
    return "".join(d)

def read_choice(norm, pw_pt, ph_pt, nc):
    """读取选择题答案。坐标与 generate_sheet.py 精确匹配。"""
    mp = p2p(MARGIN_PT); h, w = norm.shape[:2]
    cw, ch = pw_pt - 2*MARGIN_PT, ph_pt - 2*MARGIN_PT
    sx = (w - 2*mp) / cw; sy = (h - 2*mp) / ch
    choices = []
    col_w = (pw_pt - 2*MARGIN_PT) / CHOICE_COLS_PER_ROW
    for qi in range(nc):
        ri, ci = qi // CHOICE_COLS_PER_ROW, qi % CHOICE_COLS_PER_ROW
        rx = MARGIN_PT + 10 + ci * col_w
        ry = ph_pt - MARGIN_PT - 38 - 78 - 15 - ri * CHOICE_ROW_GAP
        fills = []
        for oi, opt in enumerate("ABCDE"):
            cx = rx + 20 + oi * CHOICE_OPTION_GAP
            cy = ry - 4
            # cx/cy 已含 MARGIN_PT，使用 (cx-MARGIN_PT) 而非 mp+cx
            px = int(mp + (cx - MARGIN_PT) * sx)
            py = int(mp + (ph_pt - cy - MARGIN_PT) * sy)
            dr = p2p(CHOICE_CIRCLE_RADIUS * CH_DETECT)
            fills.append((opt, cfill(norm, px, py, dr)))
        best = max(fills, key=lambda x: x[1])
        choices.append(best[0] if best[1] > 0.35 else "?")
    return choices

def crop_fill_region(gray, pw_pt, ph_pt, fi, nc, is_back=False):
    """裁切填空区域。坐标与 generate_sheet.py 精确匹配。"""
    mp = p2p(MARGIN_PT); h, w = gray.shape[:2]
    cw, ch = pw_pt - 2*MARGIN_PT, ph_pt - 2*MARGIN_PT
    sx = (w - 2*mp) / cw; sy = (h - 2*mp) / ch

    if is_back:
        if nc > 0:
            n_choice_rows = nc // CHOICE_COLS_PER_ROW + 1
            y0_pt = ph_pt - MARGIN_PT - 48 - n_choice_rows * CHOICE_ROW_GAP - 30
        else:
            y0_pt = ph_pt - MARGIN_PT - 48
    else:
        n_rows = max(1, (nc + CHOICE_COLS_PER_ROW - 1) // CHOICE_COLS_PER_ROW)
        y0_pt = ph_pt - MARGIN_PT - 38 - 78 - (n_rows + 1) * CHOICE_ROW_GAP - 30
    ly_pt = y0_pt - 10 - fi * FILL_LINE_GAP
    y_top = int(mp + (ph_pt - MARGIN_PT - (ly_pt + 15)) * sy)
    y_bot = int(mp + (ph_pt - MARGIN_PT - (ly_pt - 15)) * sy)
    x0 = int(mp + (30) * sx)
    x1 = int(mp + (pw_pt - 2*MARGIN_PT) * sx)
    y0, y1 = max(0, min(y_top, y_bot)), min(h, max(y_top, y_bot))
    x0, x1 = max(0, min(x0, x1)), min(w, max(x0, x1))
    if x0 >= x1 or y0 >= y1:
        return None
    return gray[y0:y1, x0:x1]

def crop_fill_segments(gray, pw_pt, ph_pt, fi, nc, content, is_back=False):
    """多空填空题：按____位置比例分割填空区域为多个子区域"""
    region = crop_fill_region(gray, pw_pt, ph_pt, fi, nc, is_back)
    if region is None:
        return []
    blank_count = content.count("____")
    if blank_count <= 1:
        return [region]
    h, w = region.shape
    segments = []
    for i in range(blank_count):
        x_start = int(w * i / blank_count)
        x_end = int(w * (i + 1) / blank_count)
        seg = region[:, x_start:x_end]
        if seg.shape[1] > 5:
            segments.append(seg)
    return segments

def semantic_score(ocr_text, correct_answer):
    if not ocr_text or not correct_answer:
        return 0.0, 0.0, 0.0
    if ocr_text.strip() == correct_answer.strip():
        return 1.0, 1.0, 1.0
    ocr_words = set(jieba.cut(ocr_text))
    ans_words = set(jieba.cut(correct_answer))
    if not ans_words:
        return 0.0, 0.0, 0.0
    jaccard = len(ocr_words & ans_words) / len(ans_words)
    edit_sim = SequenceMatcher(None, ocr_text, correct_answer).ratio()
    combined = 0.4 * jaccard + 0.6 * edit_sim
    conf = max(jaccard, edit_sim)
    if combined > 0.85:
        score = 1.0
    elif combined > 0.65:
        score = 0.5
    else:
        score = 0.0
    return score, combined, conf

def _config_hash(config, scan_path):
    h = hashlib.md5()
    h.update(json.dumps(config, sort_keys=True).encode())
    h.update(str(os.path.getsize(scan_path)).encode())
    return h.hexdigest()[:8]

def run(scan_path, config, output_path, resume=False, duplex=False, template=False):
    # === 输入校验 ===
    if "questions" not in config:
        print("❌ 配置文件缺少 questions 字段")
        sys.exit(1)
    doc = fitz.open(scan_path)
    choice_qs = [q for q in config["questions"] if q["type"] == "choice"]
    fill_qs = [q for q in config["questions"] if q["type"] == "fill"]
    NC, NF = len(choice_qs), len(fill_qs)
    ps = config.get("paper_size", "A4")
    pw_pt, ph_pt = PAPER_SIZES[ps]
    total_score = sum(q["score"] for q in config["questions"])
    if duplex and "back_questions" in config:
        total_score += sum(q["score"] for q in config["back_questions"])
    results = []
    start_page = 0
    last_sid = ""
    pending_result = None  # 双面模式：暂存正面结果，等背面合并

    # 双面模式：分别提取正反面题目
    if duplex:
        front_cq = [q for q in choice_qs if q.get("side", "front") != "back"]
        front_fq = [q for q in fill_qs if q.get("side", "front") != "back"]
        back_cq = [q for q in choice_qs if q.get("side", "") == "back"]
        back_fq = [q for q in fill_qs if q.get("side", "") == "back"]
        if "back_questions" in config:
            back_all = config["back_questions"]
            back_cq = [q for q in back_all if q["type"] == "choice"]
            back_fq = [q for q in back_all if q["type"] == "fill"]
            front_cq = choice_qs
            front_fq = fill_qs
    else:
        front_cq, front_fq = choice_qs, fill_qs
        back_cq, back_fq = [], []

    ch = _config_hash(config, scan_path)
    progress_path = output_path.replace(".json", ".progress.json")

    if resume and os.path.exists(progress_path):
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                prog = json.load(f)
            if prog.get("config_hash") == ch and prog.get("total_pages") == len(doc):
                results = prog.get("results", [])
                start_page = prog.get("done_pages", 0)
                print(f"🔄 恢复模式：已完成 {start_page}/{len(doc)} 页，从第{start_page+1}页继续")
            else:
                print("⚠️ 配置已变更，忽略旧进度文件，重新开始")
        except Exception:
            print("⚠️ 进度文件损坏，重新开始")

    ocr_engine = None
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr_engine = RapidOCR()
        print("RapidOCR 已加载")
    except ImportError:
        print("⚠️ RapidOCR 未安装，填空题跳过OCR")

    # 混淆词典（审阅标记）
    try:
        from confusion_dict import check_confusion
        _has_cdict = True
    except ImportError:
        check_confusion = None
        _has_cdict = False

    for pi in range(start_page, len(doc)):
        page = doc[pi]
        is_back = duplex and (pi % 2 == 1)
        side_label = " [背面]" if is_back else ""

        mat = fitz.Matrix(DPI/72, DPI/72)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        print(f"\n第{pi+1}页{side_label}: {gray.shape[1]}x{gray.shape[0]}")

        # --- 模板模式：角标检测 + 透视矫正 ---
        paper_type = config.get("paper_type", "answer_sheet")
        if paper_type == "template":
            markers = detect_markers(gray)
            if len(markers) != 4:
                print("⚠️ 未检测到4个角标，跳过本页")
                continue
            gray = warp_perspective(gray, markers)
            mp = p2p(MARGIN_PT)
            h, w = gray.shape[:2]
            cw, ch = pw_pt - 2*MARGIN_PT, ph_pt - 2*MARGIN_PT
            sx = (w - 2*mp) / cw
            sy = (h - 2*mp) / ch
            print(f"    模板矫正: {w}x{h}")

        # 背面：跳过QR和学号检测，复用正面学号
        if is_back:
            sid = last_sid
            ch_qs, fl_qs = back_cq, back_fq
            print(f"    学号: {sid} (复用正面)")
        else:
            det = cv2.QRCodeDetector()
            qdata, _, _ = det.detectAndDecode(gray)
            if qdata:
                print(f"    QR: {qdata}")
            sid = read_sid(gray, pw_pt, ph_pt)
            last_sid = sid
            ch_qs, fl_qs = front_cq, front_fq
            print(f"    学号: {sid}")

        ChN, FlN = len(ch_qs), len(fl_qs)

        answers = read_choice(gray, pw_pt, ph_pt, ChN)
        cc, sc = 0, 0
        cdetails = []
        for qi, q in enumerate(ch_qs):
            ua = answers[qi] if qi < len(answers) else "?"
            ok = (ua == q["answer"])
            s = q["score"] if ok else 0
            if ok: cc += 1; sc += s
            cdetails.append({"id": q["id"], "user": ua, "correct": q["answer"],
                            "score": s, "max": q["score"], "kp": q["knowledge_point"]})
        cm = sum(q["score"] for q in ch_qs)
        print(f"    选择题: {cc}/{ChN} 正确, 得分 {sc}/{cm}")
        for d in cdetails:
            mk = "✓" if d["user"] == d["correct"] else "✗"
            print(f"      Q{d['id']}: {mk} 答{d['user']}→应{d['correct']} ({d['score']}分)")

        fdetails = []
        fscore = 0

        for fi, q in enumerate(fl_qs):
            answer = q.get("answer", "")
            content = q.get("content", "")
            blank_count = content.count("____")
            is_multi = isinstance(answer, list) and blank_count > 1 and len(answer) == blank_count

            if is_multi:
                # 多空题：分割区域 → 每空独立OCR+判分
                segments = crop_fill_segments(gray, pw_pt, ph_pt, fi, ChN, content, is_back)
                blank_scores = []
                blank_texts = []
                for bi, seg in enumerate(segments):
                    if bi >= len(answer):
                        break
                    if ocr_engine:
                        result, _ = ocr_engine(seg)
                        ocr_txt = "".join([r[1] for r in result]).strip() if result else ""
                        ocr_conf = max(r[2] for r in result) if result else 0.0
                    else:
                        ocr_txt, ocr_conf = "", 0.0
                    blank_texts.append(ocr_txt)
                    score_ratio, sim, conf = semantic_score(ocr_txt, answer[bi])
                    per_blank_score = q["score"] / blank_count
                    awarded = round(per_blank_score * score_ratio, 1) if score_ratio > 0 else 0
                    blank_scores.append({"text": ocr_txt, "score": awarded, "max": round(per_blank_score, 1),
                                          "similarity": round(sim, 3), "confidence": round(max(conf, ocr_conf), 3)})

                total_awarded = round(sum(b["score"] for b in blank_scores), 1)
                fd = {"id": q["id"], "ocr_text": " | ".join(bt for bt in blank_texts),
                      "correct": " | ".join(str(a) for a in answer),
                      "score": total_awarded, "max": q["score"],
                      "kp": q.get("knowledge_point", ""),
                      "similarity": round(float(np.mean([b["similarity"] for b in blank_scores])), 3) if blank_scores else 0,
                      "confidence": round(float(np.mean([b["confidence"] for b in blank_scores])), 3) if blank_scores else 0,
                      "status": "ocr_done", "blanks": blank_scores}
            else:
                # 单空题（保持原有逻辑）
                ans_text = answer[0] if isinstance(answer, list) else answer
                crop = crop_fill_region(gray, pw_pt, ph_pt, fi, ChN, is_back)
                if crop is None:
                    fdetails.append({"id": q["id"], "ocr_text": "", "correct": str(ans_text),
                                    "score": 0, "max": q["score"], "kp": q.get("knowledge_point", ""),
                                    "similarity": 0, "confidence": 0, "status": "crop_failed"})
                    continue

                if ocr_engine:
                    result, _ = ocr_engine(crop)
                    ocr_txt = "".join([r[1] for r in result]).strip() if result else ""
                    ocr_conf = max(r[2] for r in result) if result else 0.0
                else:
                    ocr_txt, ocr_conf = "", 0.0

                review_flag = False
                ocr_suggestion = ""
                if _has_cdict and ocr_txt and ocr_txt != str(ans_text):
                    confusion = check_confusion(ocr_txt, str(ans_text), q.get("knowledge_point", ""))
                    if confusion and confusion["confidence"] >= 0.7:
                        review_flag = True
                        ocr_suggestion = confusion.get("suggested_correction", "")

                score_ratio, sim, conf = semantic_score(ocr_txt, str(ans_text))
                awarded = round(q["score"] * score_ratio, 1) if score_ratio > 0 else 0

                fd = {"id": q["id"], "ocr_text": ocr_txt, "correct": str(ans_text),
                      "score": awarded, "max": q["score"], "kp": q.get("knowledge_point", ""),
                      "similarity": round(sim, 3), "confidence": round(max(conf, ocr_conf), 3),
                      "status": "ocr_done" if ocr_txt else "ocr_empty"}
                if review_flag:
                    fd["review_flag"] = True
                    fd["ocr_suggestion"] = ocr_suggestion
            fdetails.append(fd)
            fscore += awarded

        fm = sum(q["score"] for q in fl_qs)
        print(f"    填空题: 得分 {fscore}/{fm}")
        for d in fdetails:
            status_icon = "✓" if d["score"] >= d["max"] * 0.8 else ("△" if d["score"] > 0 else "✗")
            review_tag = " 🔍待审" if d.get("review_flag") else ""
            suggestion = f" (建议={d['ocr_suggestion']})" if d.get("ocr_suggestion") else ""
            print(f"      Q{d['id']}: {status_icon} OCR='{d['ocr_text']}' → 答案='{d['correct']}' "
                  f"相似度={d['similarity']} 得分={d['score']}{review_tag}{suggestion}")

        # 构建本页结果
        page_result = {
            "page": pi + 1, "student_id": sid, "side": "back" if is_back else "front",
            "choice_answers": answers, "choice_score": sc, "choice_max": cm,
            "choice_details": cdetails, "fill_details": fdetails,
            "fill_score": round(fscore, 1), "fill_max": fm,
            "total_scored": sc + fscore, "total_max": total_score,
        }

        # 双面模式：正面暂存，背面合并后加入
        if duplex and not is_back:
            pending_result = page_result  # 暂存正面
        elif duplex and is_back and pending_result:
            # 合并正反面
            merged = pending_result
            merged["choice_score"] += sc
            merged["fill_score"] += round(fscore, 1)
            merged["total_scored"] += sc + fscore
            merged["choice_answers"].extend(answers)
            merged["choice_details"].extend(cdetails)
            merged["fill_details"].extend(fdetails)
            merged["choice_max"] += cm
            merged["fill_max"] += fm
            merged["page"] = f"{pending_result['page']},{pi+1}"
            merged.pop("side", None)
            results.append(merged)
            pending_result = None
        else:
            results.append(page_result)  # 单面模式直接加入

        # 增量保存
        prog = {
            "config_hash": ch,
            "total_pages": len(doc),
            "done_pages": pi + 1,
            "results": results,
        }
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(prog, f, ensure_ascii=False)

    # 双面模式：最后一面如果是正面且没有背面配对，直接加入
    if pending_result:
        results.append(pending_result)

    summary = {
        "exam_name": config["exam_name"], "total_students": len(results),
        "choice_avg": round(float(np.mean([r["choice_score"] for r in results])), 1) if results else 0,
        "fill_avg": round(float(np.mean([r["fill_score"] for r in results])), 1) if results else 0,
        "results": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    if os.path.exists(progress_path):
        os.remove(progress_path)

    print(f"\n✅ 判分完成 → {output_path}")
    print(f"   考生数: {len(results)}")
    if results:
        print(f"   选择题均分: {summary['choice_avg']}/{results[0]['choice_max']}")
        print(f"   填空题均分: {summary['fill_avg']}/{results[0]['fill_max']}")

def main():
    p = argparse.ArgumentParser(description="阅卷无忧 v9")
    p.add_argument("--config", required=True)
    p.add_argument("--scan", required=True)
    p.add_argument("--output", default="results.json")
    p.add_argument("--resume", action="store_true", help="从中断处恢复")
    p.add_argument("--duplex", action="store_true", help="双面扫描模式(正反面配对)")
    p.add_argument("--template", action="store_true", help="模板模式(角标检测+透视矫正)")
    a = p.parse_args()
    with open(a.config, encoding="utf-8") as f:
        c = json.load(f)
    run(a.scan, c, a.output, resume=a.resume, duplex=a.duplex, template=a.template)

if __name__ == "__main__":
    main()
