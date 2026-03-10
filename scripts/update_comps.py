"""
阵容数据更新工具

支持两种方式:
1. 手动编辑模式: 打开编辑器修改 comps.json
2. 从网页抓取模式: 尝试从 DataTFT 等网站解析阵容数据 (需要浏览器抓包后配置 API)
3. 交互式添加: 通过命令行交互添加阵容
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
COMPS_FILE = PROJECT_ROOT / "data" / "cache" / "comps.json"
CHAMPIONS_FILE = PROJECT_ROOT / "data" / "cache" / "tft_champions.json"


def load_comps() -> list[dict]:
    if COMPS_FILE.exists():
        return json.loads(COMPS_FILE.read_text(encoding="utf-8"))
    return []


def save_comps(comps: list[dict]):
    COMPS_FILE.write_text(
        json.dumps(comps, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已保存 {len(comps)} 套阵容到 {COMPS_FILE}")


def load_champion_names() -> dict[str, str]:
    """加载英雄 ID → 中文名映射"""
    if not CHAMPIONS_FILE.exists():
        return {}
    data = json.loads(CHAMPIONS_FILE.read_text(encoding="utf-8"))
    return {c["id"]: c["name"] for c in data}


def list_comps():
    """列出所有阵容"""
    comps = load_comps()
    names = load_champion_names()
    print(f"\n当前共 {len(comps)} 套阵容:\n")
    for i, comp in enumerate(comps):
        champ_names = [names.get(c, c) for c in comp.get("champions", [])]
        print(f"  [{i}] [{comp.get('tier', '?')}] {comp['name']}")
        print(f"      英雄: {', '.join(champ_names[:6])}{'...' if len(champ_names) > 6 else ''}")
        print(f"      平均名次: {comp.get('avg_placement', '?')} | 使用率: {comp.get('play_rate', '?')}")
        print()


def add_comp_interactive():
    """交互式添加阵容"""
    names = load_champion_names()
    reverse_names = {v: k for k, v in names.items()}

    print("\n--- 添加新阵容 ---")
    name = input("阵容名称: ").strip()
    tier = input("评级 (S/A/B/C): ").strip().upper()

    print("\n输入核心英雄 (中文名，逗号分隔):")
    print(f"  可用英雄示例: {', '.join(list(names.values())[:10])}...")
    champ_input = input("> ").strip()
    champion_ids = []
    for cn in champ_input.split(","):
        cn = cn.strip()
        if cn in reverse_names:
            champion_ids.append(reverse_names[cn])
            print(f"  ✓ {cn} → {reverse_names[cn]}")
        else:
            # 模糊匹配
            matches = [k for k, v in names.items() if cn in v]
            if matches:
                champion_ids.append(matches[0])
                print(f"  ✓ {cn} → {names[matches[0]]} ({matches[0]})")
            else:
                print(f"  ✗ 未找到: {cn}")

    playstyle = input("运营方式: ").strip()
    difficulty = input("难度 (低/中/高): ").strip()
    avg_placement = float(input("平均名次 (如 3.5): ") or "4.0")

    comp = {
        "name": name,
        "tier": tier,
        "champions": champion_ids,
        "items": {},
        "augments": [],
        "playstyle": playstyle,
        "difficulty": difficulty,
        "avg_placement": avg_placement,
        "play_rate": 0.0,
        "win_rate": 0.0,
    }

    # 装备配置
    print("\n配置装备? (输入英雄中文名，留空跳过)")
    while True:
        carry = input("给谁装备 (留空结束): ").strip()
        if not carry:
            break
        carry_id = reverse_names.get(carry)
        if not carry_id:
            matches = [k for k, v in names.items() if carry in v]
            carry_id = matches[0] if matches else None
        if carry_id:
            items_str = input(f"  {carry} 的装备 (逗号分隔): ").strip()
            comp["items"][carry_id] = [i.strip() for i in items_str.split(",")]
        else:
            print(f"  未找到英雄: {carry}")

    comps = load_comps()
    comps.append(comp)
    save_comps(comps)
    print(f"\n已添加阵容: {name}")


def delete_comp():
    """删除阵容"""
    comps = load_comps()
    list_comps()
    idx = input("输入要删除的序号: ").strip()
    try:
        idx = int(idx)
        removed = comps.pop(idx)
        save_comps(comps)
        print(f"已删除: {removed['name']}")
    except (ValueError, IndexError):
        print("无效序号")


def update_tier():
    """批量更新阵容评级"""
    comps = load_comps()
    list_comps()
    print("输入 '序号 评级' 来更新 (如 '0 S'), 输入 'done' 结束:")
    while True:
        line = input("> ").strip()
        if line.lower() == "done":
            break
        parts = line.split()
        if len(parts) == 2:
            try:
                idx = int(parts[0])
                tier = parts[1].upper()
                comps[idx]["tier"] = tier
                print(f"  {comps[idx]['name']} → Tier {tier}")
            except (ValueError, IndexError):
                print("  无效输入")
    save_comps(comps)


def set_datatft_api():
    """配置 DataTFT API 端点 (需要手动抓包获取)"""
    print("\n--- 配置 DataTFT API ---")
    print("请在浏览器中打开 https://www.datatft.com/comps")
    print("按 F12 → Network → XHR，找到返回阵容数据的请求")
    print("复制该请求的完整 URL\n")
    url = input("API URL: ").strip()
    if url:
        config_path = PROJECT_ROOT / "config_api.json"
        config = {}
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
        config["datatft_comps_api"] = url
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"已保存 API 地址到 {config_path}")
        print("下次运行 main.py 时会自动尝试从此 API 拉取阵容数据")


def import_comps(filepath: str):
    """从 JSON 文件批量导入阵容，与现有数据合并"""
    import_path = Path(filepath)
    if not import_path.exists():
        print(f"文件不存在: {filepath}")
        return

    try:
        new_comps = json.loads(import_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        return

    if not isinstance(new_comps, list):
        print("错误: JSON 文件必须是阵容数组")
        return

    existing = load_comps()
    existing_names = {c["name"] for c in existing}

    added = 0
    updated = 0
    for comp in new_comps:
        if not comp.get("name"):
            continue
        if comp["name"] in existing_names:
            for i, e in enumerate(existing):
                if e["name"] == comp["name"]:
                    existing[i] = comp
                    updated += 1
                    break
        else:
            existing.append(comp)
            added += 1

    save_comps(existing)
    print(f"导入完成: {added} 个新增, {updated} 个更新")


def force_refresh():
    """强制从网络重新拉取阵容数据"""
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from data.scraper import DataTFTScraper
        scraper = DataTFTScraper()
        try:
            comps = scraper.fetch_comps(force=True)
            if comps:
                print(f"成功拉取 {len(comps)} 套阵容")
                list_comps()
            else:
                print("未能从 API 获取数据，缓存保持不变")
        finally:
            scraper.close()
    except Exception as e:
        print(f"刷新失败: {e}")


def main():
    print("=" * 40)
    print("  阵容数据管理工具")
    print("=" * 40)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "list":
            list_comps()
        elif cmd == "add":
            add_comp_interactive()
        elif cmd == "delete":
            delete_comp()
        elif cmd == "tier":
            update_tier()
        elif cmd == "api":
            set_datatft_api()
        elif cmd == "import":
            if len(sys.argv) < 3:
                print("用法: python scripts/update_comps.py import <file.json>")
            else:
                import_comps(sys.argv[2])
        elif cmd == "refresh":
            force_refresh()
        else:
            print(f"未知命令: {cmd}")
    else:
        print("\n用法:")
        print("  python scripts/update_comps.py list             查看所有阵容")
        print("  python scripts/update_comps.py add              交互式添加阵容")
        print("  python scripts/update_comps.py delete           删除阵容")
        print("  python scripts/update_comps.py tier             批量更新评级")
        print("  python scripts/update_comps.py api              配置 DataTFT API 端点")
        print("  python scripts/update_comps.py import <file>    从 JSON 文件导入阵容")
        print("  python scripts/update_comps.py refresh          强制从网络刷新阵容")


if __name__ == "__main__":
    main()
