from __future__ import annotations

import os
import sys
from pathlib import Path

from paper_ai_reader.config import (
    GUI_CONFIG_PATH,
    Settings,
    load_settings,
    save_app_config,
)
from paper_ai_reader.gui.i18n import SUPPORTED_UI_LANGUAGES, tr
from paper_ai_reader.pipeline import PipelineRunner
from paper_ai_reader.prompts import (
    PROMPT_LANGUAGE_LABELS,
    ensure_prompt_xml,
    get_prompt,
    prompt_path,
    write_prompt_xml,
)

os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")


THEME_MODES = ("system", "light", "dark")

try:
    from PySide6.QtCore import QEvent, QObject, QThread, QTimer, QUrl, Signal, Slot
    from PySide6.QtGui import QAction, QDesktopServices, QFontDatabase, QPalette
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QComboBox,
        QFormLayout,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QStackedWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - only reached without GUI deps
    raise SystemExit("Please install PySide6 first: pip install -r requirements.txt") from exc


class PipelineWorker(QObject):
    log = Signal(str)
    status = Signal(str)
    conversation = Signal(str, str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.stop_requested = False

    @Slot()
    def run(self) -> None:
        try:
            runner = PipelineRunner(
                self.settings,
                log_callback=self.log.emit,
                status_callback=self.status.emit,
                conversation_callback=self.conversation.emit,
                should_stop=lambda: self.stop_requested,
            )
            runner.run()
            self.finished.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

    def request_stop(self) -> None:
        self.stop_requested = True


class DashboardPage(QWidget):
    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, language: str) -> None:
        super().__init__()
        self.language = language
        self.status_state = "idle"
        self.status_dot = QFrame()
        self.title_label = QLabel()
        self.subtitle_label = QLabel()
        self.log_title = QLabel()
        self.log_subtitle = QLabel()
        self.conversation_title = QLabel()
        self.conversation_subtitle = QLabel()
        self.start_button = QPushButton()
        self.stop_button = QPushButton()
        self.log_view = QPlainTextEdit()
        self.conversation_view = QPlainTextEdit()
        self.hint_label = QLabel()
        self._build()
        self.retranslate(language)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("FloatingHeader")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_text = QVBoxLayout()
        self.title_label.setObjectName("PageTitle")
        self.subtitle_label.setObjectName("PageSubtitle")
        self.subtitle_label.setWordWrap(True)
        hero_text.addWidget(self.title_label)
        hero_text.addWidget(self.subtitle_label)
        hero_layout.addLayout(hero_text, 1)

        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setFixedSize(16, 16)
        self.start_button.clicked.connect(self.start_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        actions = QHBoxLayout()
        actions.addWidget(self.status_dot)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        hero_layout.addLayout(actions)
        layout.addWidget(hero)

        self.hint_label.setWordWrap(True)
        self.hint_label.setObjectName("HintText")
        layout.addWidget(self.hint_label)

        panes = QHBoxLayout()
        panes.setSpacing(18)
        log_frame = self._make_panel(self.log_title, self.log_subtitle, self.log_view)
        conversation_frame = self._make_panel(
            self.conversation_title,
            self.conversation_subtitle,
            self.conversation_view,
        )
        panes.addWidget(log_frame, 1)
        panes.addWidget(conversation_frame, 1)
        layout.addLayout(panes, 1)

        self.log_view.setReadOnly(True)
        self.conversation_view.setReadOnly(True)
        self.stop_button.setEnabled(False)

    def _make_panel(
        self,
        title: QLabel,
        subtitle: QLabel,
        editor: QPlainTextEdit,
    ) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        panel_layout = QVBoxLayout(frame)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(10)
        title.setObjectName("CardTitle")
        subtitle.setObjectName("CardSubtitle")
        subtitle.setWordWrap(True)
        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)
        panel_layout.addWidget(editor)
        return frame

    def retranslate(self, language: str) -> None:
        self.language = language
        self.title_label.setText(tr(language, "dashboard_title"))
        self.subtitle_label.setText(tr(language, "dashboard_subtitle"))
        self.start_button.setText(tr(language, "start"))
        self.stop_button.setText(tr(language, "stop"))
        self.log_title.setText(tr(language, "activity_log"))
        self.log_subtitle.setText(tr(language, "log_subtitle"))
        self.conversation_title.setText(tr(language, "conversation"))
        self.conversation_subtitle.setText(tr(language, "conversation_subtitle"))
        self.hint_label.setText(tr(language, "conversation_hint"))
        self._refresh_status_text()

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        if running:
            self.set_status_state("running", tr(self.language, "status_running"))

    def set_status(self, status: str) -> None:
        self.status_dot.setToolTip(status)

    def set_status_state(self, state: str, text: str | None = None) -> None:
        self.status_state = state
        self.status_dot.setToolTip(text or tr(self.language, f"status_{state}"))
        dot_colors = {
            "idle": "#9b9b9b",
            "running": "#d97706",
            "done": "#16a34a",
        }
        self.status_dot.setStyleSheet(
            f"background: {dot_colors.get(state, dot_colors['idle'])}; border-radius: 8px;"
        )

    def _refresh_status_text(self) -> None:
        self.set_status_state(self.status_state)

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def append_conversation(self, role: str, content: str) -> None:
        preview = content
        self.conversation_view.appendPlainText(f"\n[{role.upper()}]\n{preview}\n")


