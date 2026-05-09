#!/usr/bin/env python3
"""阅卷无忧 - 模拟填涂 v4（+填空题手写模拟）"""
import argparse, json, random, fitz, subprocess, os

MARGIN_PT=36; DIGIT_WIDTH=28; DIGIT_GAP=36; CIRCLE_RADIUS=3; CIRCLE_GAP=6
CHOICE_CIRCLE_RADIUS=7; CHOICE_OPTION_GAP=16; CHOICE_ROW_GAP=48; CHOICE_COLS_PER_ROW=5
FILL_LINE_GAP=36
PAPER_SIZES={"A4":(595,842),"B4":(709,1006),"8开":(787,1092),"A3":(842,1190)}

# 模拟错误答案（同义词、错别字、部分正确）
WRONG_ANSWERS = {
    "惯性": ["惯性定律", "惯姓", "牛一", "惯性定率"],
    "牛顿": ["牛吨", "N", "牛", "牛頓"],
    "9.8": ["9.8N", "9.8n/kg", "10", "9.81"],
    "相反": ["相反方向", "相同", "反方向", "相返"],
    "压力": ["正压力", "压强", "重力", "拉力"],
}

def fcircle(page,cx_pt,cy_pt,r_pt,ph):
    fy=ph-cy_pt; s=page.new_shape()
    rect=fitz.Rect(cx_pt-r_pt,fy-r_pt,cx_pt+r_pt,fy+r_pt)
    s.draw_oval(rect); s.finish(fill=(0,0,0),color=(0,0,0)); s.commit()

def fill_sid(page,sid,pw,ph):
    iy=ph-MARGIN_PT-78; x0=MARGIN_PT+10
    for di,ch in enumerate(str(sid).zfill(8)):
        val=int(ch); dx=x0+di*(DIGIT_WIDTH+DIGIT_GAP)
        for v in range(10):
            if v<5: cx,cy=dx+v*CIRCLE_GAP, iy-5
            else: cx,cy=dx+(v-5)*CIRCLE_GAP, iy-5-CIRCLE_GAP-2
            if v==val:
                fcircle(page,cx+CIRCLE_RADIUS,cy+CIRCLE_RADIUS,CIRCLE_RADIUS*0.85,ph)

def fill_choice(page,sel,nq,pw,ph,is_back=False):
    if is_back:
        cy_=ph-MARGIN_PT-48  # 背面：对齐 generate_sheet biy=ph-84 的 choice 区域
    else:
        cy_=ph-MARGIN_PT-116
    cw=(pw-2*MARGIN_PT)/CHOICE_COLS_PER_ROW
    for qi,ans in enumerate(sel):
        if qi>=nq: break
        r,c=qi//CHOICE_COLS_PER_ROW,qi%CHOICE_COLS_PER_ROW
        rx,ry=MARGIN_PT+10+c*cw, cy_-15-r*CHOICE_ROW_GAP
        for oi,op in enumerate(["A","B","C","D","E"]):
            cx,cy=rx+20+oi*CHOICE_OPTION_GAP, ry-4
            if op==ans: fcircle(page,cx,cy,CHOICE_CIRCLE_RADIUS*0.85,ph)

