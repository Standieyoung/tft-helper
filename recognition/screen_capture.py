"""屏幕截图与游戏区域定位"""

import json
import numpy as np
from pathlib import Path
from PIL import Image

try:
    import mss
except ImportError:
    mss = None


PROJECT_ROOT = Path(__file__).parent.parent
CALIBRATION_FILE = PROJECT_ROOT / "config_screen.json"

# 基于 1920x1080 分辨率的默认区域坐标 (x, y, w, h)
REGIONS_1080P = {
    "shop": (485, 1010, 950, 60),
    "shop_slot_0": (485, 1010, 190, 60),
    "shop_slot_1": (675, 1010, 190, 60),
    "shop_slot_2": (865, 1010, 190, 60),
    "shop_slot_3": (1055, 1010, 190, 60),
    "shop_slot_4": (1245, 1010, 190, 60),

    "my_board": (340, 410, 1240, 290),
    "bench": (340, 730, 1240, 70),
    "round_info": (750, 5, 200, 30),
    "level_info": (370, 870, 80, 50),
    "gold_info": (870, 870, 60, 40),
    "hp_info": (100, 5, 160, 30),
    "opponent_board": (340, 410, 1240, 290),

    "augment_choice_0": (400, 230, 280, 450),
    "augment_choice_1": (780, 230, 280, 450),
    "augment_choice_2": (1160, 230, 280, 450),

    "minimap": (0, 300, 100, 400),
}


def load_calibrated_regions() -> dict[str, tuple] | None:
    """从 config_screen.json 加载校准后的区域坐标"""
    if not CALIBRATION_FILE.exists():
        return None
    try:
        data = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
        regions = {}
        for key, val in data.items():
            if key in ("raw_points", "screen_resolution"):
                continue
            if isinstance(val, list) and len(val) == 4:
                regions[key] = tuple(val)
        return regions if regions else None
    except (json.JSONDecodeError, OSError):
        return None


def scale_region(region: tuple, game_w: int, game_h: int) -> tuple:
    """根据实际分辨率缩放区域坐标"""
    x, y, w, h = region
    sx = game_w / 1920
    sy = game_h / 1080
    return (int(x * sx), int(y * sy), int(w * sx), int(h * sy))


class ScreenCapture:
    """屏幕截图管理"""

    def __init__(self, game_resolution: tuple = (1920, 1080)):
        if mss is None:
            raise ImportError("请安装 mss: pip install mss")
        self.sct = mss.mss()
        self.game_w, self.game_h = game_resolution
        self._monitor = None

        calibrated = load_calibrated_regions()
        if calibrated:
            self.regions = calibrated
            self._use_calibrated = True
        else:
            self.regions = REGIONS_1080P
            self._use_calibrated = False

    def find_game_window(self) -> dict | None:
        """
        查找云顶之弈游戏窗口

        macOS 上 League 客户端窗口名为 "League of Legends"
        TODO: 使用 pyobjc / Quartz 获取窗口位置
        目前使用主显示器全屏截图
        """
        monitors = self.sct.monitors
        if len(monitors) > 1:
            self._monitor = monitors[1]
        return self._monitor

    def capture_full(self) -> np.ndarray:
        """截取完整游戏画面"""
        monitor = self._monitor or self.sct.monitors[1]
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        return img[:, :, :3]

    def capture_region(self, region_name: str) -> np.ndarray | None:
        """截取指定区域"""
        region = self.regions.get(region_name)
        if not region:
            return None

        if self._use_calibrated:
            x, y, w, h = region
        else:
            x, y, w, h = scale_region(region, self.game_w, self.game_h)

        monitor = self._monitor or self.sct.monitors[1]
        area = {
            "left": monitor["left"] + x,
            "top": monitor["top"] + y,
            "width": w,
            "height": h,
        }
        screenshot = self.sct.grab(area)
        img = np.array(screenshot)
        return img[:, :, :3]

    def capture_shop_slots(self) -> list[np.ndarray]:
        """截取商店 5 个英雄槽位"""
        slots = []
        for i in range(5):
            img = self.capture_region(f"shop_slot_{i}")
            if img is not None:
                slots.append(img)
        return slots

    def capture_augment_choices(self) -> list[np.ndarray]:
        """截取强化选择 3 个选项"""
        choices = []
        for i in range(3):
            img = self.capture_region(f"augment_choice_{i}")
            if img is not None:
                choices.append(img)
        return choices
