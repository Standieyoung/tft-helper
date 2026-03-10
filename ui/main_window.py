"""主界面 - PyQt6"""

import sys
import yaml
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QGroupBox,
    QProgressBar, QComboBox, QHeaderView, QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPixmap, QIcon

from data.models import Champion, Comp, Item, GameState, PlayerBoard, PoolTracker, POOL_SIZE


CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
ASSETS_DIR = Path(__file__).parent.parent / "assets"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


class MainWindow(QMainWindow):
    """TFT Helper 主窗口"""

    def __init__(
        self,
        champion_db: dict[str, Champion] | None = None,
        comp_db: list[Comp] | None = None,
        items_raw: list[dict] | None = None,
    ):
        super().__init__()
        self.config = load_config()
        self.champion_db = champion_db or {}
        self.comp_db = comp_db or []
        self.items_raw = items_raw or []
        self.monitoring = False

        self.setWindowTitle("云顶助手 - TFT Helper")
        self.setMinimumSize(1000, 700)
        self._setup_ui()
        self._populate_data()

    def _setup_ui(self):
        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        tabs.addTab(self._create_live_tab(), "实时助手")
        tabs.addTab(self._create_comps_tab(), "热门阵容")
        tabs.addTab(self._create_items_tab(), "装备合成")
        tabs.addTab(self._create_pool_tab(), "牌池追踪")
        tabs.addTab(self._create_augments_tab(), "强化评级")

        self.statusBar().showMessage("就绪 - 等待游戏启动")

    def _create_live_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        control_bar = QHBoxLayout()
        self.btn_start = QPushButton("开始监控")
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 16px;")
        self.btn_stop = QPushButton("停止监控")
        self.btn_stop.setEnabled(False)
        self.lbl_status = QLabel("状态: 未连接")
        self.lbl_round = QLabel("回合: -")
        self.lbl_round.setFont(QFont("Arial", 14, QFont.Weight.Bold))

        self.btn_start.clicked.connect(self._on_start_monitoring)
        self.btn_stop.clicked.connect(self._on_stop_monitoring)

        control_bar.addWidget(self.btn_start)
        control_bar.addWidget(self.btn_stop)
        control_bar.addStretch()
        control_bar.addWidget(self.lbl_round)
        control_bar.addWidget(self.lbl_status)
        layout.addLayout(control_bar)

        mid_layout = QHBoxLayout()

        comp_group = QGroupBox("阵容推荐")
        comp_layout = QVBoxLayout(comp_group)
        self.comp_recommendations = QTextEdit()
        self.comp_recommendations.setReadOnly(True)
        self.comp_recommendations.setPlaceholderText(
            "开始监控后，将根据你的场上英雄实时推荐最佳阵容...\n\n"
            "功能:\n"
            "- 匹配当前棋子到热门阵容\n"
            "- 计算牌池可行性\n"
            "- 检测对手竞争度\n"
            "- 推荐下一步购买"
        )
        comp_layout.addWidget(self.comp_recommendations)
        mid_layout.addWidget(comp_group, stretch=2)

        alert_group = QGroupBox("实时提醒")
        alert_layout = QVBoxLayout(alert_group)
        self.alerts_text = QTextEdit()
        self.alerts_text.setReadOnly(True)
        self.alerts_text.setPlaceholderText(
            "这里会显示:\n\n"
            "🔴 三星追踪提醒\n"
            "⚠️ 卡牌/被抢警告\n"
            "💰 经济建议\n"
            "📊 D牌概率"
        )
        alert_layout.addWidget(self.alerts_text)
        mid_layout.addWidget(alert_group, stretch=1)

        layout.addLayout(mid_layout)

        status_group = QGroupBox("当前状态")
        status_layout = QHBoxLayout(status_group)
        self.lbl_level = QLabel("等级: -")
        self.lbl_gold = QLabel("金币: -")
        self.lbl_hp = QLabel("血量: -")
        self.lbl_board = QLabel("场上: -")
        for lbl in [self.lbl_level, self.lbl_gold, self.lbl_hp, self.lbl_board]:
            lbl.setFont(QFont("Arial", 12))
            status_layout.addWidget(lbl)
        layout.addWidget(status_group)

        return widget

    def _create_comps_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("评级:"))
        self.comp_tier_filter = QComboBox()
        self.comp_tier_filter.addItems(["全部", "S", "A", "B"])
        self.comp_tier_filter.currentTextChanged.connect(self._filter_comps)
        filter_layout.addWidget(self.comp_tier_filter)
        filter_layout.addStretch()
        btn_refresh = QPushButton("刷新数据")
        btn_refresh.clicked.connect(self._refresh_comp_data)
        filter_layout.addWidget(btn_refresh)
        layout.addLayout(filter_layout)

        self.comps_table = QTableWidget()
        self.comps_table.setColumnCount(6)
        self.comps_table.setHorizontalHeaderLabels(
            ["评级", "阵容名称", "核心英雄", "平均名次", "使用率", "难度"]
        )
        header = self.comps_table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.comps_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.comps_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.comps_table.setAlternatingRowColors(True)
        layout.addWidget(self.comps_table)

        return widget

    def _create_items_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("装备合成表", font=QFont("Arial", 16, QFont.Weight.Bold)))

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(3)
        self.items_table.setHorizontalHeaderLabels(["组件 A", "组件 B", "合成装备"])
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.setAlternatingRowColors(True)
        layout.addWidget(self.items_table)

        return widget

    def _create_pool_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("牌池追踪", font=QFont("Arial", 16, QFont.Weight.Bold)))
        layout.addWidget(QLabel(
            "显示每个英雄在共享牌池中的剩余数量。"
            "红色 = 快被拿光，绿色 = 充裕"
        ))

        self.pool_tables: dict[int, QTableWidget] = {}
        for cost in range(1, 6):
            pool_total = self.config.get("card_pool", {}).get(cost, POOL_SIZE.get(cost, "?"))
            group = QGroupBox(f"{cost} 费英雄 (总数: {pool_total})")
            group_layout = QVBoxLayout(group)
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["英雄", "总数", "已知被拿", "剩余"])
            header = table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            group_layout.addWidget(table)
            layout.addWidget(group)
            self.pool_tables[cost] = table

        return widget

    def _create_augments_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("类型:"))
        aug_filter = QComboBox()
        aug_filter.addItems(["全部", "银色", "金色", "彩色"])
        filter_layout.addWidget(aug_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        self.augments_table = QTableWidget()
        self.augments_table.setColumnCount(4)
        self.augments_table.setHorizontalHeaderLabels(["强化名称", "类型", "评级", "适用阵容"])
        header = self.augments_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.augments_table)

        return widget

    # --- 数据填充 ---

    def _populate_data(self):
        """用加载的数据填充所有 Tab"""
        self._populate_comps_table()
        self._populate_items_table()
        self._populate_pool_tables()

    def _populate_comps_table(self, tier_filter: str = "全部"):
        comps = self.comp_db
        if tier_filter != "全部":
            comps = [c for c in comps if c.tier == tier_filter]

        self.comps_table.setRowCount(len(comps))
        tier_colors = {
            "S": QColor(255, 215, 0),
            "A": QColor(192, 192, 255),
            "B": QColor(180, 180, 180),
        }

        for row, comp in enumerate(comps):
            tier_item = QTableWidgetItem(comp.tier)
            tier_item.setForeground(tier_colors.get(comp.tier, QColor(200, 200, 200)))
            tier_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            self.comps_table.setItem(row, 0, tier_item)

            self.comps_table.setItem(row, 1, QTableWidgetItem(comp.name))

            champ_names = []
            for cid in comp.champions:
                champ = self.champion_db.get(cid)
                champ_names.append(champ.name if champ else cid)
            self.comps_table.setItem(row, 2, QTableWidgetItem(", ".join(champ_names)))

            placement_item = QTableWidgetItem(f"{comp.avg_placement:.1f}")
            if comp.avg_placement <= 3.5:
                placement_item.setForeground(QColor(100, 255, 100))
            elif comp.avg_placement >= 4.5:
                placement_item.setForeground(QColor(255, 100, 100))
            self.comps_table.setItem(row, 3, placement_item)

            self.comps_table.setItem(row, 4, QTableWidgetItem(f"{comp.play_rate:.1%}" if comp.play_rate else "-"))

            difficulty = getattr(comp, "difficulty", "") or "-"
            self.comps_table.setItem(row, 5, QTableWidgetItem(difficulty))

        self.comps_table.resizeRowsToContents()

    def _populate_items_table(self):
        items_with_recipe = [i for i in self.items_raw if len(i.get("composition", [])) == 2]

        name_map = {i["id"]: i["name"] for i in self.items_raw}
        self.items_table.setRowCount(len(items_with_recipe))

        for row, item in enumerate(items_with_recipe):
            comp_a = item["composition"][0]
            comp_b = item["composition"][1]
            self.items_table.setItem(row, 0, QTableWidgetItem(name_map.get(comp_a, comp_a)))
            self.items_table.setItem(row, 1, QTableWidgetItem(name_map.get(comp_b, comp_b)))

            result_item = QTableWidgetItem(item["name"])
            result_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.items_table.setItem(row, 2, result_item)

        self.items_table.resizeRowsToContents()

    def _populate_pool_tables(self):
        champs_by_cost: dict[int, list[Champion]] = {i: [] for i in range(1, 6)}
        for champ in self.champion_db.values():
            if champ.cost in champs_by_cost:
                champs_by_cost[champ.cost].append(champ)

        for cost, champs in champs_by_cost.items():
            table = self.pool_tables.get(cost)
            if not table:
                continue

            champs.sort(key=lambda c: c.name)
            table.setRowCount(len(champs))
            total = POOL_SIZE.get(cost, 0)

            for row, champ in enumerate(champs):
                table.setItem(row, 0, QTableWidgetItem(f"{champ.name} ({champ.id})"))
                table.setItem(row, 1, QTableWidgetItem(str(total)))
                table.setItem(row, 2, QTableWidgetItem("0"))

                remaining_item = QTableWidgetItem(str(total))
                remaining_item.setForeground(QColor(100, 255, 100))
                table.setItem(row, 3, remaining_item)

            table.resizeRowsToContents()

    # --- 信号槽 ---

    def _on_start_monitoring(self):
        self.monitoring = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("状态: 监控中...")
        self.lbl_status.setStyleSheet("color: #4CAF50;")
        self.statusBar().showMessage("监控中 - 正在检测游戏画面...")

        self._monitor_timer = QTimer()
        self._monitor_timer.timeout.connect(self._tick_monitor)
        interval = self.config.get("recognition", {}).get("capture_interval_ms", 2000)
        self._monitor_timer.start(interval)

    def _on_stop_monitoring(self):
        self.monitoring = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("状态: 已停止")
        self.lbl_status.setStyleSheet("color: #FF6B6B;")
        self.statusBar().showMessage("监控已停止")

        if hasattr(self, "_monitor_timer"):
            self._monitor_timer.stop()

    def _tick_monitor(self):
        """定时监控回调 — 截图 -> 解析 -> 推荐 -> 刷新 UI"""
        try:
            from recognition.screen_capture import ScreenCapture
            from recognition.game_state import GameStateParser
            from recognition.image_match import TemplateMatcher
            from advisor.comp_advisor import CompAdvisor

            if not hasattr(self, "_screen_capture"):
                self._screen_capture = ScreenCapture()
                self._screen_capture.find_game_window()
            if not hasattr(self, "_matcher"):
                self._matcher = TemplateMatcher(
                    confidence=self.config.get("recognition", {}).get("match_confidence", 0.85)
                )
                self._matcher.load_champion_icons()
                self._matcher.load_item_icons()
            if not hasattr(self, "_state_parser"):
                self._state_parser = GameStateParser(self._screen_capture, self._matcher)
            if not hasattr(self, "_advisor"):
                self._advisor = CompAdvisor(self.champion_db, self.comp_db)

            state = self._state_parser.parse_current_state()
            recs = self._advisor.recommend_comps(state, top_n=3)
            three_star = self._advisor.check_three_star(state)
            contests = self._advisor.check_contests(state)

            self.update_live_recommendations(recs, three_star + contests)
            board_count = len(state.my_board.champions)
            self.update_status(
                state.my_board.level, state.my_board.gold,
                state.my_board.hp, board_count, state.round,
            )

        except ImportError as e:
            self.statusBar().showMessage(f"缺少依赖: {e}")
        except Exception as e:
            self.statusBar().showMessage(f"识别出错: {e}")

    def _filter_comps(self, tier: str):
        self._populate_comps_table(tier)

    def _refresh_comp_data(self):
        self.statusBar().showMessage("正在刷新阵容数据...")
        try:
            from data.scraper import DataTFTScraper
            scraper = DataTFTScraper()
            try:
                comps_raw = scraper.fetch_comps(force=True)
            finally:
                scraper.close()

            self.comp_db = []
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
                self.comp_db.append(comp)

            self._populate_comps_table(self.comp_tier_filter.currentText())
            self.statusBar().showMessage(f"阵容数据已刷新: {len(self.comp_db)} 套")
        except Exception as e:
            self.statusBar().showMessage(f"刷新失败: {e}")

    # --- 数据更新方法 ---

    def update_live_recommendations(self, recommendations: list, alerts: list):
        text = ""
        for i, rec in enumerate(recommendations):
            icon = ["✅", "⚠️", "🔴"][min(i, 2)]
            text += f"{icon} 推荐 #{i+1}: {rec.comp.name}\n"
            text += f"   匹配度: {rec.match_score}% | 竞争: {rec.competition_level}\n"
            text += f"   可行性: {rec.feasibility}% | {rec.reason}\n"
            if rec.missing_champions:
                names = []
                for cid in rec.missing_champions:
                    c = self.champion_db.get(cid)
                    names.append(c.name if c else cid)
                text += f"   还缺: {', '.join(names)}\n"
            text += "\n"
        self.comp_recommendations.setText(text)

        alert_text = ""
        for alert in alerts:
            if hasattr(alert, "probability"):
                alert_text += f"⭐ {alert.champion_name}: "
                alert_text += f"{alert.owned}/9 (还需{alert.needed}张, "
                alert_text += f"池剩{alert.remaining_in_pool})\n"
                alert_text += f"   → {alert.recommendation}\n\n"
            elif hasattr(alert, "alert_type"):
                icons = {"被抢": "🔴", "可卡": "🟡", "池枯": "⚫"}
                alert_text += f"{icons.get(alert.alert_type, '❓')} {alert.message}\n\n"
        self.alerts_text.setText(alert_text)

    def update_status(self, level: int, gold: int, hp: int, board_count: int, round_str: str):
        self.lbl_level.setText(f"等级: {level}")
        self.lbl_gold.setText(f"金币: {gold}")
        self.lbl_hp.setText(f"血量: {hp}")
        self.lbl_board.setText(f"场上: {board_count} 个英雄")
        self.lbl_round.setText(f"回合: {round_str}")


def run_app(
    champion_db: dict[str, Champion] | None = None,
    comp_db: list[Comp] | None = None,
    items_raw: list[dict] | None = None,
):
    """启动应用"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(palette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.Base, QColor(40, 40, 40))
    palette.setColor(palette.ColorRole.AlternateBase, QColor(50, 50, 50))
    palette.setColor(palette.ColorRole.Text, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.Button, QColor(50, 50, 50))
    palette.setColor(palette.ColorRole.ButtonText, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.Highlight, QColor(42, 130, 218))
    app.setPalette(palette)

    window = MainWindow(champion_db, comp_db, items_raw)
    window.show()
    sys.exit(app.exec())
