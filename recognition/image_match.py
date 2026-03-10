"""图像模板匹配 - 用于识别英雄头像、装备图标等"""

import os
from pathlib import Path

import cv2
import numpy as np


ASSETS_DIR = Path(__file__).parent.parent / "assets"
CHAMPION_ICONS_DIR = ASSETS_DIR / "champions"
ITEM_ICONS_DIR = ASSETS_DIR / "items"


class TemplateMatcher:
    """基于 OpenCV 模板匹配的游戏元素识别"""

    def __init__(self, confidence: float = 0.85):
        self.confidence = confidence
        self._champion_templates: dict[str, np.ndarray] = {}
        self._item_templates: dict[str, np.ndarray] = {}

    def load_champion_icons(self):
        """加载英雄头像模板"""
        if not CHAMPION_ICONS_DIR.exists():
            print(f"[警告] 英雄头像目录不存在: {CHAMPION_ICONS_DIR}")
            return

        for f in CHAMPION_ICONS_DIR.iterdir():
            if f.suffix.lower() in (".png", ".jpg"):
                template = cv2.imread(str(f))
                if template is not None:
                    # 缩放到商店头像大小
                    template = cv2.resize(template, (48, 48))
                    self._champion_templates[f.stem] = template

        print(f"[模板匹配] 已加载 {len(self._champion_templates)} 个英雄头像")

    def load_item_icons(self):
        """加载装备图标模板"""
        if not ITEM_ICONS_DIR.exists():
            print(f"[警告] 装备图标目录不存在: {ITEM_ICONS_DIR}")
            return

        for f in ITEM_ICONS_DIR.iterdir():
            if f.suffix.lower() in (".png", ".jpg"):
                template = cv2.imread(str(f))
                if template is not None:
                    template = cv2.resize(template, (32, 32))
                    self._item_templates[f.stem] = template

        print(f"[模板匹配] 已加载 {len(self._item_templates)} 个装备图标")

    def identify_champion(self, region: np.ndarray) -> list[dict]:
        """
        在截图区域中识别英雄

        Returns:
            [{"id": "Jinx", "confidence": 0.95, "position": (x, y)}, ...]
        """
        results = []
        gray_region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        for champ_id, template in self._champion_templates.items():
            gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            h, w = gray_template.shape

            result = cv2.matchTemplate(gray_region, gray_template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= self.confidence)

            for pt in zip(*locations[::-1]):
                results.append({
                    "id": champ_id,
                    "confidence": float(result[pt[1], pt[0]]),
                    "position": (int(pt[0]), int(pt[1])),
                    "size": (w, h),
                })

        # 去重: 合并相近位置的结果
        results = self._nms(results, distance_threshold=30)
        return results

    def identify_shop(self, shop_slots: list[np.ndarray]) -> list[str]:
        """
        识别商店中的 5 个英雄

        Returns:
            ["Jinx", "Vi", "Unknown", "Caitlyn", "Ekko"]
        """
        identified = []
        for slot in shop_slots:
            best_match = None
            best_conf = 0

            for champ_id, template in self._champion_templates.items():
                # 用直方图比较代替模板匹配（更适合单头像）
                result = cv2.matchTemplate(slot, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)

                if max_val > best_conf:
                    best_conf = max_val
                    best_match = champ_id

            if best_match and best_conf >= self.confidence:
                identified.append(best_match)
            else:
                identified.append("Unknown")

        return identified

    def identify_items(self, region: np.ndarray) -> list[dict]:
        """识别区域中的装备图标"""
        results = []

        for item_id, template in self._item_templates.items():
            result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= self.confidence)

            for pt in zip(*locations[::-1]):
                results.append({
                    "id": item_id,
                    "confidence": float(result[pt[1], pt[0]]),
                    "position": (int(pt[0]), int(pt[1])),
                })

        return self._nms(results, distance_threshold=20)

    def detect_star_level(self, champion_region: np.ndarray) -> int:
        """
        检测英雄的星级 (1/2/3)

        通过检测头像上方的星星数量或头像边框颜色
        - 1星: 普通边框
        - 2星: 银色边框 + 2个星
        - 3星: 金色边框 + 3个星
        """
        # 截取头像上方区域 (星星所在位置)
        h, w = champion_region.shape[:2]
        star_region = champion_region[:int(h * 0.2), :]

        # 转 HSV 检测金色 (3星)
        hsv = cv2.cvtColor(star_region, cv2.COLOR_BGR2HSV)

        # 金色范围
        gold_lower = np.array([15, 100, 200])
        gold_upper = np.array([35, 255, 255])
        gold_mask = cv2.inRange(hsv, gold_lower, gold_upper)
        gold_ratio = np.sum(gold_mask > 0) / max(gold_mask.size, 1)

        if gold_ratio > 0.1:
            return 3

        # 银色/白色范围 (2星)
        silver_lower = np.array([0, 0, 180])
        silver_upper = np.array([180, 30, 255])
        silver_mask = cv2.inRange(hsv, silver_lower, silver_upper)
        silver_ratio = np.sum(silver_mask > 0) / max(silver_mask.size, 1)

        if silver_ratio > 0.1:
            return 2

        return 1

    def _nms(self, results: list[dict], distance_threshold: int = 30) -> list[dict]:
        """非极大值抑制 - 去除重叠检测"""
        if not results:
            return []

        # 按置信度排序
        results.sort(key=lambda r: r["confidence"], reverse=True)
        kept = []

        for r in results:
            is_duplicate = False
            for k in kept:
                dx = abs(r["position"][0] - k["position"][0])
                dy = abs(r["position"][1] - k["position"][1])
                if dx < distance_threshold and dy < distance_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept.append(r)

        return kept
