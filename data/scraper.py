"""DataTFT 数据抓取模块"""

import json
import time
from pathlib import Path

import httpx

from data.models import Comp, Champion, Item, Trait

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

BASE_URL = "https://www.datatft.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.datatft.com/",
}


def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"


def _is_cache_valid(name: str, ttl_hours: int = 4) -> bool:
    path = _cache_path(name)
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < ttl_hours * 3600


def _load_cache(name: str) -> dict | list | None:
    path = _cache_path(name)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_cache(name: str, data):
    path = _cache_path(name)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class DataTFTScraper:
    """从 DataTFT 抓取数据"""

    def __init__(self):
        self.client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15)

    def close(self):
        self.client.close()

    def fetch_page(self, path: str) -> str:
        """抓取页面 HTML"""
        url = f"{BASE_URL}{path}"
        resp = self.client.get(url)
        resp.raise_for_status()
        return resp.text

    def fetch_comps(self, force: bool = False) -> list[dict]:
        """
        抓取热门阵容数据

        优先级:
        1. 用户配置的 API 端点 (config_api.json)
        2. 默认 DataTFT API 端点
        3. 本地缓存
        """
        cache_name = "comps"
        if not force and _is_cache_valid(cache_name):
            return _load_cache(cache_name)

        api_urls = list(self._get_custom_api_urls())
        api_urls.extend([
            f"{BASE_URL}/api/comps",
            f"{BASE_URL}/api/v1/comps",
        ])

        for url in api_urls:
            try:
                resp = self.client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        _save_cache(cache_name, data)
                        print(f"[DataTFT] 从 API 获取到 {len(data)} 套阵容")
                        return data
            except Exception:
                continue

        cached = _load_cache(cache_name)
        if cached:
            print(f"[DataTFT] API 不可用，使用缓存 ({len(cached)} 套阵容)")
            return cached

        print("[DataTFT] 无法获取阵容数据，请手动更新缓存或检查 API 端点")
        return []

    @staticmethod
    def _get_custom_api_urls() -> list[str]:
        """从 config_api.json 读取用户配置的 API 端点"""
        config_path = Path(__file__).parent.parent / "config_api.json"
        if not config_path.exists():
            return []
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            url = config.get("datatft_comps_api", "")
            return [url] if url else []
        except (json.JSONDecodeError, OSError):
            return []

    def fetch_augments(self, force: bool = False) -> list[dict]:
        """抓取强化评级数据"""
        cache_name = "augments"
        if not force and _is_cache_valid(cache_name):
            return _load_cache(cache_name)

        api_urls = [
            f"{BASE_URL}/api/augments",
            f"{BASE_URL}/api/v1/augment/tier",
        ]

        for url in api_urls:
            try:
                resp = self.client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    _save_cache(cache_name, data)
                    return data
            except Exception:
                continue

        cached = _load_cache(cache_name)
        return cached or []


