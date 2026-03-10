"""
云顶助手 - TFT Helper
主程序入口
"""

import sys
import time
import threading
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent))

from data.scraper import DataTFTScraper, RiotDataDragon
from data.models import Champion, Comp, GameState, PlayerBoard
from advisor.comp_advisor import CompAdvisor
from advisor.item_advisor import ItemAdvisor


def init_data():
    """初始化数据: 从 DataTFT 和 Riot CDN 拉取"""
    print("正在加载游戏数据...")

    # 从 Community Dragon 获取基础数据
    ddragon = RiotDataDragon()
    try:
        champions_raw = ddragon.fetch_tft_champions()
        items_raw = ddragon.fetch_tft_items()
        traits_raw = ddragon.fetch_tft_traits()
        print(f"  英雄: {len(champions_raw)} 个")
        print(f"  装备: {len(items_raw)} 个")
        print(f"  羁绊: {len(traits_raw)} 个")
    finally:
        ddragon.close()

    # 构建英雄数据库
    champion_db: dict[str, Champion] = {}
    for c in champions_raw:
        if c.get("cost", 0) > 0:  # 过滤掉无效数据
            champ = Champion(
                id=c["id"],
                name=c["name"],
                cost=c["cost"],
                traits=c.get("traits", []),
                icon_url=c.get("icon", ""),
            )
            champion_db[champ.id] = champ

    # 从 DataTFT 获取阵容推荐
    scraper = DataTFTScraper()
    try:
        comps_raw = scraper.fetch_comps()
    finally:
        scraper.close()

    # 解析阵容数据
    comp_db: list[Comp] = []
    for c in comps_raw:
        comp = Comp(
            name=c.get("name", "未知阵容"),
            tier=c.get("tier", "B"),
            champions=c.get("champions", []),
            items=c.get("items", {}),
            augments=c.get("augments", []),
            avg_placement=c.get("avg_placement", 4.0),
            play_rate=c.get("play_rate", 0.0),
        )
        comp_db.append(comp)

    print(f"  阵容: {len(comp_db)} 套")
    print("数据加载完成!")
    return champion_db, comp_db, items_raw


def demo_advisor(champion_db: dict[str, Champion], comp_db: list[Comp]):
    """演示决策引擎 (无需截屏)"""
    advisor = CompAdvisor(champion_db, comp_db)

    # 加载升级概率
    import yaml
    config_path = Path(__file__).parent / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    level_odds = config.get("level_odds", {})

    # 模拟一个游戏状态: 你在 3-2, 6级, 有一些巴德阵容的棋子
    state = GameState(
        round="3-2",
        my_board=PlayerBoard(
            player_id=0,
            champions=[
                {"id": "TFT16_Shen", "star": 2},    # 2星慎
                {"id": "TFT16_Illaoi", "star": 2},   # 2星俄洛伊
                {"id": "TFT16_Sona", "star": 1},     # 1星娑娜
                {"id": "TFT16_Vi", "star": 1},       # 1星蔚
                {"id": "TFT16_Bard", "star": 1},     # 1星巴德 (备战席)
                {"id": "TFT16_Qiyana", "star": 2},   # 2星奇亚娜
            ],
            level=6,
            hp=72,
            gold=30,
        ),
        opponents=[
            PlayerBoard(player_id=1, champions=[
                {"id": "TFT16_Bard", "star": 2},     # 对手1也在玩巴德!
                {"id": "TFT16_Sion", "star": 2},
                {"id": "TFT16_Wukong", "star": 1},
            ]),
            PlayerBoard(player_id=2, champions=[
                {"id": "TFT16_Kayle", "star": 2},    # 对手2在玩德玛
                {"id": "TFT16_Garen", "star": 2},
                {"id": "TFT16_JarvanIV", "star": 2},
            ]),
            PlayerBoard(player_id=3, champions=[
                {"id": "TFT16_Qiyana", "star": 2},   # 对手3也有奇亚娜
                {"id": "TFT16_Karma", "star": 1},
                {"id": "TFT16_Lissandra", "star": 1},
            ]),
        ],
        shop=["TFT16_Lulu", "TFT16_Rumble", "TFT16_Caitlyn", "TFT16_Teemo", "TFT16_Sion"],
    )

    print("\n--- 阵容推荐 ---")
    recs = advisor.recommend_comps(state, top_n=3)
    for i, rec in enumerate(recs):
        print(f"#{i+1} {rec.comp.name} (Tier {rec.comp.tier})")
        print(f"    匹配度: {rec.match_score}% | 可行性: {rec.feasibility}%")
        print(f"    竞争: {rec.competition_level} | {rec.reason}")
        if rec.missing_champions:
            print(f"    缺: {', '.join(rec.missing_champions[:5])}")

    print("\n--- 三星追踪 ---")
    alerts = advisor.check_three_star(state)
    for a in alerts:
        print(f"  {a.champion_name}: {a.owned}/9, 池剩 {a.remaining_in_pool}, {a.recommendation}")

    print("\n--- 卡牌提醒 ---")
    contests = advisor.check_contests(state)
    for c in contests:
        print(f"  [{c.alert_type}] {c.message}")

    # D牌概率计算
    print("\n--- D牌概率 (当前6级) ---")
    for target in ["TFT16_Bard", "TFT16_Neeko", "TFT16_Orianna"]:
        champ = champion_db.get(target)
        if champ:
            prob = advisor.calc_roll_probability(target, 6, level_odds)
            print(f"  {champ.name} ({champ.cost}费): 单次刷新出现概率 {prob*100:.2f}%")


def main():
    """主入口"""
    print("=" * 50)
    print("  云顶助手 - TFT Helper")
    print("  数据源: DataTFT + Riot CDN")
    print("=" * 50)

    # 检查启动模式
    if "--ui" in sys.argv:
        # GUI 模式
        champion_db, comp_db, items_raw = init_data()
        from ui.main_window import run_app
        run_app(champion_db, comp_db, items_raw)
    elif "--demo" in sys.argv:
        # 演示模式 (不需要截屏)
        champion_db, comp_db, items_raw = init_data()
        demo_advisor(champion_db, comp_db)
    elif "--calibrate" in sys.argv:
        from scripts.calibrate_screen import Calibrator
        calibrator = Calibrator()
        calibrator.run()
    elif "--download-icons" in sys.argv:
        from scripts.download_icons import download_champion_icons, download_item_icons
        download_champion_icons()
        print()
        download_item_icons()
    elif "--update-comps" in sys.argv:
        from scripts.update_comps import list_comps
        list_comps()
    else:
        print("\n用法:")
        print("  python main.py --ui              启动图形界面")
        print("  python main.py --demo            演示决策引擎")
        print("  python main.py --calibrate       屏幕坐标校准")
        print("  python main.py --download-icons  下载英雄/装备图标")
        print("  python main.py --update-comps    查看阵容数据")
        print()

        # 默认先加载数据测试
        champion_db, comp_db, items_raw = init_data()
        print(f"\n已加载 {len(champion_db)} 个英雄到数据库")

        # 打印部分英雄作为验证
        print("\n示例英雄数据:")
        for i, (cid, champ) in enumerate(champion_db.items()):
            if i >= 10:
                break
            print(f"  [{champ.cost}费] {champ.name} ({cid}) - 羁绊: {', '.join(champ.traits)}")


if __name__ == "__main__":
    main()