class SettingPage(QWidget):
    saved = Signal(object)

    def __init__(self, settings: Settings, language: str) -> None:
        super().__init__()
        self.settings = settings
        self.language = language
        self.title_label = QLabel()
        self.subtitle_label = QLabel()
        self.notion_token_input = QLineEdit()
        self.notion_database_id_input = QLineEdit()
        self.ai_api_key_input = QLineEdit()
        self.ai_base_url_input = QLineEdit()
        self.ai_model_input = QLineEdit()
        self.paper_text_limit_input = QSpinBox()
        self.save_button = QPushButton()
        self.open_config_button = QPushButton()
        self.form = QFormLayout()
        self.form_labels: dict[str, QLabel] = {}
        self._build()
        self.load_settings(settings)
        self.retranslate(language)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("FloatingHeader")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        self.title_label.setObjectName("PageTitle")
        self.subtitle_label.setObjectName("PageSubtitle")
        self.subtitle_label.setWordWrap(True)
        hero_layout.addWidget(self.title_label)
        hero_layout.addWidget(self.subtitle_label)
        outer.addWidget(hero)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.ai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.paper_text_limit_input.setRange(1_000, 300_000)
        self.paper_text_limit_input.setSingleStep(5_000)

        self.save_button.clicked.connect(self._save)
        self.open_config_button.clicked.connect(lambda: self._open_file(GUI_CONFIG_PATH))

        connection_card = QFrame()
        connection_card.setObjectName("Card")
        connection_layout = QVBoxLayout(connection_card)
        connection_layout.setContentsMargins(20, 20, 20, 20)
        self.connection_title = QLabel()
        self.connection_title.setObjectName("CardTitle")
        connection_layout.addWidget(self.connection_title)
        connection_layout.addLayout(self.form)
        layout.addWidget(connection_card)

        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(14, 14, 14, 14)
        buttons.addStretch(1)
        buttons.addWidget(self.open_config_button)
        buttons.addWidget(self.save_button)
        button_bar = QFrame()
        button_bar.setObjectName("FloatingBar")
        button_bar.setLayout(buttons)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        outer.addWidget(button_bar)

    def load_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.notion_token_input.setText(settings.notion_token)
        self.notion_database_id_input.setText(settings.notion_database_id)
        self.ai_api_key_input.setText(settings.ai_api_key)
        self.ai_base_url_input.setText(settings.ai_base_url or "")
        self.ai_model_input.setText(settings.ai_model)
        self.paper_text_limit_input.setValue(settings.paper_text_limit)

    def retranslate(self, language: str) -> None:
        self.language = language
        self.title_label.setText(tr(language, "setting_title"))
        self.subtitle_label.setText(tr(language, "setting_subtitle"))
        self.connection_title.setText(tr(language, "connection_card"))
        self.save_button.setText(tr(language, "save"))
        self.open_config_button.setText(tr(language, "open_config"))
        self._rebuild_form()

    def _rebuild_form(self) -> None:
        rows = [
            ("notion_token", self.notion_token_input),
            ("notion_database_id", self.notion_database_id_input),
            ("ai_api_key", self.ai_api_key_input),
            ("ai_base_url", self.ai_base_url_input),
            ("ai_model", self.ai_model_input),
            ("paper_text_limit", self.paper_text_limit_input),
        ]
        if not self.form_labels:
            for key, widget in rows:
                label = QLabel()
                self.form_labels[key] = label
                self.form.addRow(label, widget)
        for key, label in self.form_labels.items():
            label.setText(tr(self.language, key))
        self.ai_base_url_input.setPlaceholderText(tr(self.language, "ai_base_url_hint"))

    def current_settings(self) -> Settings:
        return Settings(
            notion_token=self.notion_token_input.text().strip(),
            notion_database_id=self.notion_database_id_input.text().strip(),
            ai_api_key=self.ai_api_key_input.text().strip(),
            ai_model=self.ai_model_input.text().strip(),
            ai_base_url=self.ai_base_url_input.text().strip() or None,
            paper_text_limit=self.paper_text_limit_input.value(),
            ui_language=self.language,
            theme_mode=self.settings.theme_mode,
            prompt_language=self.settings.prompt_language,
            prompt=self.settings.prompt,
            profile="gui",
        )

    def _save(self) -> None:
        settings = self.current_settings()
        save_app_config(settings, profile="gui")
        self.saved.emit(settings)
        QMessageBox.information(self, tr(self.language, "saved"), tr(self.language, "saved_message"))

    def _open_file(self, path: Path) -> None:
        save_app_config(self.current_settings(), profile="gui")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


