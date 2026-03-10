"""TFT 数据模型定义"""

from dataclasses import dataclass, field
from enum import IntEnum


class Cost(IntEnum):
    """英雄费用"""
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


# 牌池总数
POOL_SIZE = {
    Cost.ONE: 22,
    Cost.TWO: 20,
    Cost.THREE: 17,
    Cost.FOUR: 10,
    Cost.FIVE: 9,
}

# 三星所需张数
THREE_STAR_REQUIRED = 9


@dataclass
class Champion:
    """英雄数据"""
    id: str              # 英雄唯一标识 (如 "Jinx")
    name: str            # 显示名称 (如 "金克丝")
    cost: int            # 费用 1-5
    traits: list[str]    # 羁绊列表
    icon_url: str = ""   # 头像 URL
    # 基础属性
    hp: int = 0
    atk: int = 0
    armor: int = 0
    mr: int = 0
    atk_speed: float = 0.0
    range: int = 0


@dataclass
class Item:
    """装备数据"""
    id: str
    name: str
    components: list[str]   # 合成所需的基础装备 ID
    stats: dict = field(default_factory=dict)
    icon_url: str = ""
    is_base: bool = False   # 是否基础装备


@dataclass
class Trait:
    """羁绊数据"""
    id: str
    name: str
    breakpoints: list[int]          # 激活档位 [2, 4, 6]
    effects: list[str] = field(default_factory=list)
    champions: list[str] = field(default_factory=list)


@dataclass
class Comp:
    """阵容数据"""
    name: str
    tier: str                       # "S", "A", "B" 等
    champions: list[str]            # 核心英雄 ID 列表
    items: dict[str, list[str]] = field(default_factory=dict)  # 英雄 → 推荐装备
    augments: list[str] = field(default_factory=list)           # 推荐强化
    playstyle: str = ""             # 运营方式描述
    difficulty: str = ""            # 难度
    avg_placement: float = 0.0      # 平均名次
    play_rate: float = 0.0          # 使用率
    win_rate: float = 0.0           # 吃鸡率


@dataclass
class PlayerBoard:
    """玩家棋盘状态"""
    player_id: int                  # 0=自己, 1-7=对手
    champions: list[dict] = field(default_factory=list)  # [{"id": "Jinx", "star": 2}, ...]
    level: int = 1
    hp: int = 100
    gold: int = 0


@dataclass
class GameState:
    """当前游戏状态"""
    round: str = ""                 # "3-2" 格式
    phase: str = ""                 # "combat", "planning", "carousel"
    my_board: PlayerBoard = field(default_factory=lambda: PlayerBoard(player_id=0))
    opponents: list[PlayerBoard] = field(default_factory=list)
    shop: list[str] = field(default_factory=list)  # 商店中的英雄 ID
    my_items: list[str] = field(default_factory=list)  # 备战席上的装备组件


@dataclass
class PoolTracker:
    """牌池追踪器"""
    # champion_id → 已知被拿走的数量
    taken: dict[str, int] = field(default_factory=dict)

    def remaining(self, champion_id: str, cost: int) -> int:
        """计算某英雄在牌池中的剩余数量"""
        total = POOL_SIZE.get(cost, 0)
        used = self.taken.get(champion_id, 0)
        return max(0, total - used)

    def three_star_feasibility(self, champion_id: str, cost: int, owned: int) -> dict:
        """计算三星可行性"""
        remaining = self.remaining(champion_id, cost)
        needed = THREE_STAR_REQUIRED - owned
        if needed <= 0:
            return {"needed": 0, "remaining": remaining, "feasible": True, "ratio": 1.0}
        ratio = remaining / max(needed, 1)
        return {
            "needed": needed,
            "remaining": remaining,
            "feasible": remaining >= needed,
            "ratio": round(ratio, 2),
        }

    def update_from_boards(self, game_state: GameState, champion_db: dict[str, Champion]):
        """根据所有棋盘状态更新牌池"""
        self.taken.clear()
        # 统计自己的棋子
        for piece in game_state.my_board.champions:
            cid = piece["id"]
            star = piece.get("star", 1)
            count = {1: 1, 2: 3, 3: 9}.get(star, 1)
            self.taken[cid] = self.taken.get(cid, 0) + count
        # 统计对手的棋子
        for opp in game_state.opponents:
            for piece in opp.champions:
                cid = piece["id"]
                star = piece.get("star", 1)
                count = {1: 1, 2: 3, 3: 9}.get(star, 1)
                self.taken[cid] = self.taken.get(cid, 0) + count
