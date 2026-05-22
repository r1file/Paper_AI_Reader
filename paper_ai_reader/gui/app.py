from __future__ import annotations

import os
import sys
from pathlib import Path

from paper_ai_reader.config import (
    AppState,
    GUI_CONFIG_PATH,
    Settings,
    load_app_state,
    load_settings,
    save_app_state,
    save_settings_xml,
    validate_runtime_files,
)
from paper_ai_reader.backend import PaperAIReaderBackend
from paper_ai_reader.connectivity import CheckResult
from paper_ai_reader.gui.i18n import SUPPORTED_UI_LANGUAGES, tr
from paper_ai_reader.prompts import (
    ensure_prompt_xml,
    get_prompt,
    get_user_prompt_template,
    prompt_path,
    read_system_prompt_xml,
)

os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")


THEME_MODES = ("system", "light", "dark")
LANGUAGE_CYCLE = ("zh", "ja", "en")
LANGUAGE_SHORT_LABELS = {"zh": "🇨🇳 中", "ja": "🇯🇵 日", "en": "🇺🇸 EN"}


def elide_status(text: str, limit: int = 9) -> str:
    clean_text = text.strip()
    return clean_text if len(clean_text) <= limit else f"{clean_text[:limit - 1]}…"


def next_language(language: str) -> str:
    index = LANGUAGE_CYCLE.index(language) if language in LANGUAGE_CYCLE else 0
    return LANGUAGE_CYCLE[(index + 1) % len(LANGUAGE_CYCLE)]


def system_language() -> str:
    locale_name = QLocale.system().name().lower()
    if locale_name.startswith("ja"):
        return "ja"
    if locale_name.startswith("zh"):
        return "zh"
    return "en"

try:
    from PySide6.QtCore import QEvent, QLocale, QObject, Qt, QThread, QTimer, QUrl, Signal, Slot
    from PySide6.QtGui import QAction, QDesktopServices, QFontDatabase, QPalette
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QComboBox,
        QFileDialog,
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
            backend = PaperAIReaderBackend(self.settings)
            backend.run_pipeline(
                log_callback=self.log.emit,
                status_callback=self.status.emit,
                conversation_callback=self.conversation.emit,
                should_stop=lambda: self.stop_requested,
            )
            self.finished.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

    def request_stop(self) -> None:
        self.stop_requested = True


class ConnectivityWorker(QObject):
    log = Signal(str)
    result = Signal(str, object)
    finished = Signal(bool)
    failed = Signal(str)

    def __init__(self, settings: Settings, target: str) -> None:
        super().__init__()
        self.settings = settings
        self.target = target

    @Slot()
    def run(self) -> None:
        try:
            backend = PaperAIReaderBackend(self.settings)
            has_error = False
            if self.target in {"notion", "all"}:
                notion_result = backend.check_notion()
                has_error = has_error or not notion_result.ok
                self.result.emit("notion", notion_result)
                if not notion_result.ok and notion_result.detail:
                    self.log.emit(notion_result.detail)
            if self.target in {"ai", "all"}:
                ai_result = backend.check_ai()
                has_error = has_error or not ai_result.ok
                self.result.emit("ai", ai_result)
                if not ai_result.ok and ai_result.detail:
                    self.log.emit(ai_result.detail)
            self.finished.emit(not has_error)
        except Exception as exc:
            self.failed.emit(str(exc))


class ModelListWorker(QObject):
    log = Signal(str)
    finished = Signal(list, str)
    failed = Signal(str)

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

    @Slot()
    def run(self) -> None:
        try:
            backend = PaperAIReaderBackend(self.settings)
            models = backend.list_ai_models()
            default_model = backend.default_ai_model(models)
            self.finished.emit(models, default_model)
        except Exception as exc:
            self.failed.emit(str(exc))


