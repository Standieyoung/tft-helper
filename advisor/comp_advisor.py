"""阵容推荐与决策引擎"""

from dataclasses import dataclass, field
from data.models import (
    Champion, Comp, GameState, PoolTracker,
    POOL_SIZE, THREE_STAR_REQUIRED, Cost,
)


@dataclass
class CompRecommendation:
    """阵容推荐结果"""
    comp: Comp
    match_score: float          # 匹配度 0-100
    missing_champions: list[str]  # 还缺哪些英雄
    competition_level: str      # "低", "中", "高"
    competing_players: list[int]  # 竞争玩家编号
    feasibility: float          # 可行性评分 0-100
    reason: str                 # 推荐理由


@dataclass
class ThreeStarAlert:
    """三星追踪提醒"""
    champion_id: str
    champion_name: str
    cost: int
    owned: int                  # 已拥有张数 (1星=1, 2星=3)
    needed: int                 # 还需要几张
    remaining_in_pool: int      # 牌池剩余
    competitors: list[int]      # 也在追这个英雄的对手
    probability: str            # "高", "中", "低"
    recommendation: str         # "继续追", "放弃转型", "谨慎D牌"


@dataclass
class ContestAlert:
    """抢牌/卡牌提醒"""
    champion_id: str
    champion_name: str
    alert_type: str             # "被抢", "可卡", "池枯"
    message: str


