# 云顶助手 - TFT Helper

基于 PyQt6 + OpenCV 的云顶之弈实时助手工具。

## 功能

- **阵容推荐** — 根据场上棋子匹配热门阵容，计算牌池可行性和对手竞争度
- **装备合成** — 完整合成表 + 根据阵容推荐最优出装
- **牌池追踪** — 实时追踪共享牌池剩余，评估三星可行性
- **屏幕识别** — 模板匹配识别英雄头像 + OCR 识别回合/金币/血量
- **PyQt6 GUI** — 深色主题图形界面，5 个功能 Tab

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Standieyoung/tft-helper.git
cd tft-helper
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate    # macOS / Linux
# venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 3. 首次运行（加载游戏数据）

```bash
python main.py
```

首次运行会从 Community Dragon 拉取英雄、装备、羁绊数据并缓存到 `data/cache/`。

### 4. 启动图形界面

```bash
python main.py --ui
```

## 所有命令

| 命令 | 说明 |
|------|------|
| `python main.py --ui` | 启动图形界面 |
| `python main.py --demo` | 演示决策引擎（无需游戏运行） |
| `python main.py --calibrate` | 屏幕坐标校准工具 |
| `python main.py --download-icons` | 下载/更新英雄头像和装备图标 |
| `python main.py --update-comps` | 查看当前阵容数据 |

## 阵容数据管理

```bash
python scripts/update_comps.py list             # 查看所有阵容
python scripts/update_comps.py add              # 交互式添加阵容
python scripts/update_comps.py delete           # 删除阵容
python scripts/update_comps.py tier             # 批量更新评级
python scripts/update_comps.py import <file>    # 从 JSON 文件导入阵容
python scripts/update_comps.py refresh          # 强制从网络刷新
python scripts/update_comps.py api              # 配置 DataTFT API 端点
```

## 屏幕校准

不同分辨率需要校准屏幕坐标，确保识别区域准确：

```bash
python main.py --calibrate
```

按提示依次点击商店、棋盘、备战席等区域，校准结果自动保存到 `config_screen.json`。

## 项目结构

```
tft-helper/
├── main.py                 # 主入口
├── config.yaml             # 配置（牌池、升级概率、识别参数）
├── requirements.txt        # Python 依赖
├── advisor/                # 决策引擎
│   ├── comp_advisor.py     # 阵容推荐 & 三星追踪 & D牌概率
│   └── item_advisor.py     # 装备合成推荐
├── data/                   # 数据层
│   ├── models.py           # 数据模型
│   ├── scraper.py          # Community Dragon + DataTFT 数据抓取
│   └── cache/              # 缓存（英雄/装备/羁绊/阵容 JSON）
├── recognition/            # 屏幕识别
│   ├── screen_capture.py   # 截图 & 区域定位
│   ├── game_state.py       # 游戏状态解析
│   └── image_match.py      # 模板匹配
├── ui/                     # 图形界面
│   └── main_window.py      # PyQt6 主窗口
├── scripts/                # 工具脚本
│   ├── calibrate_screen.py # 坐标校准
│   ├── download_icons.py   # 图标下载
│   └── update_comps.py     # 阵容管理
└── assets/                 # 资源文件
    ├── champions/          # 英雄头像 (101个)
    └── items/              # 装备图标 (60个)
```

## 依赖

- Python 3.11+
- PyQt6 — GUI 界面
- OpenCV — 图像识别
- pytesseract — OCR 文字识别（需要安装 [Tesseract](https://github.com/tesseract-ocr/tesseract)）
- mss — 屏幕截图
- httpx — 网络请求

## 注意事项

- macOS 用户使用屏幕截图功能需要在 **系统设置 → 隐私与安全性 → 屏幕录制** 中授权终端或 IDE
- Tesseract OCR 需要单独安装：`brew install tesseract`（macOS）或 `apt install tesseract-ocr`（Linux）
- 阵容数据建议每次版本更新后手动维护 `data/cache/comps.json`
