"""装备推荐引擎"""

from data.models import Item, Champion


class ItemAdvisor:
    """装备合成与推荐"""

    # 基础装备列表
    BASE_ITEMS = [
        "BFSword",       # 暴风大剑
        "RecurveBow",    # 反曲之弓
        "NeedlesslyLargeRod",  # 无用大棒
        "TearOfTheGoddess",    # 女神之泪
        "ChainVest",     # 锁子甲
        "NegatronCloak", # 负极斗篷
        "GiantsBelt",    # 巨人腰带
        "Spatula",       # 金铲铲
        "SparringGloves", # 拳套
    ]

    def __init__(self, item_db: dict[str, Item]):
        self.item_db = item_db
        # 构建合成表: (组件A, 组件B) → 成品
        self.recipe_map: dict[tuple[str, str], Item] = {}
        for item in item_db.values():
            if len(item.components) == 2:
                key = tuple(sorted(item.components))
                self.recipe_map[key] = item

    def get_possible_items(self, components: list[str]) -> list[dict]:
        """
        给定当前拥有的组件，列出所有可合成的装备

        返回: [{"item": Item, "use_components": [comp1, comp2]}, ...]
        """
        results = []
        used = set()

        for i in range(len(components)):
            for j in range(i + 1, len(components)):
                if i in used or j in used:
                    continue
                key = tuple(sorted([components[i], components[j]]))
                if key in self.recipe_map:
                    results.append({
                        "item": self.recipe_map[key],
                        "use_components": [components[i], components[j]],
                    })

        return results

    def recommend_items(
        self, components: list[str], target_champions: list[str],
        comp_items: dict[str, list[str]]
    ) -> list[dict]:
        """
        根据阵容推荐的出装和当前组件，推荐最优合成方案

        Args:
            components: 当前拥有的组件
            target_champions: 目标阵容的英雄
            comp_items: 阵容推荐出装 {champion_id: [item_id, ...]}

        Returns:
            优先级排序的装备合成推荐
        """
        # 收集所有推荐装备
        wanted_items = set()
        for champ_id in target_champions:
            for item_id in comp_items.get(champ_id, []):
                wanted_items.add(item_id)

        # 检查哪些推荐装备可以用现有组件合成
        possible = self.get_possible_items(components)
        recommendations = []

        for p in possible:
            item = p["item"]
            priority = "高" if item.id in wanted_items else "普通"
            recommendations.append({
                "item": item,
                "components": p["use_components"],
                "priority": priority,
            })

        # 优先推荐阵容需要的装备
        recommendations.sort(key=lambda r: 0 if r["priority"] == "高" else 1)
        return recommendations

    def get_recipe_table(self) -> dict[str, list[dict]]:
        """
        生成完整合成表，用于 UI 展示

        Returns:
            {base_item: [{combine_with: str, result: Item}, ...]}
        """
        table = {}
        for (comp1, comp2), item in self.recipe_map.items():
            for base, other in [(comp1, comp2), (comp2, comp1)]:
                if base not in table:
                    table[base] = []
                table[base].append({
                    "combine_with": other,
                    "result": item,
                })
        return table