class CompAdvisor:
    """阵容决策引擎"""

    def __init__(self, champion_db: dict[str, Champion], comp_db: list[Comp]):
        self.champion_db = champion_db
        self.comp_db = comp_db
        self.pool_tracker = PoolTracker()

    def update_game_state(self, state: GameState):
        """更新游戏状态，重新计算牌池"""
        self.pool_tracker.update_from_boards(state, self.champion_db)
        self._current_state = state

    def recommend_comps(self, state: GameState, top_n: int = 3) -> list[CompRecommendation]:
        """
        根据当前状态推荐最佳阵容

        算法:
        1. 计算每个热门阵容与当前棋子的匹配度
        2. 评估牌池可行性 (需要的棋子还剩多少)
        3. 评估竞争度 (有几个对手在玩类似阵容)
        4. 综合评分排序
        """
        self.update_game_state(state)
        my_champions = {p["id"] for p in state.my_board.champions}
        recommendations = []

        for comp in self.comp_db:
            # 1. 匹配度: 已有的核心英雄 / 总核心英雄
            comp_set = set(comp.champions)
            overlap = my_champions & comp_set
            match_score = (len(overlap) / len(comp_set) * 100) if comp_set else 0
            missing = list(comp_set - my_champions)

            # 2. 牌池可行性: 缺的棋子在池中是否还有足够数量
            feasibility = self._calc_feasibility(missing)

            # 3. 竞争度: 对手中有多少人在用同一套阵容的核心棋子
            competition_level, competing_players = self._calc_competition(
                comp.champions, state.opponents
            )

            # 4. 综合评分
            competition_penalty = {"低": 0, "中": 15, "高": 30}.get(competition_level, 0)
            final_score = match_score * 0.4 + feasibility * 0.4 - competition_penalty + self._tier_bonus(comp.tier) * 0.2

            reason = self._gen_reason(match_score, feasibility, competition_level, comp)

            recommendations.append(CompRecommendation(
                comp=comp,
                match_score=round(match_score, 1),
                missing_champions=missing,
                competition_level=competition_level,
                competing_players=competing_players,
                feasibility=round(feasibility, 1),
                reason=reason,
            ))

        # 按综合评分排序
        recommendations.sort(
            key=lambda r: r.match_score * 0.4 + r.feasibility * 0.4,
            reverse=True,
        )
        return recommendations[:top_n]

    def check_three_star(self, state: GameState) -> list[ThreeStarAlert]:
        """
        检查哪些英雄接近三星，评估是否值得追

        规则:
        - 2星(已有3张)以上才追踪
        - 计算池中剩余 vs 还需要的
        - 考虑对手是否也在追
        """
        self.update_game_state(state)
        alerts = []

        for piece in state.my_board.champions:
            cid = piece["id"]
            star = piece.get("star", 1)
            if star < 2:
                continue

            champ = self.champion_db.get(cid)
            if not champ:
                continue

            owned = {1: 1, 2: 3, 3: 9}.get(star, 1)
            # 加上备战席上同名英雄
            bench_count = sum(
                {1: 1, 2: 3}.get(p.get("star", 1), 1)
                for p in state.my_board.champions
                if p["id"] == cid and p is not piece
            )
            total_owned = owned + bench_count

            info = self.pool_tracker.three_star_feasibility(cid, champ.cost, total_owned)
            if info["needed"] <= 0:
                continue

            # 检查对手中谁也有这个英雄
            competitors = []
            for opp in state.opponents:
                for op in opp.champions:
                    if op["id"] == cid:
                        competitors.append(opp.player_id)
                        break

            # 评估概率
            if info["remaining"] <= 0:
                probability = "不可能"
                recommendation = "放弃转型"
            elif info["ratio"] >= 2.0 and len(competitors) == 0:
                probability = "高"
                recommendation = "继续追"
            elif info["ratio"] >= 1.0:
                probability = "中"
                recommendation = "谨慎D牌" if len(competitors) > 0 else "继续追"
            else:
                probability = "低"
                recommendation = "放弃转型" if len(competitors) > 1 else "谨慎D牌"

            alerts.append(ThreeStarAlert(
                champion_id=cid,
                champion_name=champ.name,
                cost=champ.cost,
                owned=total_owned,
                needed=info["needed"],
                remaining_in_pool=info["remaining"],
                competitors=competitors,
                probability=probability,
                recommendation=recommendation,
            ))

        return alerts

    def check_contests(self, state: GameState) -> list[ContestAlert]:
        """
        检查卡牌/抢牌情况

        - 被抢: 对手在用你阵容的核心棋子
        - 可卡: 你可以买走对手急需的棋子
        - 池枯: 某关键棋子池中所剩无几
        """
        self.update_game_state(state)
        alerts = []
        my_champions = {p["id"] for p in state.my_board.champions}

        # 找到当前最匹配的阵容
        best_comp = None
        best_overlap = 0
        for comp in self.comp_db:
            overlap = len(my_champions & set(comp.champions))
            if overlap > best_overlap:
                best_overlap = overlap
                best_comp = comp

        if not best_comp:
            return alerts

        # 检查被抢
        for cid in best_comp.champions:
            if cid in my_champions:
                continue
            champ = self.champion_db.get(cid)
            if not champ:
                continue

            remaining = self.pool_tracker.remaining(cid, champ.cost)
            total = POOL_SIZE.get(champ.cost, 0)

            # 谁在用这个英雄
            users = []
            for opp in state.opponents:
                for p in opp.champions:
                    if p["id"] == cid:
                        users.append(opp.player_id)
                        break

            if len(users) >= 2:
                alerts.append(ContestAlert(
                    champion_id=cid,
                    champion_name=champ.name,
                    alert_type="被抢",
                    message=f"{champ.name} 被 {len(users)} 人使用，池中仅剩 {remaining}/{total}",
                ))
            elif remaining <= total * 0.3:
                alerts.append(ContestAlert(
                    champion_id=cid,
                    champion_name=champ.name,
                    alert_type="池枯",
                    message=f"{champ.name} 池中仅剩 {remaining}/{total}，建议尽早锁定",
                ))

        return alerts

    def calc_roll_probability(self, champion_id: str, level: int, level_odds: dict) -> float:
        """
        计算在当前等级D到某个英雄的概率

        公式: P = (该费用出现概率) × (该英雄剩余 / 该费用所有英雄剩余)
        每次商店刷新有 5 个位置，所以出现至少 1 个的概率:
        P_at_least_1 = 1 - (1 - P)^5
        """
        champ = self.champion_db.get(champion_id)
        if not champ:
            return 0.0

        cost = champ.cost
        odds = level_odds.get(level, [0] * 5)
        cost_probability = odds[cost - 1] / 100  # 该费用出现的概率

        # 该费用所有英雄的剩余总数
        same_cost_remaining = 0
        target_remaining = 0
        for cid, c in self.champion_db.items():
            if c.cost == cost:
                r = self.pool_tracker.remaining(cid, cost)
                same_cost_remaining += r
                if cid == champion_id:
                    target_remaining = r

        if same_cost_remaining <= 0:
            return 0.0

        # 单次 slot 命中概率
        p_single = cost_probability * (target_remaining / same_cost_remaining)
        # 5 个 slot 至少出现一次
        p_at_least_one = 1 - (1 - p_single) ** 5

        return round(p_at_least_one, 4)

    # --- 内部辅助方法 ---

    def _calc_feasibility(self, missing_champions: list[str]) -> float:
        """计算缺失英雄的牌池可行性 0-100"""
        if not missing_champions:
            return 100.0

        scores = []
        for cid in missing_champions:
            champ = self.champion_db.get(cid)
            if not champ:
                scores.append(50)
                continue
            remaining = self.pool_tracker.remaining(cid, champ.cost)
            total = POOL_SIZE.get(champ.cost, 1)
            scores.append(remaining / total * 100)

        return sum(scores) / len(scores)

    def _calc_competition(
        self, comp_champions: list[str], opponents: list
    ) -> tuple[str, list[int]]:
        """计算阵容竞争度"""
        comp_set = set(comp_champions)
        competing = []

        for opp in opponents:
            opp_champs = {p["id"] for p in opp.champions}
            overlap = len(comp_set & opp_champs)
            # 有 3 个以上核心英雄重叠认为在玩同一套
            if overlap >= 3:
                competing.append(opp.player_id)

        if len(competing) >= 2:
            return "高", competing
        elif len(competing) == 1:
            return "中", competing
        return "低", []

    def _tier_bonus(self, tier: str) -> float:
        """阵容评级加分"""
        return {"S": 100, "A": 75, "B": 50, "C": 25}.get(tier, 50)

    def _gen_reason(
        self, match: float, feasibility: float, competition: str, comp: Comp
    ) -> str:
        """生成推荐理由"""
        parts = []
        if match >= 60:
            parts.append("高匹配度")
        if feasibility >= 70:
            parts.append("牌池充裕")
        elif feasibility < 40:
            parts.append("牌池紧张")
        if competition == "低":
            parts.append("无人竞争")
        elif competition == "高":
            parts.append("竞争激烈")
        if comp.tier in ("S", "A"):
            parts.append(f"{comp.tier}级阵容")
        return "，".join(parts) if parts else "综合推荐"