class RiotDataDragon:
    """
    从 Riot Data Dragon CDN 获取基础游戏数据
    这是官方公开的静态数据源
    """

    DDRAGON_BASE = "https://ddragon.leagueoflegends.com"

    def __init__(self):
        self.client = httpx.Client(follow_redirects=True, timeout=15)
        self._version = None

    def close(self):
        self.client.close()

    @property
    def version(self) -> str:
        """获取最新游戏版本号"""
        if self._version is None:
            resp = self.client.get(f"{self.DDRAGON_BASE}/api/versions.json")
            versions = resp.json()
            # TFT 数据可能和 LoL 版本不完全同步，取最新即可
            self._version = versions[0]
        return self._version

    CDRAGON_TFT_URL = "https://raw.communitydragon.org/latest/cdragon/tft/zh_cn.json"
    CURRENT_SET = "16"  # 当前赛季

    def _fetch_tft_data(self, force: bool = False) -> dict:
        """获取并缓存 Community Dragon 完整 TFT 数据"""
        cache_name = "cdragon_tft_raw"
        if not force and _is_cache_valid(cache_name, ttl_hours=24):
            return _load_cache(cache_name)

        try:
            resp = self.client.get(self.CDRAGON_TFT_URL)
            if resp.status_code == 200:
                data = resp.json()
                _save_cache(cache_name, data)
                return data
        except Exception as e:
            print(f"[CommunityDragon] 获取数据失败: {e}")

        return _load_cache(cache_name) or {}

    def fetch_tft_champions(self, force: bool = False) -> list[dict]:
        """获取当前赛季 TFT 英雄数据"""
        cache_name = "tft_champions"
        if not force and _is_cache_valid(cache_name, ttl_hours=24):
            return _load_cache(cache_name)

        data = self._fetch_tft_data(force)
        current_set = data.get("sets", {}).get(self.CURRENT_SET, {})
        champions = []
        for c in current_set.get("champions", []):
            cost = c.get("cost", 0)
            # 只保留正常费用英雄 (1-5费)
            if cost not in (1, 2, 3, 4, 5):
                continue
            name = c.get("name", "")
            api_name = c.get("apiName", "")
            # 过滤掉非英雄条目 (训练假人、发明等)
            if not api_name.startswith("TFT16_"):
                continue
            champions.append({
                "id": api_name,
                "name": name,
                "cost": cost,
                "traits": c.get("traits", []),
                "icon": c.get("icon", ""),
                "stats": c.get("stats", {}),
                "ability": {
                    "name": c.get("ability", {}).get("name", ""),
                    "desc": c.get("ability", {}).get("desc", ""),
                },
            })
        _save_cache(cache_name, champions)
        return champions

    def fetch_tft_items(self, force: bool = False) -> list[dict]:
        """获取 TFT 装备数据 (只含可合成的标准装备)"""
        cache_name = "tft_items"
        if not force and _is_cache_valid(cache_name, ttl_hours=24):
            return _load_cache(cache_name)

        data = self._fetch_tft_data(force)
        items = []
        for item in data.get("items", []):
            api_name = item.get("apiName", "")
            # 标准合成装备
            if api_name.startswith("TFT_Item_") and item.get("composition"):
                items.append({
                    "id": api_name,
                    "name": item.get("name", ""),
                    "composition": item.get("composition", []),
                    "desc": item.get("desc", ""),
                    "icon": item.get("icon", ""),
                    "effects": item.get("effects", {}),
                })
        # 也加入基础装备
        base_ids = {
            "TFT_Item_BFSword", "TFT_Item_RecurveBow",
            "TFT_Item_NeedlesslyLargeRod", "TFT_Item_TearOfTheGoddess",
            "TFT_Item_ChainVest", "TFT_Item_NegatronCloak",
            "TFT_Item_GiantsBelt", "TFT_Item_Spatula",
            "TFT_Item_SparringGloves",
        }
        for item in data.get("items", []):
            if item.get("apiName", "") in base_ids:
                items.append({
                    "id": item["apiName"],
                    "name": item.get("name", ""),
                    "composition": [],
                    "desc": item.get("desc", ""),
                    "icon": item.get("icon", ""),
                    "is_base": True,
                })

        _save_cache(cache_name, items)
        return items

    def fetch_tft_traits(self, force: bool = False) -> list[dict]:
        """获取当前赛季 TFT 羁绊数据"""
        cache_name = "tft_traits"
        if not force and _is_cache_valid(cache_name, ttl_hours=24):
            return _load_cache(cache_name)

        data = self._fetch_tft_data(force)
        current_set = data.get("sets", {}).get(self.CURRENT_SET, {})
        traits = []
        for t in current_set.get("traits", []):
            effects = t.get("effects", [])
            breakpoints = [e.get("minUnits", 0) for e in effects if e.get("minUnits", 0) > 0]
            traits.append({
                "id": t.get("apiName", ""),
                "name": t.get("name", ""),
                "breakpoints": breakpoints,
                "effects": [
                    {
                        "min_units": e.get("minUnits", 0),
                        "max_units": e.get("maxUnits", 0),
                        "desc": e.get("desc", ""),
                    }
                    for e in effects
                ],
            })
        _save_cache(cache_name, traits)
        return traits
