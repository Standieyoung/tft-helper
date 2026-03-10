"""游戏状态解析 - 整合截屏识别结果为结构化游戏状态"""

import re

import cv2
import numpy as np

try:
    import pytesseract
except ImportError:
    pytesseract = None

from data.models import GameState, PlayerBoard
from recognition.screen_capture import ScreenCapture
from recognition.image_match import TemplateMatcher


class GameStateParser:
    """从屏幕截图解析游戏状态"""

    def __init__(self, capture: ScreenCapture, matcher: TemplateMatcher):
        self.capture = capture
        self.matcher = matcher

    def parse_current_state(self) -> GameState:
        """解析当前完整游戏状态"""
        state = GameState()

        # 解析回合信息
        state.round = self._parse_round()

        # 解析己方信息
        state.my_board = self._parse_my_board()

        # 解析商店
        state.shop = self._parse_shop()

        return state

    def _parse_round(self) -> str:
        """识别当前回合数 (如 '3-2')"""
        region = self.capture.capture_region("round_info")
        if region is None:
            return ""

        text = self._ocr(region)
        # 匹配 "X-Y" 格式
        match = re.search(r"(\d+)-(\d+)", text)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        return text.strip()

    def _parse_my_board(self) -> PlayerBoard:
        """解析己方棋盘"""
        board = PlayerBoard(player_id=0)

        # 识别等级
        level_region = self.capture.capture_region("level_info")
        if level_region is not None:
            text = self._ocr(level_region)
            nums = re.findall(r"\d+", text)
            if nums:
                board.level = int(nums[0])

        # 识别金币
        gold_region = self.capture.capture_region("gold_info")
        if gold_region is not None:
            text = self._ocr(gold_region)
            nums = re.findall(r"\d+", text)
            if nums:
                board.gold = int(nums[0])

        # 识别血量
        hp_region = self.capture.capture_region("hp_info")
        if hp_region is not None:
            text = self._ocr(hp_region)
            nums = re.findall(r"\d+", text)
            if nums:
                board.hp = int(nums[0])

        # 识别场上英雄
        board_region = self.capture.capture_region("my_board")
        if board_region is not None:
            detected = self.matcher.identify_champion(board_region)
            for d in detected:
                # 截取该英雄区域来检测星级
                x, y = d["position"]
                size = d.get("size", (48, 48))
                h_img, w_img = board_region.shape[:2]
                x1 = max(0, x - 10)
                y1 = max(0, y - 15)
                x2 = min(w_img, x + size[0] + 10)
                y2 = min(h_img, y + size[1] + 5)
                champ_region = board_region[y1:y2, x1:x2]
                star = self.matcher.detect_star_level(champ_region)

                board.champions.append({
                    "id": d["id"],
                    "star": star,
                    "confidence": d["confidence"],
                })

        # 识别备战席英雄
        bench_region = self.capture.capture_region("bench")
        if bench_region is not None:
            detected = self.matcher.identify_champion(bench_region)
            for d in detected:
                board.champions.append({
                    "id": d["id"],
                    "star": 1,  # 备战席默认 1 星
                    "confidence": d["confidence"],
                })

        return board

    def _parse_shop(self) -> list[str]:
        """识别商店中的英雄"""
        slots = self.capture.capture_shop_slots()
        if not slots:
            return []
        return self.matcher.identify_shop(slots)

    def parse_opponent(self, opponent_id: int) -> PlayerBoard:
        """
        解析当前查看的对手棋盘
        需要玩家手动切到对手视角时调用
        """
        board = PlayerBoard(player_id=opponent_id)

        region = self.capture.capture_region("opponent_board")
        if region is not None:
            detected = self.matcher.identify_champion(region)
            for d in detected:
                x, y = d["position"]
                size = d.get("size", (48, 48))
                h_img, w_img = region.shape[:2]
                x1 = max(0, x - 10)
                y1 = max(0, y - 15)
                x2 = min(w_img, x + size[0] + 10)
                y2 = min(h_img, y + size[1] + 5)
                champ_region = region[y1:y2, x1:x2]
                star = self.matcher.detect_star_level(champ_region)

                board.champions.append({
                    "id": d["id"],
                    "star": star,
                    "confidence": d["confidence"],
                })

        return board

    def detect_augment_screen(self) -> bool:
        """检测是否处于强化选择界面"""
        region = self.capture.capture_region("augment_choice_1")
        if region is None:
            return False
        # 强化选择界面有特殊的背景色
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        # 检测暗色背景
        dark_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 50, 80]))
        dark_ratio = np.sum(dark_mask > 0) / max(dark_mask.size, 1)
        return dark_ratio > 0.4

    def _ocr(self, image: np.ndarray) -> str:
        """OCR 文字识别"""
        if pytesseract is None:
            return ""
        # 预处理: 灰度 + 二值化
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        try:
            text = pytesseract.image_to_string(binary, lang="eng", config="--psm 7")
            return text.strip()
        except Exception:
            return ""