class DashboardPage(QWidget):
    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, language: str) -> None:
        super().__init__()
        self.language = language
        self.status_state = "idle"
        self.status_capsule = QFrame()
        self.status_dot = QFrame()
        self.status_text_label = QLabel()
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

        self.status_capsule.setObjectName("StatusCapsule")
        self.status_capsule.setFixedSize(136, 44)
        self.status_capsule.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        capsule_layout = QHBoxLayout(self.status_capsule)
        capsule_layout.setContentsMargins(12, 0, 12, 0)
        capsule_layout.setSpacing(8)
        capsule_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setFixedSize(14, 14)
        self.status_dot.setFrameShape(QFrame.Shape.NoFrame)
        self.status_dot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.status_text_label.setObjectName("StatusTextPill")
        self.status_text_label.setFixedSize(86, 26)
        self.status_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capsule_layout.addWidget(self.status_dot)
        capsule_layout.addWidget(self.status_text_label, 1)
        self.start_button.clicked.connect(self.start_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.start_button.setFixedHeight(44)
        self.stop_button.setFixedHeight(44)
        actions = QHBoxLayout()
        actions.setSpacing(14)
        actions.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        actions.addWidget(self.status_capsule)
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
        status_text = self._display_status_text(state, text)
        self.status_dot.setToolTip(status_text)
        self.status_text_label.setText(elide_status(status_text))
        self.status_text_label.setToolTip(status_text)
        self.status_text_label.setProperty("state", state)
        self.status_text_label.style().unpolish(self.status_text_label)
        self.status_text_label.style().polish(self.status_text_label)
        dot_colors = {
            "idle": "#9b9b9b",
            "running": "#d97706",
            "done": "#16a34a",
            "error": "#dc2626",
        }
        self.status_dot.setStyleSheet(
            f"""
            QFrame#StatusDot {{
                background: {dot_colors.get(state, dot_colors['idle'])};
                border-radius: 7px;
                min-width: 14px;
                max-width: 14px;
                min-height: 14px;
                max-height: 14px;
            }}
            """
        )

    def _refresh_status_text(self) -> None:
        self.set_status_state(self.status_state)

    def _display_status_text(self, state: str, text: str | None) -> str:
        if text:
            known_statuses = {
                tr(self.language, "status_idle"),
                tr(self.language, "status_running"),
                tr(self.language, "status_done"),
                tr(self.language, "status_error"),
                tr(self.language, "status_normal"),
                tr(self.language, "status_initializing"),
                tr(self.language, "status_check_prompt"),
                tr(self.language, "status_check_setting"),
            }
            return text if text in known_statuses else tr(self.language, f"status_{state}")
        return tr(self.language, f"status_{state}")

    def append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def append_conversation(self, role: str, content: str) -> None:
        preview = content
        self.conversation_view.appendPlainText(f"\n[{role.upper()}]\n{preview}\n")


class SettingPage(QWidget):
    saved = Signal(object)
    applied = Signal(object)
    test_requested = Signal(str, object)
    models_requested = Signal(object)
    log_requested = Signal()

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
        self.ai_model_input = QComboBox()
        self.refresh_models_button = QPushButton()
        self.paper_text_limit_input = QSpinBox()
        self.test_api_button = QPushButton()
        self.api_test_result_button = QPushButton()
        self.api_check_failed = False
        self.save_button = QPushButton()
        self.new_config_button = QPushButton()
        self.save_as_button = QPushButton()
        self.apply_button = QPushButton()
        self.open_config_button = QPushButton()
        self.open_config_external_button = QPushButton()
        self.config_path = GUI_CONFIG_PATH
        self.loading = False
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
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(18)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(6)
        self.title_label.setObjectName("PageTitle")
        self.subtitle_label.setObjectName("PageSubtitle")
        self.subtitle_label.setWordWrap(True)
        hero_text.addWidget(self.title_label)
        hero_text.addWidget(self.subtitle_label)
        hero_layout.addLayout(hero_text, 1)

        self.api_test_result_button.setObjectName("CheckResultButton")
        self.api_test_result_button.setProperty("clickable", False)
        self.api_test_result_button.setFixedSize(150, 44)
        self.test_api_button.setFixedHeight(44)
        header_actions = QHBoxLayout()
        header_actions.setSpacing(14)
        header_actions.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_actions.addWidget(self.api_test_result_button)
        header_actions.addWidget(self.test_api_button)
        hero_layout.addLayout(header_actions)
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
        self.new_config_button.clicked.connect(self.new_config)
        self.save_as_button.clicked.connect(self.save_as)
        self.apply_button.clicked.connect(self._apply)
        self.open_config_button.clicked.connect(self.open_config_file)
        self.open_config_external_button.clicked.connect(lambda: self._open_file_external(self.config_path))
        self.test_api_button.clicked.connect(lambda: self.test_requested.emit("all", self.current_settings()))
        self.api_test_result_button.clicked.connect(self._open_log_if_failed)
        self.refresh_models_button.clicked.connect(lambda: self.models_requested.emit(self.current_settings()))
        self.ai_model_input.setEditable(True)

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
        buttons.setSpacing(10)
        buttons.addWidget(self.new_config_button)
        buttons.addWidget(self.open_config_button)
        buttons.addWidget(self.open_config_external_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.save_as_button)
        buttons.addWidget(self.apply_button)
        buttons.addStretch(1)
        button_bar = QFrame()
        button_bar.setObjectName("FloatingBar")
        button_bar.setLayout(buttons)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        outer.addWidget(button_bar)

    def load_settings(self, settings: Settings) -> None:
        self.loading = True
        self.settings = settings
        self.notion_token_input.setText(settings.notion_token)
        self.notion_database_id_input.setText(settings.notion_database_id)
        self.ai_api_key_input.setText(settings.ai_api_key)
        self.ai_base_url_input.setText(settings.ai_base_url or "")
        self.set_available_models([settings.ai_model], settings.ai_model)
        self.paper_text_limit_input.setValue(settings.paper_text_limit)
        self.loading = False

    def retranslate(self, language: str) -> None:
        self.language = language
        self.title_label.setText(tr(language, "setting_title"))
        self.subtitle_label.setText(tr(language, "setting_subtitle"))
        self.connection_title.setText(tr(language, "connection_card"))
        self.test_api_button.setText(tr(language, "test_api"))
        self.refresh_models_button.setText(tr(language, "refresh_models"))
        if not self.api_test_result_button.text():
            self.api_test_result_button.setText(tr(language, "test_waiting"))
        self.save_button.setText(tr(language, "save"))
        self.new_config_button.setText(tr(language, "new_file"))
        self.save_as_button.setText(tr(language, "save_as"))
        self.apply_button.setText(tr(language, "apply"))
        self.open_config_button.setText(tr(language, "open_config"))
        self.open_config_external_button.setText(tr(language, "open_external"))
        self._rebuild_form()

    def _rebuild_form(self) -> None:
        rows = [
            ("notion_token", self.notion_token_input),
            ("notion_database_id", self.notion_database_id_input),
            ("ai_api_key", self.ai_api_key_input),
            ("ai_base_url", self.ai_base_url_input),
            ("ai_model", self._model_selector_widget()),
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
            ai_model=self.ai_model_input.currentText().strip(),
            ai_base_url=self.ai_base_url_input.text().strip() or None,
            paper_text_limit=self.paper_text_limit_input.value(),
            ui_language=self.language,
            theme_mode=self.settings.theme_mode,
            prompt_language=self.settings.prompt_language,
            prompt=self.settings.prompt,
            user_prompt_template=self.settings.user_prompt_template,
            profile="gui",
            ai_model_explicit=bool(self.ai_model_input.currentText().strip()),
        )

    def _save(self) -> None:
        self._save_to_file(show_message=True)

    def _save_to_file(self, show_message: bool) -> bool:
        settings = self.current_settings()
        save_settings_xml(settings, config_path=self.config_path, profile="gui")
        self.saved.emit(settings)
        if show_message:
            QMessageBox.information(self, tr(self.language, "saved"), tr(self.language, "setting_saved_message"))
        return True

    def _apply(self) -> None:
        self.apply_changes()

    def _open_file(self, path: Path) -> None:
        self._open_file_external(path)

    def _open_file_external(self, path: Path) -> None:
        if not path.exists():
            save_settings_xml(self.current_settings(), config_path=path, profile="gui")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def open_config_file(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            tr(self.language, "open_config"),
            str(self.config_path.parent),
            "XML (*.xml)",
        )
        if not path_text:
            return
        self.config_path = Path(path_text)
        self.load_settings(load_settings(config_path=self.config_path, validate_required=False, profile="gui"))

    def new_config(self) -> None:
        self.notion_token_input.clear()
        self.notion_database_id_input.clear()
        self.ai_api_key_input.clear()
        self.ai_base_url_input.clear()
        self.ai_model_input.setCurrentText("")
        self.paper_text_limit_input.setValue(50_000)

    def save_as(self, show_message: bool = False) -> bool:
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            tr(self.language, "save_as"),
            str(self.config_path),
            "XML (*.xml)",
        )
        if not path_text:
            return False
        self.config_path = Path(path_text)
        save_settings_xml(self.current_settings(), config_path=self.config_path, profile="gui")
        if show_message:
            QMessageBox.information(self, tr(self.language, "saved"), tr(self.language, "setting_saved_message"))
        return True

    def set_check_running(self, target: str) -> None:
        self.api_check_failed = False
        self.api_test_result_button.setProperty("clickable", False)
        self.api_test_result_button.setCursor(Qt.CursorShape.ArrowCursor)
        self.api_test_result_button.setText(tr(self.language, "test_running"))
        self.api_test_result_button.setProperty("state", "running")
        self._refresh_check_labels()

    def set_check_result(self, target: str, result: CheckResult) -> None:
        self.api_test_result_button.setToolTip(result.detail or result.message)
        if result.ok and not self.api_check_failed:
            self.api_test_result_button.setText(tr(self.language, "api_normal"))
            self.api_test_result_button.setProperty("state", "ok")
            self.api_test_result_button.setProperty("clickable", False)
            self.api_test_result_button.setCursor(Qt.CursorShape.ArrowCursor)
            self._refresh_check_labels()
            return
        if not result.ok:
            self.api_check_failed = True
            self.api_test_result_button.setText(tr(self.language, "view_log"))
            self.api_test_result_button.setProperty("state", "error")
            self.api_test_result_button.setProperty("clickable", True)
            self.api_test_result_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_check_labels()

    def _open_log_if_failed(self) -> None:
        if self.api_check_failed:
            self.log_requested.emit()

    def set_models_loading(self) -> None:
        current_model = self.ai_model_input.currentText().strip()
        self.refresh_models_button.setEnabled(False)
        self.refresh_models_button.setText(tr(self.language, "models_loading"))
        if current_model:
            self.ai_model_input.setCurrentText(current_model)

    def set_available_models(self, models: list[str], selected_model: str | None = None) -> None:
        selected = selected_model or self.ai_model_input.currentText().strip()
        unique_models = []
        for model in models:
            clean_model = model.strip()
            if clean_model and clean_model not in unique_models:
                unique_models.append(clean_model)
        if selected and selected not in unique_models:
            unique_models.insert(0, selected)

        self.ai_model_input.blockSignals(True)
        self.ai_model_input.clear()
        self.ai_model_input.addItems(unique_models)
        if selected:
            self.ai_model_input.setCurrentText(selected)
        self.ai_model_input.blockSignals(False)
        self.refresh_models_button.setEnabled(True)
        self.refresh_models_button.setText(tr(self.language, "refresh_models"))

    def set_models_error(self) -> None:
        self.refresh_models_button.setEnabled(True)
        self.refresh_models_button.setText(tr(self.language, "refresh_models"))

    def _model_selector_widget(self) -> QWidget:
        if hasattr(self, "model_selector_widget"):
            return self.model_selector_widget
        self.model_selector_widget = QWidget()
        layout = QHBoxLayout(self.model_selector_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.ai_model_input, 1)
        layout.addWidget(self.refresh_models_button)
        return self.model_selector_widget

    def _refresh_check_labels(self) -> None:
        self.api_test_result_button.style().unpolish(self.api_test_result_button)
        self.api_test_result_button.style().polish(self.api_test_result_button)

    def save_and_apply(self) -> bool:
        return self.save_changes() and self.apply_changes()

    def apply_changes(self) -> bool:
        settings = self.current_settings()
        self.applied.emit(settings)
        return True

    def save_changes(self) -> bool:
        return self._save_to_file(show_message=False)

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


