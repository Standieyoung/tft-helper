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
        state.round = self._parse_round()
        state.my_board = self._parse_my_board()
        state.shop = self._parse_shop()
        return state

    def _parse_round(self) -> str:
        """识别当前回合数 (如 '3-2')"""
        region = self.capture.capture_region("round_info")
        if region is None:
            return ""

        text = self._ocr_number(region, mode="white")
        match = re.search(r"(\d+)\s*[-–—]\s*(\d+)", text)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        return ""

    def _parse_my_board(self) -> PlayerBoard:
        """解析己方棋盘"""
        board = PlayerBoard(player_id=0)

        level_region = self.capture.capture_region("level_info")
        if level_region is not None:
            text = self._ocr_number(level_region, mode="white")
            nums = re.findall(r"\d+", text)
            if nums:
                val = int(nums[0])
                if 1 <= val <= 11:
                    board.level = val

        gold_region = self.capture.capture_region("gold_info")
        if gold_region is not None:
            text = self._ocr_number(gold_region, mode="gold")
            nums = re.findall(r"\d+", text)
            if nums:
                val = int(nums[0])
                if 0 <= val <= 999:
                    board.gold = val

        hp_region = self.capture.capture_region("hp_info")
        if hp_region is not None:
            text = self._ocr_number(hp_region, mode="white")
            nums = re.findall(r"\d+", text)
            if nums:
                val = int(nums[0])
                if 1 <= val <= 100:
                    board.hp = val

        board_region = self.capture.capture_region("my_board")
        if board_region is not None:
            detected = self.matcher.identify_champion(board_region)
            for d in detected:
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

        bench_region = self.capture.capture_region("bench")
        if bench_region is not None:
            detected = self.matcher.identify_champion(bench_region)
            for d in detected:
                board.champions.append({
                    "id": d["id"],
                    "star": 1,
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
        """解析对手棋盘（需要手动切到对手视角）"""
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
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        dark_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 50, 80]))
        dark_ratio = np.sum(dark_mask > 0) / max(dark_mask.size, 1)
        return dark_ratio > 0.4

    # --- OCR ---

    def _ocr_number(self, image: np.ndarray, mode: str = "white") -> str:
        """
        针对 TFT 游戏 UI 优化的数字 OCR。

        TFT 中不同区域的文字颜色不同:
        - white: 回合、等级、血量 (白色/浅色文字)
        - gold:  金币 (黄色文字)

        使用多种预处理策略，取最佳结果。
        """
        if pytesseract is None:
            return ""

        candidates = []

        # 放大小图以提高 OCR 精度
        h, w = image.shape[:2]
        if w < 100 or h < 40:
            scale = max(3, 120 // max(w, 1))
            image = cv2.resize(image, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        preprocessed_images = []

        if mode == "gold":
            # 黄色文字: 提取 HSV 中的黄色通道
            yellow_mask = cv2.inRange(hsv,
                                      np.array([15, 80, 150]),
                                      np.array([40, 255, 255]))
            preprocessed_images.append(yellow_mask)
            # 也试试高亮度通道
            bright_mask = cv2.inRange(hsv,
                                      np.array([0, 0, 180]),
                                      np.array([180, 255, 255]))
            preprocessed_images.append(bright_mask)

        # 白色/浅色文字: 高灰度阈值
        for thresh in (140, 160, 180, 200):
            _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
            preprocessed_images.append(binary)

        # 反色 (白底黑字有时识别更好)
        _, inv_binary = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)
        preprocessed_images.append(inv_binary)

        # 自适应阈值
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 11, 2)
        preprocessed_images.append(adaptive)

        # OTSU 自动阈值
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        preprocessed_images.append(otsu)

        for img in preprocessed_images:
            text = self._run_tesseract(img)
            if text and re.search(r"\d", text):
                candidates.append(text)

        if not candidates:
            return ""

        # 选包含数字最多的结果
        best = max(candidates, key=lambda t: len(re.findall(r"\d", t)))
        return best

    @staticmethod
    def _run_tesseract(binary_image: np.ndarray) -> str:
        """执行 tesseract OCR"""
        try:
            # whitelist 只识别数字和常见分隔符
            config = "--psm 7 -c tessedit_char_whitelist=0123456789-/"
            text = pytesseract.image_to_string(binary_image, lang="eng", config=config)
            return text.strip()
        except Exception:
            return ""
