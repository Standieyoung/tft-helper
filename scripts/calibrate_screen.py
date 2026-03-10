"""
屏幕坐标校准工具

使用方法:
1. 启动云顶之弈游戏，进入一局对战
2. 运行此脚本: python scripts/calibrate_screen.py
3. 脚本会截取全屏，然后让你点击关键位置来校准

校准的区域:
- 商店第1个槽位的左上角和右下角
- 棋盘区域的左上角和右下角
- 回合信息位置
- 金币/等级/血量位置
"""

import sys
import json
from pathlib import Path

import cv2
import numpy as np

try:
    import mss
except ImportError:
    print("请安装 mss: pip install mss")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent
CALIBRATION_FILE = PROJECT_ROOT / "config_screen.json"

# 需要校准的区域及说明
CALIBRATION_STEPS = [
    ("shop_left_top", "请点击【商店第1个英雄】的左上角"),
    ("shop_right_bottom", "请点击【商店第5个英雄】的右下角"),
    ("board_left_top", "请点击【己方棋盘】的左上角"),
    ("board_right_bottom", "请点击【己方棋盘】的右下角"),
    ("bench_left_top", "请点击【备战席】的左上角"),
    ("bench_right_bottom", "请点击【备战席】的右下角"),
    ("round_pos", "请点击【回合数字】的位置 (如 3-2)"),
    ("level_pos", "请点击【等级数字】的位置"),
    ("gold_pos", "请点击【金币数字】的位置"),
    ("hp_pos", "请点击【血量数字】的位置"),
]


class Calibrator:
    def __init__(self):
        self.points = {}
        self.current_step = 0
        self.screenshot = None
        self.display_img = None
        self.window_name = "TFT 屏幕校准 (按 ESC 退出, R 重新截图)"

    def capture_screen(self):
        """截取屏幕"""
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # 主显示器
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            self.screenshot = img[:, :, :3]  # 去掉 alpha
            self.screen_w = monitor["width"]
            self.screen_h = monitor["height"]
            print(f"屏幕分辨率: {self.screen_w} x {self.screen_h}")

    def mouse_callback(self, event, x, y, flags, param):
        """鼠标点击回调"""
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.current_step < len(CALIBRATION_STEPS):
                key, desc = CALIBRATION_STEPS[self.current_step]
                # 由于显示的图像可能被缩放了，需要还原到原始坐标
                scale = self.screenshot.shape[1] / self.display_img.shape[1]
                real_x = int(x * scale)
                real_y = int(y * scale)
                self.points[key] = (real_x, real_y)
                print(f"  ✓ {key}: ({real_x}, {real_y})")

                # 在图上画标记
                cv2.circle(self.display_img, (x, y), 5, (0, 255, 0), -1)
                cv2.putText(self.display_img, key, (x + 10, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                cv2.imshow(self.window_name, self.display_img)

                self.current_step += 1
                if self.current_step < len(CALIBRATION_STEPS):
                    next_key, next_desc = CALIBRATION_STEPS[self.current_step]
                    print(f"\n步骤 {self.current_step + 1}/{len(CALIBRATION_STEPS)}: {next_desc}")
                else:
                    print("\n校准完成!")

    def run(self):
        """运行校准"""
        print("=" * 50)
        print("  TFT 屏幕坐标校准工具")
        print("=" * 50)
        print("\n请确保云顶之弈游戏正在运行并处于对战界面")
        print("按任意键开始截图...\n")
        input()

        self.capture_screen()

        # 缩放显示 (避免图片太大)
        max_display_w = 1280
        scale = min(1.0, max_display_w / self.screenshot.shape[1])
        display_h = int(self.screenshot.shape[0] * scale)
        display_w = int(self.screenshot.shape[1] * scale)
        self.display_img = cv2.resize(self.screenshot, (display_w, display_h))

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

        first_key, first_desc = CALIBRATION_STEPS[0]
        print(f"步骤 1/{len(CALIBRATION_STEPS)}: {first_desc}")

        cv2.imshow(self.window_name, self.display_img)

        while True:
            key = cv2.waitKey(100) & 0xFF
            if key == 27:  # ESC
                print("已取消")
                break
            elif key == ord('r'):
                print("重新截图...")
                self.capture_screen()
                self.display_img = cv2.resize(self.screenshot, (display_w, display_h))
                cv2.imshow(self.window_name, self.display_img)
            elif self.current_step >= len(CALIBRATION_STEPS):
                break

        cv2.destroyAllWindows()

        if self.current_step >= len(CALIBRATION_STEPS):
            self._save_calibration()

    def _save_calibration(self):
        """保存校准结果并生成区域配置"""
        p = self.points

        # 从点击位置计算区域 (x, y, w, h)
        regions = {
            "screen_resolution": [self.screen_w, self.screen_h],
            "shop": [
                p["shop_left_top"][0], p["shop_left_top"][1],
                p["shop_right_bottom"][0] - p["shop_left_top"][0],
                p["shop_right_bottom"][1] - p["shop_left_top"][1],
            ],
            "my_board": [
                p["board_left_top"][0], p["board_left_top"][1],
                p["board_right_bottom"][0] - p["board_left_top"][0],
                p["board_right_bottom"][1] - p["board_left_top"][1],
            ],
            "bench": [
                p["bench_left_top"][0], p["bench_left_top"][1],
                p["bench_right_bottom"][0] - p["bench_left_top"][0],
                p["bench_right_bottom"][1] - p["bench_left_top"][1],
            ],
            "round_info": [p["round_pos"][0] - 50, p["round_pos"][1] - 15, 100, 30],
            "level_info": [p["level_pos"][0] - 30, p["level_pos"][1] - 20, 60, 40],
            "gold_info": [p["gold_pos"][0] - 30, p["gold_pos"][1] - 20, 60, 40],
            "hp_info": [p["hp_pos"][0] - 40, p["hp_pos"][1] - 15, 80, 30],
            "raw_points": {k: list(v) for k, v in p.items()},
        }

        # 计算商店的 5 个槽位
        shop_x, shop_y, shop_w, shop_h = regions["shop"]
        slot_w = shop_w // 5
        for i in range(5):
            regions[f"shop_slot_{i}"] = [shop_x + i * slot_w, shop_y, slot_w, shop_h]

        CALIBRATION_FILE.write_text(
            json.dumps(regions, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n校准配置已保存到: {CALIBRATION_FILE}")
        print("\n生成的区域配置:")
        for k, v in regions.items():
            if k not in ("raw_points", "screen_resolution"):
                print(f"  {k}: {v}")


if __name__ == "__main__":
    calibrator = Calibrator()
    calibrator.run()