class PromptPage(QWidget):
    saved = Signal(object)

    def __init__(self, settings: Settings, language: str) -> None:
        super().__init__()
        self.settings = settings
        self.language = language
        self.title_label = QLabel()
        self.subtitle_label = QLabel()
        self.prompt_language_label = QLabel()
        self.prompt_editor_label = QLabel()
        self.prompt_language_combo = QComboBox()
        self.prompt_editor = QTextEdit()
        self.load_default_prompt_button = QPushButton()
        self.save_button = QPushButton()
        self.open_prompt_button = QPushButton()
        self._build()
        self.load_settings(settings)
        self.retranslate(language)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("FloatingHeader")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        self.title_label.setObjectName("PageTitle")
        self.subtitle_label.setObjectName("PageSubtitle")
        self.subtitle_label.setWordWrap(True)
        hero_layout.addWidget(self.title_label)
        hero_layout.addWidget(self.subtitle_label)
        outer.addWidget(hero)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 30)
        card_layout.setSpacing(14)
        for code, label in PROMPT_LANGUAGE_LABELS.items():
            self.prompt_language_combo.addItem(label, code)
        self.prompt_editor.setMinimumHeight(260)
        self.prompt_editor.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.prompt_language_combo.currentIndexChanged.connect(self._load_default_prompt_for_selection)
        self.prompt_language_label.setObjectName("CardSubtitle")
        self.prompt_editor_label.setObjectName("CardSubtitle")
        card_layout.addWidget(self.prompt_language_label)
        card_layout.addWidget(self.prompt_language_combo)
        card_layout.addWidget(self.prompt_editor_label)
        card_layout.addWidget(self.prompt_editor, 1)
        outer.addWidget(card, 1)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(14, 14, 14, 14)
        buttons.addWidget(self.load_default_prompt_button)
        buttons.addStretch(1)
        buttons.addWidget(self.open_prompt_button)
        buttons.addWidget(self.save_button)
        button_bar = QFrame()
        button_bar.setObjectName("FloatingBar")
        button_bar.setLayout(buttons)
        outer.addWidget(button_bar)

        self.load_default_prompt_button.clicked.connect(self._load_default_prompt_for_selection)
        self.save_button.clicked.connect(self._save)
        self.open_prompt_button.clicked.connect(lambda: self._open_file())

    def load_settings(self, settings: Settings) -> None:
        self.settings = settings
        self._set_combo_value(self.prompt_language_combo, settings.prompt_language)
        self.prompt_editor.setPlainText(get_prompt("gui", settings.prompt_language))

    def retranslate(self, language: str) -> None:
        self.language = language
        self.title_label.setText(tr(language, "prompt_title_page"))
        self.subtitle_label.setText(tr(language, "prompt_subtitle_page"))
        self.prompt_language_label.setText(tr(language, "prompt_language"))
        self.prompt_editor_label.setText(tr(language, "prompt"))
        self.load_default_prompt_button.setText(tr(language, "load_default_prompt"))
        self.save_button.setText(tr(language, "save"))
        self.open_prompt_button.setText(tr(language, "open_prompt"))

    def apply_to_settings(self, settings: Settings) -> Settings:
        settings.profile = "gui"
        settings.prompt_language = self.prompt_language_combo.currentData()
        settings.prompt = self.prompt_editor.toPlainText().strip()
        return settings

    def _save(self) -> None:
        settings = self.apply_to_settings(self.settings)
        save_app_config(settings, profile="gui")
        write_prompt_xml(
            path=prompt_path("gui", settings.prompt_language),
            profile="gui",
            language=settings.prompt_language,
            content=settings.prompt,
        )
        self.saved.emit(settings)
        QMessageBox.information(self, tr(self.language, "saved"), tr(self.language, "saved_message"))

    def _load_default_prompt_for_selection(self) -> None:
        language = self.prompt_language_combo.currentData()
        if language:
            self.prompt_editor.setPlainText(get_prompt("gui", language))

    def _open_file(self) -> None:
        language = self.prompt_language_combo.currentData()
        path = ensure_prompt_xml("gui", language)
        write_prompt_xml(
            path=path,
            profile="gui",
            language=language,
            content=self.prompt_editor.toPlainText(),
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings(validate_required=False, profile="gui")
        self.language = self.settings.ui_language if self.settings.ui_language in SUPPORTED_UI_LANGUAGES else "zh"
        self.thread: QThread | None = None
        self.worker: PipelineWorker | None = None

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.dashboard_button = QPushButton()
        self.prompt_button = QPushButton()
        self.edit_button = QPushButton()
        self.language_button = QPushButton()
        self.language_menu = QMenu(self)
        self.theme_button = QPushButton()
        self.theme_menu = QMenu(self)
        self.stack = QStackedWidget()
        self.theme_mode = self.settings.theme_mode if self.settings.theme_mode in THEME_MODES else "system"
        self.current_colors = self._palette_for_dark(self._effective_dark())
        self.target_colors = self.current_colors
        self.theme_frames: list[dict[str, str]] = []
        self.theme_timer = QTimer(self)
        self.theme_timer.setInterval(16)
        self.theme_timer.timeout.connect(self._advance_theme_animation)
        self.palette_debounce = QTimer(self)
        self.palette_debounce.setSingleShot(True)
        self.palette_debounce.setInterval(90)
        self.palette_debounce.timeout.connect(lambda: self._request_theme_update(animated=True))
        self.dashboard = DashboardPage(self.language)
        self.prompt_page = PromptPage(self.settings, self.language)
        self.setting_page = SettingPage(self.settings, self.language)
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.prompt_page)
        self.stack.addWidget(self.setting_page)
        self._build_shell()

        self.dashboard.start_requested.connect(self.start_pipeline)
        self.dashboard.stop_requested.connect(self.stop_pipeline)
        self.prompt_page.saved.connect(self.update_settings)
        self.setting_page.saved.connect(self.update_settings)

        self.setMinimumSize(1180, 780)
        self._apply_style()
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(tr(self.language, "app_title"))
        self.brand_title.setText(tr(self.language, "app_title"))
        self.brand_subtitle.setText(tr(self.language, "app_subtitle"))
        self.dashboard_button.setText(f"  🧭  {tr(self.language, 'dashboard')}")
        self.prompt_button.setText(f"  ✍️  {tr(self.language, 'prompt_nav')}")
        self.edit_button.setText(f"  ⚙️  {tr(self.language, 'setting')}")
        self.language_button.setText(f"🌐 {SUPPORTED_UI_LANGUAGES[self.language]}")
        self.theme_button.setText(f"◐ {tr(self.language, f'theme_short_{self.theme_mode}')}")
        self.dashboard.retranslate(self.language)
        self.prompt_page.retranslate(self.language)
        self.setting_page.retranslate(self.language)

    def _build_shell(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(22, 26, 22, 22)
        sidebar_layout.setSpacing(14)
        self.sidebar.setFixedWidth(260)

        self.brand_title = QLabel()
        self.brand_title.setObjectName("BrandTitle")
        self.brand_subtitle = QLabel()
        self.brand_subtitle.setObjectName("BrandSubtitle")
        self.brand_subtitle.setWordWrap(True)
        sidebar_layout.addWidget(self.brand_title)
        sidebar_layout.addWidget(self.brand_subtitle)
        sidebar_layout.addSpacing(22)

        for index, button in enumerate([self.dashboard_button, self.prompt_button, self.edit_button]):
            button.setCheckable(True)
            button.setObjectName("NavButton")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.nav_group.addButton(button, index)
            sidebar_layout.addWidget(button)
        self.dashboard_button.setChecked(True)
        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        sidebar_layout.addStretch(1)

        bottom_actions = QHBoxLayout()
        bottom_actions.setSpacing(8)

        self.language_button.setObjectName("BottomMenuButton")
        self.language_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build_language_menu()
        self.language_button.setMenu(self.language_menu)
        bottom_actions.addWidget(self.language_button, 1)

        self.theme_button.setObjectName("BottomMenuButton")
        self.theme_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build_theme_menu()
        self.theme_button.setMenu(self.theme_menu)
        bottom_actions.addWidget(self.theme_button, 1)
        sidebar_layout.addLayout(bottom_actions)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def _build_language_menu(self) -> None:
        self.language_menu.clear()
        for code, label in SUPPORTED_UI_LANGUAGES.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(code == self.language)
            action.triggered.connect(lambda checked=False, selected=code: self.set_language(selected))
            self.language_menu.addAction(action)

    def _build_theme_menu(self) -> None:
        self.theme_menu.clear()
        for mode in THEME_MODES:
            action = QAction(tr(self.language, f"theme_{mode}"), self)
            action.setCheckable(True)
            action.setChecked(mode == self.theme_mode)
            action.triggered.connect(lambda checked=False, selected=mode: self.set_theme_mode(selected))
            self.theme_menu.addAction(action)

    @Slot(str)
    def set_language(self, language: str) -> None:
        self.language = language
        self.settings.ui_language = language
        self._build_language_menu()
        self._build_theme_menu()
        self.retranslate()

    @Slot(str)
    def set_theme_mode(self, mode: str) -> None:
        if mode not in THEME_MODES:
            return
        self.theme_mode = mode
        self.settings = self.setting_page.current_settings()
        self.settings = self.prompt_page.apply_to_settings(self.settings)
        self.settings.ui_language = self.language
        self.settings.theme_mode = mode
        self.setting_page.settings.theme_mode = mode
        self.prompt_page.settings.theme_mode = mode
        save_app_config(self.settings, profile="gui")
        self._build_theme_menu()
        self.retranslate()
        self._request_theme_update(animated=True)

    @Slot(Settings)
    def update_settings(self, settings: Settings) -> None:
        settings.theme_mode = self.theme_mode
        self.settings = settings
        self.setting_page.settings = settings
        self.prompt_page.settings = settings

    @Slot()
    def start_pipeline(self) -> None:
        self.settings = self.setting_page.current_settings()
        self.settings = self.prompt_page.apply_to_settings(self.settings)
        self.settings.theme_mode = self.theme_mode
        self.dashboard.log_view.clear()
        self.dashboard.conversation_view.clear()
        self.dashboard.set_running(True)
        self.dashboard.set_status_state("running")

        self.thread = QThread()
        self.worker = PipelineWorker(self.settings)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.dashboard.append_log)
        self.worker.status.connect(self.dashboard.set_status)
        self.worker.conversation.connect(self.dashboard.append_conversation)
        self.worker.failed.connect(self._pipeline_failed)
        self.worker.finished.connect(self._pipeline_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._clear_thread)
        self.thread.start()

    @Slot()
    def stop_pipeline(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.dashboard.append_log(tr(self.language, "stopping"))

    @Slot()
    def _pipeline_finished(self) -> None:
        self.dashboard.set_running(False)
        self.dashboard.set_status_state("done")

    @Slot(str)
    def _pipeline_failed(self, message: str) -> None:
        self.dashboard.set_running(False)
        self.dashboard.set_status_state("idle")
        self.dashboard.append_log(f"{tr(self.language, 'error')}: {message}")
        QMessageBox.critical(self, tr(self.language, "error"), message)

    @Slot()
    def _clear_thread(self) -> None:
        self.thread = None
        self.worker = None

    def changeEvent(self, event: QEvent) -> None:
        if event.type() in {
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.PaletteChange,
        }:
            if self.theme_mode == "system":
                self.palette_debounce.start()
        super().changeEvent(event)

    def _apply_style(self) -> None:
        self._set_style_colors(self.current_colors)

    def _set_style_colors(self, colors: dict[str, str]) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: %(window)s;
                color: %(text)s;
                font-size: 14px;
            }
            QFrame#Sidebar {
                background: %(sidebar)s;
                border: none;
            }
            QLabel#BrandTitle {
                color: %(text)s;
                font-size: 22px;
                font-weight: 760;
            }
            QLabel#BrandSubtitle {
                color: %(muted)s;
                font-size: 13px;
                line-height: 1.4;
            }
            QLabel {
                background: transparent;
            }
            QPushButton#NavButton, QPushButton#BottomMenuButton {
                text-align: left;
                background: transparent;
                color: %(text)s;
                border-radius: 8px;
                padding: 9px 10px;
                font-weight: 600;
            }
            QPushButton#NavButton:hover, QPushButton#BottomMenuButton:hover {
                background: %(nav_hover)s;
            }
            QPushButton#NavButton:checked {
                background: %(nav_checked)s;
                color: %(text)s;
            }
            QMenu {
                background: %(surface)s;
                color: %(text)s;
                border: 1px solid %(border)s;
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item {
                border-radius: 7px;
                padding: 8px 28px 8px 14px;
            }
            QMenu::item:selected {
                background: %(nav_hover)s;
            }
            QFrame#FloatingHeader {
                border: 1px solid %(border)s;
                border-radius: 18px;
                background: %(surface)s;
            }
            QFrame#Card {
                border: 1px solid %(border)s;
                border-radius: 14px;
                background: %(surface)s;
            }
            QFrame#FloatingBar {
                border: 1px solid %(border)s;
                border-radius: 18px;
                background: %(surface)s;
            }
            QLabel#PageTitle {
                color: %(text)s;
                font-size: 27px;
                font-weight: 760;
            }
            QLabel#PageSubtitle, QLabel#CardSubtitle, QLabel#HintText {
                color: %(muted)s;
                font-size: 13px;
            }
            QLabel#CardTitle {
                color: %(text)s;
                font-size: 16px;
                font-weight: 700;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 9px 14px;
                background: %(button)s;
                color: %(button_text)s;
                font-weight: 650;
            }
            QPushButton:hover {
                background: %(button_hover)s;
            }
            QPushButton:disabled {
                background: %(surface_3)s;
                color: %(muted)s;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
                border: 1px solid %(border)s;
                border-radius: 9px;
                padding: 9px;
                background: %(surface_2)s;
                color: %(text)s;
                selection-background-color: %(selection)s;
            }
            QTextEdit {
                padding: 14px;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid %(border_focus)s;
                background: %(surface)s;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 8px 2px 8px 2px;
            }
            QScrollBar::handle:vertical {
                background: %(scroll_handle)s;
                min-height: 44px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
                height: 0px;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 10px;
                margin: 2px 8px 2px 8px;
            }
            QScrollBar::handle:horizontal {
                background: %(scroll_handle)s;
                min-width: 44px;
                border-radius: 5px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
                border: none;
                width: 0px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                border: none;
                background: transparent;
                width: 22px;
                margin: 2px;
                border-radius: 6px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: %(nav_hover)s;
            }
            QSpinBox::up-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid %(muted)s;
            }
            QSpinBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid %(muted)s;
            }
            QScrollArea {
                border: none;
                background: %(window)s;
            }
            QScrollArea > QWidget > QWidget {
                background: %(window)s;
            }
            QPlainTextEdit, QTextEdit {
                font-family: "Menlo", "Monaco", "Consolas", monospace;
                font-size: 12px;
            }
            QFrame#StatusDot {
                border: none;
            }
            """
            % colors
        )

    def _request_theme_update(self, animated: bool) -> None:
        target = self._palette_for_dark(self._effective_dark())
        if target == self.current_colors:
            return
        self.target_colors = target
        if not animated:
            self.current_colors = target
            self._set_style_colors(target)
            return
        self.theme_frames = self._build_theme_frames(self.current_colors, target, steps=10)
        if not self.theme_timer.isActive():
            self.theme_timer.start()

    def _advance_theme_animation(self) -> None:
        if not self.theme_frames:
            self.theme_timer.stop()
            self.current_colors = self.target_colors
            self._set_style_colors(self.current_colors)
            return
        self.current_colors = self.theme_frames.pop(0)
        self._set_style_colors(self.current_colors)

    def _effective_dark(self) -> bool:
        if self.theme_mode == "dark":
            return True
        if self.theme_mode == "light":
            return False
        return self._system_dark_mode()

    def _system_dark_mode(self) -> bool:
        app = QApplication.instance()
        if not app:
            return False
        color = app.palette().color(QPalette.ColorRole.Window)
        return color.lightness() < 128

    def _palette_for_dark(self, dark: bool) -> dict[str, str]:
        if dark:
            return {
                "window": "#191919",
                "sidebar": "#191919",
                "surface": "#191919",
                "surface_2": "#202020",
                "surface_3": "#2f2f2f",
                "border": "#333333",
                "border_focus": "#6b7280",
                "text": "#e6e6e6",
                "muted": "#9b9b9b",
                "button": "#e6e6e6",
                "button_hover": "#ffffff",
                "button_text": "#191919",
                "nav_hover": "#2a2a2a",
                "nav_checked": "#333333",
                "status_bg": "#2f2f2f",
                "status_text": "#e6e6e6",
                "scroll_handle": "#555555",
                "selection": "#3b82f6",
            }
        return {
            "window": "#ffffff",
            "sidebar": "#ffffff",
            "surface": "#ffffff",
            "surface_2": "#f7f7f5",
            "surface_3": "#eeeeec",
            "border": "#e6e6e4",
            "border_focus": "#9ca3af",
            "text": "#2f3437",
            "muted": "#6f6f6a",
            "button": "#2f3437",
            "button_hover": "#111111",
            "button_text": "#ffffff",
            "nav_hover": "#f1f1ef",
            "nav_checked": "#eeeeec",
                "status_bg": "#eeeeec",
                "status_text": "#37352f",
                "scroll_handle": "#d8d8d4",
                "selection": "#bcd7ff",
        }

    def _build_theme_frames(
        self,
        start: dict[str, str],
        end: dict[str, str],
        steps: int,
    ) -> list[dict[str, str]]:
        return [
            {
                key: self._mix_hex(start[key], end[key], step / steps)
                for key in start
            }
            for step in range(1, steps + 1)
        ]

    def _mix_hex(self, start: str, end: str, amount: float) -> str:
        start_rgb = tuple(int(start[index : index + 2], 16) for index in (1, 3, 5))
        end_rgb = tuple(int(end[index : index + 2], 16) for index in (1, 3, 5))
        mixed = tuple(
            round(start_value + (end_value - start_value) * amount)
            for start_value, end_value in zip(start_rgb, end_rgb)
        )
        return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
