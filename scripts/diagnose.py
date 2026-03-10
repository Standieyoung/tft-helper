"""
屏幕识别诊断工具

在游戏对局中运行此脚本，它会：
1. 截取全屏并标注每个识别区域的位置
2. 分别截取每个区域并尝试 OCR 识别
3. 把所有截图保存到 debug_output/ 目录

用法:
    python scripts/diagnose.py

检查 debug_output/ 目录下的图片:
- full_annotated.png  → 全屏截图 + 区域标注框
- region_*.png        → 每个区域的截图
如果标注框没有覆盖到游戏的正确位置，需要校准:
    python main.py --calibrate
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "debug_output"

import cv2
import numpy as np
import re

from recognition.screen_capture import ScreenCapture, REGIONS_1080P, scale_region

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


REGION_COLORS = {
    "shop":       (0, 255, 0),
    "my_board":   (255, 0, 0),
    "bench":      (0, 255, 255),
    "round_info": (255, 255, 0),
    "level_info": (0, 165, 255),
    "gold_info":  (0, 215, 255),
    "hp_info":    (0, 0, 255),
}


def try_ocr(image: np.ndarray, label: str) -> str:
    """对一个区域截图尝试多种 OCR 预处理"""
    if not HAS_OCR:
        return "(pytesseract 未安装)"

    h, w = image.shape[:2]
    if w < 100 or h < 40:
        scale = max(3, 120 // max(w, 1))
        image = cv2.resize(image, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    methods = {}

    for t in (140, 160, 180, 200):
        _, binary = cv2.threshold(gray, t, 255, cv2.THRESH_BINARY)
        methods[f"thresh_{t}"] = binary

    _, inv = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)
    methods["inverted"] = inv

    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    methods["otsu"] = otsu

    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 11, 2)
    methods["adaptive"] = adaptive

    yellow = cv2.inRange(hsv, np.array([15, 80, 150]), np.array([40, 255, 255]))
    methods["yellow_mask"] = yellow

    bright = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 255, 255]))
    methods["bright_mask"] = bright

    results = {}
    config = "--psm 7 -c tessedit_char_whitelist=0123456789-/"
    for name, img in methods.items():
        try:
            text = pytesseract.image_to_string(img, lang="eng", config=config).strip()
            if text:
                results[name] = text
        except Exception:
            pass

        # 保存每种预处理结果
        out_path = OUTPUT_DIR / f"ocr_{label}_{name}.png"
        cv2.imwrite(str(out_path), img)

    return results


def main():
    print("=" * 50)
    print("  TFT 屏幕识别诊断工具")
    print("  请确保游戏正在对局中!")
    print("=" * 50)

    OUTPUT_DIR.mkdir(exist_ok=True)

    sc = ScreenCapture()
    sc.find_game_window()
    debug = sc.get_debug_info()

    print(f"\n[屏幕信息]")
    print(f"  显示器: {debug['monitor']}")
    print(f"  截图分辨率: {debug['game_resolution'][0]} x {debug['game_resolution'][1]}")
    print(f"  使用校准配置: {debug['use_calibrated']}")
    print(f"  缩放比: X={debug['scale_x']}, Y={debug['scale_y']}")

    # 截全屏
    full = sc.capture_full()
    actual_h, actual_w = full.shape[:2]
    print(f"  实际截图像素: {actual_w} x {actual_h}")

    if actual_w != 1920 or actual_h != 1080:
        print(f"\n  ⚠️  分辨率不是 1920x1080!")
        print(f"  默认区域坐标是按 1920x1080 设计的，会自动缩放。")
        print(f"  如果缩放后仍不准确，请运行: python main.py --calibrate")

    # 保存全屏原图
    cv2.imwrite(str(OUTPUT_DIR / "full_raw.png"), full)

    # 在全屏截图上标注区域
    annotated = full.copy()
    key_regions = ["shop", "my_board", "bench", "round_info",
                   "level_info", "gold_info", "hp_info"]

    print(f"\n[区域诊断]")
    for name in key_regions:
        scaled = debug["scaled_regions"].get(name)
        if not scaled:
            print(f"  {name}: 未找到区域定义")
            continue

        x, y, w, h = scaled
        in_bounds = (x >= 0 and y >= 0 and
                     x + w <= actual_w and
                     y + h <= actual_h)
        status = "✓ 正常" if in_bounds else "✗ 超出屏幕!"

        color = REGION_COLORS.get(name, (200, 200, 200))
        cv2.rectangle(annotated, (x, y), (min(x + w, actual_w - 1), min(y + h, actual_h - 1)), color, 2)
        cv2.putText(annotated, name, (x + 2, max(y - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        print(f"  {name}: ({x}, {y}, {w}, {h}) {status}")

    # 保存标注图
    cv2.imwrite(str(OUTPUT_DIR / "full_annotated.png"), annotated)

    # 逐个区域截取 + OCR 测试
    ocr_regions = ["round_info", "level_info", "gold_info", "hp_info"]

    print(f"\n[OCR 识别测试]")
    for name in ocr_regions:
        region_img = sc.capture_region(name)
        if region_img is None or region_img.size == 0:
            print(f"  {name}: 截取失败 (可能超出屏幕)")
            continue

        # 保存原始区域截图
        cv2.imwrite(str(OUTPUT_DIR / f"region_{name}.png"), region_img)
        print(f"  {name}: 截取 {region_img.shape[1]}x{region_img.shape[0]}")

        results = try_ocr(region_img, name)
        if isinstance(results, str):
            print(f"    {results}")
        elif results:
            for method, text in results.items():
                has_digit = "✓" if re.search(r"\d", text) else " "
                print(f"    {has_digit} [{method}]: \"{text}\"")
        else:
            print(f"    所有方法均未识别到文字")

    # 截取非 OCR 区域
    for name in ["shop", "my_board", "bench"]:
        region_img = sc.capture_region(name)
        if region_img is not None and region_img.size > 0:
            cv2.imwrite(str(OUTPUT_DIR / f"region_{name}.png"), region_img)

    print(f"\n[输出文件]")
    print(f"  目录: {OUTPUT_DIR}")
    for f in sorted(OUTPUT_DIR.iterdir()):
        size_kb = f.stat().st_size / 1024
        print(f"    {f.name} ({size_kb:.0f} KB)")

    print(f"\n请检查 debug_output/ 下的图片:")
    print(f"  1. full_annotated.png — 区域标注框是否对齐游戏界面?")
    print(f"  2. region_*.png — 各区域截图是否截到了正确内容?")
    print(f"  3. ocr_*_*.png — 哪种预处理方法的黑白图最清晰?")
    print(f"\n如果标注框位置不对，运行: python main.py --calibrate")


if __name__ == "__main__":
    main()