class PromptPage(QWidget):
    applied = Signal(object)

    def __init__(self, settings: Settings, language: str) -> None:
        super().__init__()
        self.settings = settings
        self.language = language
        self.prompt_language = settings.prompt_language
        self.prompt_file_path = prompt_path("gui", self.prompt_language)
        self.title_label = QLabel()
        self.subtitle_label = QLabel()
        self.prompt_file_hint_label = QLabel()
        self.prompt_preview_label = QLabel()
        self.prompt_path_input = QLineEdit()
        self.open_prompt_file_button = QPushButton()
        self.prompt_language_button = QPushButton()
        self.prompt_preview = QTextEdit()
        self.reload_prompt_button = QPushButton()
        self.open_prompt_external_button = QPushButton()
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

        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)
        self.prompt_path_input.setReadOnly(True)
        self.prompt_language_button.setFixedWidth(82)
        path_layout.addWidget(self.prompt_language_button)
        path_layout.addWidget(self.prompt_path_input, 1)
        path_layout.addWidget(self.open_prompt_file_button)

        self.prompt_preview.setReadOnly(True)
        self.prompt_preview.setMinimumHeight(260)
        self.prompt_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.prompt_file_hint_label.setObjectName("CardSubtitle")
        self.prompt_preview_label.setObjectName("CardSubtitle")
        self.prompt_file_hint_label.setWordWrap(True)
        card_layout.addWidget(self.prompt_file_hint_label)
        card_layout.addLayout(path_layout)
        card_layout.addWidget(self.prompt_preview_label)
        card_layout.addWidget(self.prompt_preview, 1)
        outer.addWidget(card, 1)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(14, 14, 14, 14)
        buttons.addWidget(self.open_prompt_external_button)
        buttons.addWidget(self.reload_prompt_button)
        buttons.addStretch(1)
        button_bar = QFrame()
        button_bar.setObjectName("FloatingBar")
        button_bar.setLayout(buttons)
        outer.addWidget(button_bar)

        self.prompt_language_button.clicked.connect(self.cycle_prompt_language)
        self.open_prompt_external_button.clicked.connect(self.open_file_external)
        self.open_prompt_file_button.clicked.connect(self.open_prompt_file)
        self.reload_prompt_button.clicked.connect(self.reload_prompt_preview)

    def load_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.prompt_language = settings.prompt_language
        self.prompt_file_path = prompt_path("gui", self.prompt_language)
        self.reload_prompt_preview(emit_applied=False)

    def retranslate(self, language: str) -> None:
        self.language = language
        self.title_label.setText(tr(language, "prompt_title_page"))
        self.subtitle_label.setText(tr(language, "prompt_subtitle_page"))
        self.prompt_file_hint_label.setText(tr(language, "prompt_preview_hint"))
        self.prompt_preview_label.setText(tr(language, "prompt_preview"))
        self.open_prompt_file_button.setText(tr(language, "open"))
        self.prompt_language_button.setText(LANGUAGE_SHORT_LABELS[self.prompt_language])
        self.open_prompt_external_button.setText(tr(language, "open_external"))
        self.reload_prompt_button.setText(tr(language, "reload_prompt"))

    def apply_to_settings(self, settings: Settings) -> Settings:
        settings.profile = "gui"
        settings.prompt_language = self.prompt_language
        settings.prompt = self.prompt_preview.toPlainText().strip()
        settings.user_prompt_template = get_user_prompt_template("gui", settings.prompt_language)
        return settings

    def cycle_prompt_language(self) -> None:
        self.set_prompt_language(next_language(self.prompt_language), emit_applied=True)

    def set_prompt_language(self, language: str, emit_applied: bool = True) -> None:
        self.prompt_language = language if language in LANGUAGE_CYCLE else "zh"
        self.prompt_file_path = prompt_path("gui", self.prompt_language)
        self.prompt_language_button.setText(LANGUAGE_SHORT_LABELS[self.prompt_language])
        self.reload_prompt_preview(emit_applied=emit_applied)

    def open_prompt_file(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            tr(self.language, "open_prompt"),
            str(prompt_path("gui", self.prompt_language).parent),
            "XML (*.xml)",
        )
        if not path_text:
            return
        self.load_prompt_file_path(Path(path_text), emit_applied=True)

    def load_prompt_file_path(self, path: Path, emit_applied: bool = True) -> None:
        if not path.exists():
            return
        self.prompt_file_path = path
        self.prompt_preview.setPlainText(read_system_prompt_xml(self.prompt_file_path))
        self.prompt_path_input.setText(str(self.prompt_file_path))
        if emit_applied:
            self.applied.emit(self.apply_to_settings(self.settings))

    def reload_prompt_preview(self, emit_applied: bool = True) -> None:
        if self.prompt_file_path.exists():
            content = read_system_prompt_xml(self.prompt_file_path)
        else:
            self.prompt_file_path = ensure_prompt_xml("gui", self.prompt_language)
            content = read_system_prompt_xml(self.prompt_file_path)
        self.prompt_preview.setPlainText(content)
        self.prompt_path_input.setText(str(self.prompt_file_path))
        if emit_applied:
            self.applied.emit(self.apply_to_settings(self.settings))

    def open_file_external(self) -> None:
        if not self.prompt_file_path.exists():
            self.prompt_file_path = ensure_prompt_xml("gui", self.prompt_language)
            self.reload_prompt_preview(emit_applied=False)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.prompt_file_path.resolve())))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.app_state = load_app_state()
        remembered_config = Path(self.app_state.last_config_path) if self.app_state.last_config_path else None
        self.active_config_path = remembered_config if remembered_config and remembered_config.exists() else GUI_CONFIG_PATH
        self.settings = load_settings(config_path=self.active_config_path, validate_required=False, profile="gui")
        initial_language = self.app_state.ui_language or system_language()
        self.language = initial_language if initial_language in SUPPORTED_UI_LANGUAGES else "en"
        self.settings.prompt_language = self.language
        self.settings.prompt = get_prompt("gui", self.settings.prompt_language)
        self.settings.user_prompt_template = get_user_prompt_template("gui", self.settings.prompt_language)
        self.settings.ui_language = self.language
        if self.app_state.theme_mode in THEME_MODES:
            self.settings.theme_mode = self.app_state.theme_mode
        self.thread: QThread | None = None
        self.worker: PipelineWorker | None = None
        self.check_thread: QThread | None = None
        self.check_worker: ConnectivityWorker | None = None
        self.model_thread: QThread | None = None
        self.model_worker: ModelListWorker | None = None
        self.model_fetch_prefer_configured = True
        self.start_after_check = False

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.dashboard_button = QPushButton()
        self.prompt_button = QPushButton()
        self.edit_button = QPushButton()
        self.language_button = QPushButton()
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
        self.validation_blink_timer = QTimer(self)
        self.validation_blink_timer.setInterval(420)
        self.validation_blink_timer.timeout.connect(self._blink_validation_status)
        self.validation_blink_on = False
        self.dashboard = DashboardPage(self.language)
        self.prompt_page = PromptPage(self.settings, self.language)
        self.setting_page = SettingPage(self.settings, self.language)
        self.setting_page.config_path = self.active_config_path
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.prompt_page)
        self.stack.addWidget(self.setting_page)
        if self.app_state.last_prompt_path:
            remembered_prompt = Path(self.app_state.last_prompt_path)
            if remembered_prompt.stem == self.prompt_page.prompt_language:
                self.prompt_page.load_prompt_file_path(remembered_prompt, emit_applied=False)
        self._build_shell()

        self.dashboard.start_requested.connect(self.start_pipeline)
        self.dashboard.stop_requested.connect(self.stop_pipeline)
        self.setting_page.applied.connect(self.update_settings)
        self.setting_page.test_requested.connect(self.start_connectivity_check)
        self.setting_page.models_requested.connect(self.start_model_list_fetch)
        self.setting_page.log_requested.connect(self.show_dashboard)
        self.prompt_page.applied.connect(self.update_settings)

        self.setMinimumSize(1180, 780)
        self._apply_style()
        self.retranslate()
        self.set_ui_interaction_enabled(False)
        self.dashboard.set_status_state("running", tr(self.language, "status_initializing"))
        QTimer.singleShot(150, self.run_startup_validation)

    def retranslate(self) -> None:
        self.setWindowTitle(tr(self.language, "app_title"))
        self.brand_title.setText(tr(self.language, "app_title"))
        self.brand_subtitle.setText(tr(self.language, "app_subtitle"))
        self.dashboard_button.setText(f"  🧭  {tr(self.language, 'dashboard')}")
        self.prompt_button.setText(f"  ✍️  {tr(self.language, 'prompt_nav')}")
        self.edit_button.setText(f"  ⚙️  {tr(self.language, 'setting')}")
        self.language_button.setText(LANGUAGE_SHORT_LABELS[self.language])
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
        self.nav_group.idClicked.connect(self.request_navigation)
        sidebar_layout.addStretch(1)

        bottom_actions = QHBoxLayout()
        bottom_actions.setSpacing(8)

        self.language_button.setObjectName("BottomMenuButton")
        self.language_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.language_button.clicked.connect(self.cycle_ui_language)
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
        self.prompt_page.set_prompt_language(language, emit_applied=True)
        self.settings.prompt_language = language
        self._build_theme_menu()
        self.retranslate()
        self.save_current_app_state()

    @Slot()
    def cycle_ui_language(self) -> None:
        self.set_language(next_language(self.language))

    @Slot()
    def show_dashboard(self) -> None:
        self.stack.setCurrentIndex(0)
        self.dashboard_button.setChecked(True)

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
        save_settings_xml(self.settings, profile="gui")
        self._build_theme_menu()
        self.retranslate()
        self._request_theme_update(animated=True)
        self.save_current_app_state()

    @Slot(Settings)
    def update_settings(self, settings: Settings) -> None:
        settings.theme_mode = self.theme_mode
        settings.ui_language = self.language
        self.settings = settings
        self.setting_page.settings = settings
        self.prompt_page.settings = settings
        self.active_config_path = self.setting_page.config_path
        self.save_current_app_state()

    @Slot(int)
    def request_navigation(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.nav_group.button(index).setChecked(True)

    def set_ui_interaction_enabled(self, enabled: bool) -> None:
        self.stack.setEnabled(enabled)
        for button in (self.dashboard_button, self.prompt_button, self.edit_button, self.language_button, self.theme_button):
            button.setEnabled(enabled)

    @Slot()
    def run_startup_validation(self) -> None:
        self.dashboard.append_log(tr(self.language, "log_startup_validation"))
        errors = validate_runtime_files("gui", self.setting_page.config_path)
        if errors:
            for error in errors:
                self.dashboard.append_log(f"{tr(self.language, 'log_validation_issue')}: {error}")
            status_key = "status_check_prompt" if any("prompt" in error.lower() for error in errors) else "status_check_setting"
            self.dashboard.set_status_state("error", tr(self.language, status_key))
            self.validation_blink_timer.start()
        else:
            self.dashboard.append_log(tr(self.language, "log_validation_ok"))
            self.dashboard.set_status_state("idle", tr(self.language, "status_normal"))
            self.validation_blink_timer.stop()
        self.set_ui_interaction_enabled(True)
        if not errors:
            self.refresh_models_on_startup()

    @Slot()
    def _blink_validation_status(self) -> None:
        self.validation_blink_on = not self.validation_blink_on
        self.dashboard.status_dot.setVisible(self.validation_blink_on)
        self.dashboard.status_text_label.setVisible(self.validation_blink_on)

    def save_current_app_state(self) -> None:
        self.app_state = AppState(
            ui_language=self.language,
            prompt_language=self.prompt_page.prompt_language,
            theme_mode=self.theme_mode,
            last_config_path=str(self.setting_page.config_path),
            last_prompt_path=str(self.prompt_page.prompt_file_path),
        )
        save_app_state(self.app_state)

    @Slot()
    def start_pipeline(self) -> None:
        if self.thread:
            self.dashboard.append_log(tr(self.language, "log_pipeline_running"))
            return
        self.settings = self.setting_page.current_settings()
        self.settings = self.prompt_page.apply_to_settings(self.settings)
        self.settings.theme_mode = self.theme_mode
        self.dashboard.log_view.clear()
        self.dashboard.conversation_view.clear()
        self.start_connectivity_check("all", self.settings, start_after=True)

    @Slot()
    def refresh_models_on_startup(self) -> None:
        settings = self.setting_page.current_settings()
        if not settings.ai_api_key:
            return
        self.start_model_list_fetch(settings, prefer_configured=self._has_configured_model_priority(settings))

    def _launch_pipeline(self) -> None:
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

    @Slot(str, object)
    def start_connectivity_check(
        self,
        target: str,
        settings: Settings,
        start_after: bool = False,
    ) -> None:
        if self.check_thread:
            self.dashboard.append_log(tr(self.language, "log_connectivity_running"))
            return
        self.start_after_check = start_after
        self.setting_page.set_check_running(target)
        self.dashboard.set_status_state("running")
        self.check_thread = QThread()
        self.check_worker = ConnectivityWorker(settings, target)
        self.check_worker.moveToThread(self.check_thread)
        self.check_thread.started.connect(self.check_worker.run)
        self.check_worker.log.connect(self.dashboard.append_log)
        self.check_worker.result.connect(self._connectivity_result)
        self.check_worker.failed.connect(self._connectivity_failed)
        self.check_worker.finished.connect(self._connectivity_finished)
        self.check_worker.finished.connect(self.check_thread.quit)
        self.check_worker.failed.connect(self.check_thread.quit)
        self.check_thread.finished.connect(self.check_worker.deleteLater)
        self.check_thread.finished.connect(self.check_thread.deleteLater)
        self.check_thread.finished.connect(self._clear_check_thread)
        self.check_thread.start()

    @Slot(str, object)
    def _connectivity_result(self, target: str, result: CheckResult) -> None:
        self.setting_page.set_check_result(target, result)
        target_key = "notion" if target == "notion" else "ai"
        status_key = "api_normal" if result.ok else "view_log"
        self.dashboard.append_log(
            f"{tr(self.language, f'log_{target_key}_api')}: {tr(self.language, status_key)}"
        )
        if not result.ok:
            self.dashboard.set_status_state("error", result.message)

    @Slot(bool)
    def _connectivity_finished(self, ok: bool) -> None:
        if ok:
            if self.start_after_check:
                self._launch_pipeline()
            else:
                self.dashboard.set_status_state("idle")
        else:
            self.dashboard.set_status_state("error")
        self.start_after_check = False

    @Slot(str)
    def _connectivity_failed(self, message: str) -> None:
        self.dashboard.append_log(f"{tr(self.language, 'error')}: {message}")
        self.dashboard.set_status_state("error", message)
        self.start_after_check = False

    @Slot()
    def _clear_check_thread(self) -> None:
        self.check_thread = None
        self.check_worker = None

    @Slot(object)
    def start_model_list_fetch(self, settings: Settings, prefer_configured: bool = True) -> None:
        if self.model_thread:
            self.dashboard.append_log(tr(self.language, "log_model_running"))
            return
        self.model_fetch_prefer_configured = prefer_configured
        self.setting_page.set_models_loading()
        self.dashboard.set_status_state("running")
        self.model_thread = QThread()
        self.model_worker = ModelListWorker(settings)
        self.model_worker.moveToThread(self.model_thread)
        self.model_thread.started.connect(self.model_worker.run)
        self.model_worker.log.connect(self.dashboard.append_log)
        self.model_worker.finished.connect(self._models_fetched)
        self.model_worker.failed.connect(self._models_failed)
        self.model_worker.finished.connect(self.model_thread.quit)
        self.model_worker.failed.connect(self.model_thread.quit)
        self.model_thread.finished.connect(self.model_worker.deleteLater)
        self.model_thread.finished.connect(self.model_thread.deleteLater)
        self.model_thread.finished.connect(self._clear_model_thread)
        self.model_thread.start()

    @Slot(list, str)
    def _models_fetched(self, models: list[str], default_model: str) -> None:
        current_model = self.setting_page.ai_model_input.currentText().strip()
        selected_model = (
            current_model
            if self.model_fetch_prefer_configured and current_model
            else default_model
        )
        self.setting_page.set_available_models(models, selected_model)
        self.dashboard.set_status_state("idle")
        self.dashboard.append_log(tr(self.language, "models_loaded"))

    @Slot(str)
    def _models_failed(self, message: str) -> None:
        self.setting_page.set_models_error()
        self.dashboard.set_status_state("error", message)
        self.dashboard.append_log(f"{tr(self.language, 'error')}: {message}")

    @Slot()
    def _clear_model_thread(self) -> None:
        self.model_thread = None
        self.model_worker = None

    def _has_configured_model_priority(self, settings: Settings) -> bool:
        if not settings.ai_model:
            return False
        if settings.ai_model == "gpt-4o-mini" and settings.ai_base_url:
            return False
        return settings.ai_model_explicit

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
        self.dashboard.set_status_state("error", message)
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

    def closeEvent(self, event: QEvent) -> None:
        self.save_current_app_state()
        for thread in (self.model_thread, self.check_thread, self.thread):
            if thread and thread.isRunning():
                thread.quit()
                if not thread.wait(1500):
                    thread.terminate()
                    thread.wait(1000)
        super().closeEvent(event)

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
            QFrame#StatusCapsule {
                border: 1px solid %(border)s;
                border-radius: 13px;
                background: %(surface_2)s;
            }
            QLabel#StatusTextPill {
                color: %(muted)s;
                padding: 0px;
                border: none;
                background: transparent;
                font-weight: 650;
            }
            QLabel#StatusTextPill[state="running"] {
                color: #d97706;
                background: transparent;
            }
            QLabel#StatusTextPill[state="done"], QLabel#StatusTextPill[state="idle"] {
                color: #16a34a;
                background: transparent;
            }
            QLabel#StatusTextPill[state="error"] {
                color: #dc2626;
                background: transparent;
            }
            QPushButton#CheckResultButton {
                color: %(muted)s;
                padding: 0px 10px;
                border: 1px solid %(border)s;
                border-radius: 13px;
                background: %(surface_2)s;
                text-align: center;
            }
            QPushButton#CheckResultButton:hover {
                background: %(nav_hover)s;
            }
            QPushButton#CheckResultButton[clickable="false"]:hover {
                background: %(surface_2)s;
            }
            QPushButton#CheckResultButton[state="running"] {
                color: #d97706;
                background: rgba(217, 119, 6, 0.10);
            }
            QPushButton#CheckResultButton[state="ok"] {
                color: #16a34a;
                background: rgba(22, 163, 74, 0.10);
            }
            QPushButton#CheckResultButton[state="error"] {
                color: #dc2626;
                background: rgba(220, 38, 38, 0.10);
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
