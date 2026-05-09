#!/usr/bin/env python3
"""阅卷无忧 - 答题卡生成器 v2（修复学号圈重叠）"""
import argparse, json, sys, io, tempfile, os, re
from reportlab.lib.pagesizes import A4, A3
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import qrcode

PAPER_SIZES = {"A4": A4, "B4": (709, 1006), "8开": (787, 1092), "A3": A3}

# 布局参数（修：CIRCLE_GAP=6, CIRCLE_RADIUS=3, DIGIT_GAP=36 防止数字间圈位重叠）
CORNER_SIZE = 28; MARGIN = 36; QR_SIZE = 80
DIGIT_WIDTH = 28; DIGIT_GAP = 36; CIRCLE_RADIUS = 3; CIRCLE_GAP = 6
CHOICE_CIRCLE_RADIUS = 7; CHOICE_OPTION_GAP = 16; CHOICE_ROW_GAP = 48; CHOICE_COLS_PER_ROW = 5
FONT_NORMAL = 10; FONT_SMALL = 7; FONT_TINY = 6

def draw_corners(c, pw, ph):
    c.setFillColorRGB(0,0,0)
    for x,y in [(MARGIN,ph-MARGIN-CORNER_SIZE),(pw-MARGIN-CORNER_SIZE,ph-MARGIN-CORNER_SIZE),
                (MARGIN,MARGIN),(pw-MARGIN-CORNER_SIZE,MARGIN)]:
        c.rect(x,y,CORNER_SIZE,CORNER_SIZE,fill=1,stroke=0)

def gen_qr(exam_name, ps):
    data=f"YJWY|{exam_name}|{ps}"
    qr=qrcode.QRCode(box_size=4,border=2); qr.add_data(data); qr.make(fit=True)
    img=qr.make_image(fill_color="black",back_color="white")
    tmp=tempfile.NamedTemporaryFile(suffix=".png",delete=False); img.save(tmp.name,format="PNG"); tmp.close()
    return tmp.name

def draw_sid(c,x0,y0):
    c.setFont("Helvetica",FONT_TINY); c.setFillColorRGB(0,0,0)
    c.drawString(x0,y0+20,"学号填涂区")
    for di in range(8):
        dx=x0+di*(DIGIT_WIDTH+DIGIT_GAP)
        for v in range(10):
            if v<5: cx,cy=dx+v*CIRCLE_GAP, y0-5
            else: cx,cy=dx+(v-5)*CIRCLE_GAP, y0-5-CIRCLE_GAP-2
            c.circle(cx+CIRCLE_RADIUS,cy+CIRCLE_RADIUS,CIRCLE_RADIUS)
            c.setFont("Helvetica",FONT_TINY)
            c.drawString(cx+CIRCLE_RADIUS-2,cy-2,str(v))

def draw_choice(c, qs, x0, y0, pw):
    c.setFont("Helvetica",FONT_SMALL); c.setFillColorRGB(0,0,0)
    c.drawString(x0,y0+10,"选择题")
    cw=(pw-2*MARGIN)/CHOICE_COLS_PER_ROW; cr=CHOICE_CIRCLE_RADIUS; og=CHOICE_OPTION_GAP
    for qi,q in enumerate(qs):
        r,c_=qi//CHOICE_COLS_PER_ROW,qi%CHOICE_COLS_PER_ROW
        rx,ry=x0+c_*cw, y0-15-r*CHOICE_ROW_GAP
        c.drawString(rx,ry+8,f"{q['id']}.")
        for oi,op in enumerate(["A","B","C","D","E"]):
            cx,cy=rx+20+oi*og, ry-4
            c.circle(cx,cy,cr); c.drawString(cx-2,cy-cr-8,op)