def fill_blanks(page,fill_qs,n_choice,pw,ph,seed,is_back=False):
    """在填空题线上绘制模拟手写答案"""
    random.seed(seed)
    if is_back:
        if n_choice > 0:
            fill_y = ph - MARGIN_PT - 48 - (n_choice//CHOICE_COLS_PER_ROW + 1)*CHOICE_ROW_GAP - 30
        else:
            fill_y = ph - MARGIN_PT - 48
    else:
        choice_y = ph - MARGIN_PT - 116
        fill_y = choice_y - (n_choice//CHOICE_COLS_PER_ROW + 1)*CHOICE_ROW_GAP - 30
    x0 = MARGIN_PT + 10
    fontname = "china-s"
    fontsize = 20

    for fi, q in enumerate(fill_qs):
        y_pt = fill_y - 10 - fi * FILL_LINE_GAP
        fitz_y = ph - y_pt - 4
        fitz_x = x0 + 28

        answer = q.get("answer", "")
        content = q.get("content", "")
        blank_count = content.count("____")
        is_multi = isinstance(answer, list) and blank_count > 1 and len(answer) == blank_count

        if is_multi:
            # 多空：按比例放置每个答案
            line_w = pw - 2*MARGIN_PT - 30
            for bi in range(blank_count):
                ans = answer[bi]
                if random.random() < 0.8:
                    text = ans
                else:
                    wrong = WRONG_ANSWERS.get(ans, [ans + "X"])
                    text = random.choice(wrong)
                seg_x = fitz_x + int(line_w * bi / blank_count) + 4
                try:
                    page.insert_text((seg_x, fitz_y), text,
                                   fontname=fontname, fontsize=fontsize, color=(0,0,0))
                except Exception:
                    try:
                        page.insert_text((seg_x, fitz_y), text, fontsize=fontsize, color=(0,0,0))
                    except:
                        pass
        else:
            ans_text = answer[0] if isinstance(answer, list) else answer
            if random.random() < 0.8:
                text = ans_text
            else:
                wrong = WRONG_ANSWERS.get(ans_text, [ans_text + "X"])
                text = random.choice(wrong)

            try:
                page.insert_text((fitz_x, fitz_y), text,
                               fontname=fontname, fontsize=fontsize, color=(0,0,0))
            except Exception:
                try:
                    page.insert_text((fitz_x, fitz_y), text, fontsize=fontsize, color=(0,0,0))
                except:
                    pass


def sim(config,sp,op,seed=42,duplex=False):
    random.seed(seed); doc=fitz.open(sp)
    cq=[q for q in config["questions"] if q["type"]=="choice"]
    fq=[q for q in config["questions"] if q["type"]=="fill"]
    ps=config.get("paper_size","A4"); pw,ph=PAPER_SIZES[ps]

    # 双面模式：分离正反面题目（与 scan_and_grade.py 逻辑一致）
    if duplex:
        if "back_questions" in config:
            back_cq=[q for q in config["back_questions"] if q["type"]=="choice"]
            back_fq=[q for q in config["back_questions"] if q["type"]=="fill"]
        else:
            back_cq=[q for q in cq if q.get("side","")=="back"]
            back_fq=[q for q in fq if q.get("side","")=="back"]
            cq=[q for q in cq if q.get("side","front")!="back"]
            fq=[q for q in fq if q.get("side","front")!="back"]

    if duplex:
        n_students=len(doc)//2
        for si in range(n_students):
            fp=doc[si*2]; bp=doc[si*2+1]
            sid=str(random.randint(20240001,20240050))
            # 正面：正常填涂学号+选择+填空
            sel=[]
            for q in cq:
                if random.random()<0.8: sel.append(q["answer"])
                else: sel.append(random.choice([o for o in ["A","B","C","D","E"] if o!=q["answer"]]))
            fill_sid(fp,sid,pw,ph)
            fill_choice(fp,sel,len(cq),pw,ph)
            fill_blanks(fp,fq,len(cq),pw,ph,seed+si*100)
            # 背面：跳过学号，只填背面选择题+填空题
            bsel=[]
            for q in back_cq:
                if random.random()<0.8: bsel.append(q["answer"])
                else: bsel.append(random.choice([o for o in ["A","B","C","D","E"] if o!=q["answer"]]))
            fill_choice(bp,bsel,len(back_cq),pw,ph,is_back=True)
            fill_blanks(bp,back_fq,len(back_cq),pw,ph,seed+si*100+n_students*100,is_back=True)
            print(f"  第{si+1}份: 学号={sid} (正+背面)")
        pc=n_students
    else:
        for pi in range(len(doc)):
            p=doc[pi]; sid=str(random.randint(20240001,20240050))
            sel=[]
            for q in cq:
                if random.random()<0.8: sel.append(q["answer"])
                else: sel.append(random.choice([o for o in ["A","B","C","D","E"] if o!=q["answer"]]))
            fill_sid(p,sid,pw,ph)
            fill_choice(p,sel,len(cq),pw,ph)
            fill_blanks(p,fq,len(cq),pw,ph,seed+pi*100)
            print(f"  第{pi+1}份: 学号={sid}")
        pc=len(doc)
    doc.save(op); doc.close()
    print(f"✅ 已生成 {pc} 份模拟答卷 → {op}")

def main():
    p=argparse.ArgumentParser(description="模拟填涂v4")
    p.add_argument("--config",required=True); p.add_argument("--sheet",required=True)
    p.add_argument("--output",default="filled.pdf"); p.add_argument("--seed",type=int,default=42)
    p.add_argument("--copies",type=int,default=3)
    p.add_argument("--duplex",action="store_true",help="双面填涂模式")
    a=p.parse_args()
    with open(a.config,encoding="utf-8") as f: config=json.load(f)
    tmp=a.sheet.replace(".pdf","_tmp.pdf")
    cmd=["python3","generate_sheet.py","--config",a.config,"--copies",str(a.copies),"--output",tmp]
    if a.duplex: cmd.append("--duplex")
    subprocess.run(cmd,check=True)
    sim(config,tmp,a.output,a.seed,duplex=a.duplex); os.unlink(tmp)

if __name__=="__main__": main()
