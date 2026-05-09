#!/usr/bin/env python3
"""
template_matcher.py — 角标检测模块

检测扫描文档四角的标记方块，用于后续透视变换对齐。
CLI: python3 template_matcher.py --image <path>
输出：角标坐标列表的JSON
"""

import argparse
import json
import sys

import cv2
import numpy as np


def detect_markers(gray):
    """
    在灰度图中检测四个角标。

    算法：
    1. 二值化（THRESH_BINARY_INV），角标为黑色方块 → 变为白色前景
    2. 找轮廓
    3. 过滤面积 > 500 的轮廓，用 approxPolyDP 逼近四边形
    4. 计算每个四边形中心到图像四角的距离，取最近的 4 个
    5. 按 左上、右上、右下、左下 排序

    参数:
        gray: numpy.ndarray, 灰度图像

    返回:
        list of tuple: [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
                      四个角标的中心坐标，按左上/右上/右下/左下排列
    """
    h, w = gray.shape[:2]

    # --- 1. 二值化，黑色角标变成白色前景 ---
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

    # --- 2. 找轮廓 ---
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # --- 3. 过滤面积 > 500 的轮廓，逼近四边形 ---
    quads = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 500:
            continue

        # 轮廓周长，用于 approxPolyDP
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        # 只保留四边形
        if len(approx) == 4:
            # 计算四边形中心
            pts = approx.reshape(4, 2)
            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))
            quads.append((cx, cy))

    if len(quads) < 4:
        return []

    # --- 4. 选最接近图像四角的 4 个四边形 ---
    # 图像四角坐标
    corners = [(0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)]

    # 为每个图像角找最近的四边形中心
    used = set()
    result = []
    for ccorner in corners:
        best_idx = -1
        best_dist = float("inf")
        for i, q in enumerate(quads):
            if i in used:
                continue
            dist = (q[0] - ccorner[0]) ** 2 + (q[1] - ccorner[1]) ** 2
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx >= 0:
            used.add(best_idx)
            result.append(quads[best_idx])

    # 如果找到的不足 4 个，返回已有的
    if len(result) < 4:
        return result

    # --- 5. 返回格式: 左上, 右上, 右下, 左下 ---
    # result 已经按 corners 顺序排列：(0,0) 左上, (w-1,0) 右上, (w-1,h-1) 右下, (0,h-1) 左下
    return result


def warp_perspective(gray, markers, target_w=2481, target_h=3508):
    """
    根据四个角标进行透视变换，标准化到固定尺寸。

    参数:
        gray: numpy.ndarray, 灰度图像
        markers: list of tuple, 四个角标中心坐标 [(左上), (右上), (右下), (左下)]
        target_w: 目标宽度（像素），默认 A4@300DPI = 2481
        target_h: 目标高度（像素），默认 A4@300DPI = 3508

    返回:
        numpy.ndarray, 矫正后的灰度图像
    """
    if len(markers) != 4:
        return gray

    src_pts = np.array(markers, dtype=np.float32)
    dst_pts = np.array([
        [0, 0],
        [target_w - 1, 0],
        [target_w - 1, target_h - 1],
        [0, target_h - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(gray, M, (target_w, target_h))
    return warped


def generate_test_image(path, width=2480, height=3508, block_size=50, margin=50):
    """
    生成一张测试图片：
    - 白色背景
    - 四角各一个黑色方块（距边缘 margin px）
    - 中间写一些文字
    - 保存到 path
    """
    # 白色背景
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    # 四角黑色方块：左上、右上、右下、左下
    positions = [
        (margin, margin),                            # 左上
        (width - margin - block_size, margin),        # 右上
        (width - margin - block_size, height - margin - block_size),  # 右下
        (margin, height - margin - block_size),       # 左下
    ]

    for x, y in positions:
        cv2.rectangle(img, (x, y), (x + block_size, y + block_size), (0, 0, 0), -1)

    # 中间写文字
    text_lines = [
        "Template Matcher Test Image",
        "2480 x 3508 pixels",
        "Four corner markers: 50x50 black squares",
        "Margin from edges: 50px",
    ]
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 2
    thickness = 3
    line_spacing = 80

    # 计算文字总高度，居中放置
    total_text_h = len(text_lines) * line_spacing
    start_y = (height - total_text_h) // 2 + line_spacing // 2

    for i, line in enumerate(text_lines):
        text_size = cv2.getTextSize(line, font, font_scale, thickness)[0]
        text_x = (width - text_size[0]) // 2
        text_y = start_y + i * line_spacing
        cv2.putText(img, line, (text_x, text_y), font, font_scale, (0, 0, 0), thickness)

    cv2.imwrite(path, img)
    print(f"测试图片已保存: {path}")
    return img


def main():
    parser = argparse.ArgumentParser(description="角标检测")
    parser.add_argument("--image", required=True, help="输入图片路径")
    parser.add_argument("--generate", action="store_true", help="生成测试图片（保存到 --image 路径）")
    args = parser.parse_args()

    if args.generate:
        generate_test_image(args.image)
        return

    # 读取图片
    img = cv2.imread(args.image)
    if img is None:
        print(json.dumps({"error": f"无法读取图片: {args.image}"}))
        sys.exit(1)

    # 转灰度
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 检测角标
    markers = detect_markers(gray)

    # 输出 JSON
    print(json.dumps(markers, ensure_ascii=False))


if __name__ == "__main__":
    main()