def draw_fill(c,fqs,x0,y0,pw):
    c.setFont("Helvetica",FONT_SMALL); c.setFillColorRGB(0,0,0)
    c.drawString(x0,y0+10,"填空题")
    lw=pw-2*MARGIN-30; lg=36
    for fi,q in enumerate(fqs):
        ly=y0-10-fi*lg; c.drawString(x0,ly+6,f"{q['id']}.")
        content=q.get("content","")
        blank_positions=[m.start() for m in re.finditer(r'_{2,}',content)]
        if len(blank_positions)>1:
            # 多空：按____在content中的位置比例分割横线
            total_chars=len(content)
            for bp in blank_positions:
                ratio=bp/total_chars
                seg_start=x0+22+int(lw*ratio)
                seg_width=max(30,int(lw/(len(blank_positions)+1)))
                c.line(seg_start,ly,seg_start+seg_width,ly)
        else:
            c.line(x0+22,ly,x0+22+lw,ly)

def generate(config, out, copies=1, duplex=False):
    ps=config.get("paper_size","A4"); pw,ph=PAPER_SIZES[ps]
    cq=[q for q in config["questions"] if q["type"]=="choice"]
    fq=[q for q in config["questions"] if q["type"]=="fill"]
    qp=gen_qr(config["exam_name"],ps)
    c=canvas.Canvas(out,pagesize=(pw,ph))

    # 双面模式：背面题目
    bcq, bfq = [], []
    if duplex:
        if "back_questions" in config:
            bcq=[q for q in config["back_questions"] if q["type"]=="choice"]
            bfq=[q for q in config["back_questions"] if q["type"]=="fill"]
        else:
            bcq=[q for q in cq if q.get("side","")=="back"]
            bfq=[q for q in fq if q.get("side","")=="back"]
            cq=[q for q in cq if q.get("side","front")!="back"]
            fq=[q for q in fq if q.get("side","front")!="back"]

    for _ in range(copies):
        # === 正面 ===
        draw_corners(c,pw,ph)
        c.drawImage(qp,pw-MARGIN-QR_SIZE-10,ph-MARGIN-QR_SIZE-10,width=QR_SIZE,height=QR_SIZE)
        c.setFont("Helvetica-Bold",14); c.setFillColorRGB(0,0,0)
        c.drawString(MARGIN+10,ph-MARGIN-20,config["exam_name"])
        c.setFont("Helvetica",FONT_NORMAL)
        iy=ph-MARGIN-38
        c.drawString(MARGIN+10,iy,f"科目: {config['subject']}    班级: {config['grade']}")
        c.drawString(MARGIN+10,iy-16,f"日期: {config['date']}    A/B卷: {config.get('ab_variant','A')}")
        draw_sid(c,MARGIN+10,iy-40)
        draw_choice(c,cq,MARGIN+10,iy-78,pw)
        draw_fill(c,fq,MARGIN+10,iy-78-(len(cq)//CHOICE_COLS_PER_ROW+1)*CHOICE_ROW_GAP-30,pw)

        if duplex and (bcq or bfq):
            c.showPage()
            # === 背面 ===
            draw_corners(c,pw,ph)
            c.setFont("Helvetica-Bold",12); c.setFillColorRGB(0.5,0.5,0.5)
            c.drawString(MARGIN+10,ph-MARGIN-20,f"{config['exam_name']}（背面）")
            c.setFont("Helvetica",FONT_NORMAL); c.setFillColorRGB(0,0,0)
            biy=ph-MARGIN-48
            if bcq:
                draw_choice(c,bcq,MARGIN+10,biy,pw)
                n_choice_rows=(len(bcq)//CHOICE_COLS_PER_ROW+1)
                fill_y=biy-n_choice_rows*CHOICE_ROW_GAP-30
            else:
                fill_y=biy
            if bfq:
                draw_fill(c,bfq,MARGIN+10,fill_y,pw)

        if _ < copies-1: c.showPage()
    c.save()
    label="双面答题卡" if duplex else "答题卡"
    print(f"✅ 已生成 {copies} 份{label} → {out}")

def main():
    p=argparse.ArgumentParser(description="阅卷无忧-答题卡生成器v2")
    p.add_argument("--config",required=True); p.add_argument("--copies",type=int,default=1)
    p.add_argument("--output",default="answer_sheets.pdf")
    p.add_argument("--duplex",action="store_true",help="双面答题卡")
    a=p.parse_args()
    with open(a.config,encoding="utf-8") as f: config=json.load(f)
    generate(config,a.output,a.copies,duplex=a.duplex)

if __name__=="__main__": main()
