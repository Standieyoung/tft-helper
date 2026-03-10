"""下载英雄头像和装备图标到本地 assets 目录"""

import json
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
CHAMPIONS_DIR = ASSETS_DIR / "champions"
ITEMS_DIR = ASSETS_DIR / "items"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"

# Community Dragon 图片 CDN
CDRAGON_IMG_BASE = "https://raw.communitydragon.org/latest/game"


def download_file(client: httpx.Client, url: str, dest: Path) -> bool:
    """下载文件到本地"""
    if dest.exists():
        return True
    try:
        resp = client.get(url, timeout=15)
        if resp.status_code == 200:
            dest.write_bytes(resp.content)
            return True
        else:
            print(f"  [跳过] {resp.status_code}: {url}")
            return False
    except Exception as e:
        print(f"  [错误] {e}: {url}")
        return False


def icon_path_to_url(icon_path: str) -> str:
    """
    将 Community Dragon 的 icon path 转换为可下载的 URL
    例: "ASSETS/UX/TFT/ChampionSplashes/TFT16_Bard.TFT_Set16.tex"
    → "https://raw.communitydragon.org/latest/game/assets/ux/tft/championsplashes/tft16_bard.tft_set16.png"
    """
    # 替换路径分隔符，转小写，换扩展名
    path = icon_path.lower().replace("\\", "/").replace(".tex", ".png").replace(".dds", ".png")
    return f"{CDRAGON_IMG_BASE}/{path}"


def download_champion_icons():
    """下载所有英雄头像"""
    CHAMPIONS_DIR.mkdir(parents=True, exist_ok=True)

    cache_file = CACHE_DIR / "tft_champions.json"
    if not cache_file.exists():
        print("错误: 请先运行 main.py 加载英雄数据")
        return

    champions = json.loads(cache_file.read_text(encoding="utf-8"))
    print(f"准备下载 {len(champions)} 个英雄头像...")

    client = httpx.Client(follow_redirects=True)
    success = 0
    failed = 0

    for champ in champions:
        champ_id = champ["id"]
        icon_raw = champ.get("icon", "")
        if not icon_raw:
            continue

        dest = CHAMPIONS_DIR / f"{champ_id}.png"
        url = icon_path_to_url(icon_raw)

        if download_file(client, url, dest):
            success += 1
            print(f"  ✓ {champ['name']} ({champ_id})")
        else:
            # 尝试备用 URL 格式
            alt_url = f"https://raw.communitydragon.org/latest/game/assets/ux/tft/championsplashes/{champ_id.lower()}.tft_set16.png"
            if download_file(client, alt_url, dest):
                success += 1
                print(f"  ✓ {champ['name']} ({champ_id}) [备用URL]")
            else:
                failed += 1
                print(f"  ✗ {champ['name']} ({champ_id})")

    client.close()
    print(f"\n完成: {success} 成功, {failed} 失败")


def download_item_icons():
    """下载装备图标"""
    ITEMS_DIR.mkdir(parents=True, exist_ok=True)

    cache_file = CACHE_DIR / "tft_items.json"
    if not cache_file.exists():
        print("错误: 请先运行 main.py 加载装备数据")
        return

    items = json.loads(cache_file.read_text(encoding="utf-8"))
    print(f"准备下载 {len(items)} 个装备图标...")

    client = httpx.Client(follow_redirects=True)
    success = 0
    failed = 0

    for item in items:
        item_id = item["id"]
        icon_raw = item.get("icon", "")
        if not icon_raw:
            continue

        dest = ITEMS_DIR / f"{item_id}.png"
        url = icon_path_to_url(icon_raw)

        if download_file(client, url, dest):
            success += 1
        else:
            failed += 1
            print(f"  ✗ {item['name']} ({item_id})")

    client.close()
    print(f"\n完成: {success} 成功, {failed} 失败")


if __name__ == "__main__":
    print("=" * 40)
    print("  下载英雄头像和装备图标")
    print("=" * 40)

    if "--items" in sys.argv:
        download_item_icons()
    elif "--champions" in sys.argv:
        download_champion_icons()
    else:
        download_champion_icons()
        print()
        download_item_icons()
