"""
Airi Main Window
PyQt6 desktop window with Live2D avatar, crypto panel, and AI analysis.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

from PyQt6.QtCore import (
    Qt, QUrl, QTimer, pyqtSignal, QObject, QPoint, QSize
)
from PyQt6.QtGui import QIcon, QPixmap, QFont, QAction, QColor, QPainter
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QSizePolicy,
    QSystemTrayIcon, QMenu, QApplication, QGraphicsDropShadowEffect,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
import keyboard

# No longer need crypto formatters
from assistant.voice_cmd import VoiceCommandExecutor
from ui.styles import MAIN_STYLESHEET


class SignalBridge(QObject):
    """Bridge to safely emit signals from background threads to Qt UI."""
    greeting_received = pyqtSignal(dict)
    ore_grid_update = pyqtSignal(dict)
    ore_round_start = pyqtSignal(dict)
    ore_wallet_update = pyqtSignal(dict)
    ore_ai_log = pyqtSignal(str)
    ore_winrate = pyqtSignal(dict)
    voice_status_updated = pyqtSignal(dict)


class AiriMainWindow(QMainWindow):
    """Main desktop assistant window."""

    def __init__(self):
        super().__init__()
        self.signal_bridge = SignalBridge()
        self._drag_pos = None
        self.voice_executor = VoiceCommandExecutor(callback=self._voice_callback)

        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._start_clock()
        self._setup_global_hotkey()
        
        # Play welcome voice after slight delay to let UI load
        QTimer.singleShot(1000, self._play_welcome_voice)

    # ── Window Setup ──────────────────────────────────────────────

    def _setup_window(self):
        """Configure window properties."""
        self.setWindowTitle("Airi AI Assistant")
        self.setFixedSize(400, 700)

        # Desktop widget mode - no always-on-top, frameless
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Load settings for window position
        settings = self._load_settings()
        win_settings = settings.get("window", {})
        opacity = win_settings.get("opacity", 0.95)
        self.setWindowOpacity(opacity)

        # Position window at bottom-right of screen
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.width() - self.width() - 20
            y = geo.height() - self.height() - 20
            self.move(x, y)

        self.setStyleSheet(MAIN_STYLESHEET)

    def _load_settings(self) -> dict:
        settings_path = Path(__file__).parent.parent / "config" / "settings.json"
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    # ── Build UI ──────────────────────────────────────────────────

    def _build_ui(self):
        """Build the complete UI layout."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Main container with background
        self.main_container = QWidget()
        self.main_container.setObjectName("mainContainer")
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(139, 92, 246, 60))
        shadow.setOffset(0, 4)
        self.main_container.setGraphicsEffect(shadow)

        # Build sections
        main_layout.addWidget(self._build_header())
        main_layout.addWidget(self._build_avatar_section())
        main_layout.addWidget(self._build_greeting_section())

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 4, 0, 4)
        self.scroll_layout.setSpacing(4)

        self.scroll_layout.addWidget(self._build_ore_section())
        self.scroll_layout.addWidget(self._build_round_history_section())
        self.scroll_layout.addWidget(self._build_agent_logs_section())
        self.scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

        main_layout.addWidget(self._build_status_bar())

        central_layout.addWidget(self.main_container)

    def _build_header(self) -> QWidget:
        """Build the header with title and window controls."""
        header = QWidget()
        header.setObjectName("headerWidget")
        header.setFixedHeight(50)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 8, 12, 4)

        # Title section
        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)

        title = QLabel("✦ AIRI")
        title.setObjectName("appTitle")
        title_layout.addWidget(title)

        subtitle = QLabel("AI Desktop Assistant")
        subtitle.setObjectName("appSubtitle")
        title_layout.addWidget(subtitle)

        layout.addLayout(title_layout)
        layout.addStretch()

        # Clock
        self.clock_label = QLabel("00:00")
        self.clock_label.setObjectName("clockLabel")
        layout.addWidget(self.clock_label)

        layout.addSpacing(8)
        
        # Voice Command Button
        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setToolTip("Voice Command (Ctrl+Shift+A)")
        self.mic_btn.setFixedSize(32, 28)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: rgba(139, 92, 246, 0.2);
                border: 1px solid rgba(139, 92, 246, 0.4);
                border-radius: 14px;
                font-size: 14px;
            }
            QPushButton:hover { background: rgba(139, 92, 246, 0.4); }
            QPushButton:pressed { background: rgba(139, 92, 246, 0.6); }
        """)
        self.mic_btn.clicked.connect(self._trigger_voice)
        layout.addWidget(self.mic_btn)
        
        layout.addSpacing(8)

        # Window controls
        minimize_btn = QPushButton("—")
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.setToolTip("Minimize to tray")
        minimize_btn.clicked.connect(self._minimize_to_tray)
        layout.addWidget(minimize_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return header

    def _build_avatar_section(self) -> QWidget:
        """Build the Live2D avatar display."""
        container = QWidget()
        container.setObjectName("avatarContainer")
        container.setFixedHeight(250)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        # WebEngineView for Live2D
        self.avatar_view = QWebEngineView()
        self.avatar_view.setStyleSheet("background: transparent;")
        self.avatar_view.page().setBackgroundColor(QColor(0, 0, 0, 0))

        # Load avatar HTML
        avatar_path = Path(__file__).parent.parent / "assets" / "avatar.html"
        if avatar_path.exists():
            self.avatar_view.setUrl(QUrl.fromLocalFile(str(avatar_path.resolve())))
        else:
            self.avatar_view.setHtml(
                '<body style="background:transparent;display:flex;align-items:center;'
                'justify-content:center;height:100vh;margin:0;font-family:sans-serif;'
                'color:#8b5cf6"><div style="text-align:center">'
                '<div style="font-size:48px">🎀</div>'
                '<p>Avatar not found</p></div></body>'
            )

        layout.addWidget(self.avatar_view)
        return container

    def _build_greeting_section(self) -> QWidget:
        """Build the greeting card."""
        card = QWidget()
        card.setObjectName("greetingCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.greeting_label = QLabel("Loading...")
        self.greeting_label.setObjectName("greetingText")
        self.greeting_label.setWordWrap(True)
        layout.addWidget(self.greeting_label)

        return card

    def _build_ore_section(self) -> QWidget:
        """Build the Ore Supply wallet & stats section."""
        card = QWidget()
        card.setObjectName("cryptoCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header row
        header_row = QHBoxLayout()
        title = QLabel("⛏️ ORE SUPPLY AGENT")
        title.setStyleSheet("""
            color: #8b5cf6;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.5px;
        """)
        header_row.addWidget(title)
        header_row.addStretch()

        self.orepot_label = QLabel("Orepot: ...")
        self.orepot_label.setStyleSheet("color: #fbbf24; font-size: 10px; font-weight: 600;")
        header_row.addWidget(self.orepot_label)
        layout.addLayout(header_row)

        # Wallet address
        self.wallet_addr_label = QLabel("Wallet: Connecting...")
        self.wallet_addr_label.setStyleSheet("color: #94a3b8; font-size: 10px;")
        layout.addWidget(self.wallet_addr_label)

        # Balances row
        bal_row = QWidget()
        bal_row.setStyleSheet("background: rgba(139, 92, 246, 0.06); border-radius: 10px;")
        bal_layout = QHBoxLayout(bal_row)
        bal_layout.setContentsMargins(12, 8, 12, 8)

        self.sol_bal_label = QLabel("SOL: ...")
        self.sol_bal_label.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: 700;")
        bal_layout.addWidget(self.sol_bal_label)

        bal_layout.addStretch()

        self.ore_bal_label = QLabel("ORE: ...")
        self.ore_bal_label.setStyleSheet("color: #34d399; font-size: 13px; font-weight: 700;")
        bal_layout.addWidget(self.ore_bal_label)

        layout.addWidget(bal_row)

        # Stop button row
        control_row = QHBoxLayout()
        
        control_row.addStretch()
        
        self.mining_toggle_btn = QPushButton("⏸ Stop")
        self.mining_toggle_btn.setFixedSize(70, 26)
        self.mining_toggle_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 13px;
                color: #f87171;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 0.4); }
        """)
        self.mining_toggle_btn.clicked.connect(self._toggle_mining)
        control_row.addWidget(self.mining_toggle_btn)
        
        layout.addLayout(control_row)

        return card

    def _build_round_history_section(self) -> QWidget:
        """Build the Round History stats card."""
        card = QWidget()
        card.setObjectName("cryptoCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("\ud83d\udcca Round History")
        title.setStyleSheet("""
            color: #e2e8f0;
            font-size: 12px;
            font-weight: 700;
        """)
        header_row.addWidget(title)
        header_row.addStretch()
        
        self.rounds_played_label = QLabel("0 rounds played")
        self.rounds_played_label.setStyleSheet("color: #64748b; font-size: 10px;")
        header_row.addWidget(self.rounds_played_label)
        layout.addLayout(header_row)

        # Stats row
        stats_row = QWidget()
        stats_row.setStyleSheet("background: rgba(139, 92, 246, 0.06); border-radius: 10px;")
        stats_layout = QHBoxLayout(stats_row)
        stats_layout.setContentsMargins(12, 8, 12, 8)

        # Pending SOL column
        sol_col = QVBoxLayout()
        sol_title = QLabel("Pending SOL")
        sol_title.setStyleSheet("color: #64748b; font-size: 9px;")
        sol_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_pnl = QLabel("0.0000")
        self.history_pnl.setStyleSheet("color: #34d399; font-size: 16px; font-weight: 800;")
        self.history_pnl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sol_col.addWidget(sol_title)
        sol_col.addWidget(self.history_pnl)
        stats_layout.addLayout(sol_col)

        # Pending ORE column
        ore_col = QVBoxLayout()
        ore_title = QLabel("Pending ORE")
        ore_title.setStyleSheet("color: #64748b; font-size: 9px;")
        ore_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_ore = QLabel("0.00")
        self.history_ore.setStyleSheet("color: #e2e8f0; font-size: 16px; font-weight: 800;")
        self.history_ore.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ore_col.addWidget(ore_title)
        ore_col.addWidget(self.history_ore)
        stats_layout.addLayout(ore_col)

        layout.addWidget(stats_row)

        return card

    def _build_agent_logs_section(self) -> QWidget:
        """Build the Agent Logs section."""
        card = QWidget()
        card.setObjectName("analysisCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header
        title = QLabel("🤖 AGENT LOGS")
        title.setStyleSheet("""
            color: #8b5cf6;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.5px;
        """)
        layout.addWidget(title)

        # Log text
        self.agent_log_label = QLabel("Menunggu koneksi ke Ore Supply...")
        self.agent_log_label.setWordWrap(True)
        self.agent_log_label.setStyleSheet("color: #cbd5e1; font-size: 11px; line-height: 1.4;")
        self.agent_log_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.agent_log_label)

        return card

    def _build_status_bar(self) -> QWidget:
        """Build the bottom status bar."""
        bar = QWidget()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(24)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 2, 16, 4)

        self.status_label = QLabel("● Online")
        self.status_label.setStyleSheet("color: #34d399; font-size: 9px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        version_label = QLabel("Airi v1.0.0")
        version_label.setStyleSheet("color: #334155; font-size: 9px;")
        layout.addWidget(version_label)

        return bar

    # ── Signals & Slots ───────────────────────────────────────────

    def _connect_signals(self):
        """Connect signal bridge to UI update methods."""
        self.signal_bridge.greeting_received.connect(self._update_greeting_ui)
        self.signal_bridge.voice_status_updated.connect(self._update_voice_ui)
        self.signal_bridge.ore_wallet_update.connect(self._update_wallet_ui)
        self.signal_bridge.ore_round_start.connect(self._update_round_ui)
        self.signal_bridge.ore_ai_log.connect(self._append_ai_log)
        self.signal_bridge.ore_winrate.connect(self._update_winrate_ui)

    def signal_bridge_callback(self, event_type: str, data):
        """Callback from the scheduler (called from background thread)."""
        if event_type == "greeting":
            self.signal_bridge.greeting_received.emit(data)
        elif event_type == "ore_wallet_update":
            self.signal_bridge.ore_wallet_update.emit(data)
        elif event_type == "ore_round_start":
            self.signal_bridge.ore_round_start.emit(data)
        elif event_type == "ore_ai_log":
            self.signal_bridge.ore_ai_log.emit(data)
        elif event_type == "ore_winrate":
            self.signal_bridge.ore_winrate.emit(data)

    def _update_wallet_ui(self, data: dict):
        """Update wallet info in the UI."""
        if "error" in data:
            self.wallet_addr_label.setText(str(data["error"]))
            return

        addr = data.get("address", "")
        short_addr = f"{addr[:6]}...{addr[-4:]}" if len(addr) > 10 else addr
        self.wallet_addr_label.setText(f"Phantom: {short_addr}")

        sol_bal = data.get("sol_balance", 0.0)
        self.sol_bal_label.setText(f"SOL: {sol_bal:.5f}")

        rewards = data.get("rewards", {})
        pending_sol = float(rewards.get("pendingSOLFormatted", "0.0"))
        pending_ore = float(rewards.get("pendingOREFormatted", "0.0"))
        self.ore_bal_label.setText(f"ORE: {pending_ore:.2f}")
        
        # Update Round History Stats with True API values
        self.history_ore.setText(f"{pending_ore:.2f}")
        self.history_pnl.setText(f"{pending_sol:.4f} SOL")
        self.history_pnl.setStyleSheet("color: #34d399; font-size: 16px; font-weight: 800;")

    def _update_round_ui(self, data: dict):
        """Update round/orepot info in the UI."""
        orepot = data.get("beanpotPoolFormatted", "0.0") # Keep beanpot fallback if API re-uses it or change later
        round_id = data.get("roundId", "?")
        self.orepot_label.setText(f"R#{round_id} | Pot: {orepot} ORE")

    def _append_ai_log(self, text: str):
        """Append a line to the agent log display."""
        current = self.agent_log_label.text()
        lines = current.split('\n')
        if len(lines) > 8:
            lines = lines[-8:]
        lines.append(text)
        self.agent_log_label.setText('\n'.join(lines))

    def _update_winrate_ui(self, data: dict):
        """Update the Round History stats."""
        played = data.get("played", 0)
        
        # Round history card
        self.rounds_played_label.setText(f"{played} rounds played")
    def _toggle_mining(self):
        """Toggle mining on/off."""
        if not hasattr(self, 'scheduler') or not self.scheduler:
            return
        
        if self.scheduler.mining_active:
            self.scheduler.mining_active = False
            self.mining_toggle_btn.setText("▶ Start")
            self.mining_toggle_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(52, 211, 153, 0.2);
                    border: 1px solid rgba(52, 211, 153, 0.4);
                    border-radius: 13px;
                    color: #34d399;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover { background: rgba(52, 211, 153, 0.4); }
            """)
            self._append_ai_log("⏸️ Mining dihentikan oleh user")
        else:
            self.scheduler.mining_active = True
            self.mining_toggle_btn.setText("⏸ Stop")
            self.mining_toggle_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(239, 68, 68, 0.2);
                    border: 1px solid rgba(239, 68, 68, 0.4);
                    border-radius: 13px;
                    color: #f87171;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover { background: rgba(239, 68, 68, 0.4); }
            """)
            self._append_ai_log("▶️ Mining dilanjutkan!")

    def _update_greeting_ui(self, data: dict):
        """Update the greeting display."""
        message = data.get("message", "Hello, Master!")
        self.greeting_label.setText(message)

        # Also show in avatar speech bubble
        try:
            js = f'window.airiAvatar && window.airiAvatar.showSpeech("{message}", 8000);'
            self.avatar_view.page().runJavaScript(js)
        except Exception:
            pass

    def _play_welcome_voice(self):
        """Play the welcome audio file based on the time of day."""
        import pygame
        from pathlib import Path
        
        now = datetime.now()
        hour = now.hour
        
        if 4 <= hour < 11:
            filename = "pagi.mp3"
        elif 11 <= hour < 15:
            filename = "siang.mp3"
        elif 15 <= hour < 19:
            filename = "sore.mp3"
        elif 19 <= hour <= 23:
            filename = "malam.mp3"
        else:
            filename = "dinihari.mp3"

        welcome_path = Path(__file__).parent.parent / "assets" / filename
        
        if welcome_path.exists():
            try:
                # Ensure mixer is initialized
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(str(welcome_path))
                pygame.mixer.music.play()
                print(f"[UI] Playing welcome voice: {filename}")
            except Exception as e:
                print(f"[UI] Error playing welcome voice: {e}")
        else:
            print(f"[UI] Welcome voice file not found: {welcome_path}")

    def _voice_callback(self, data: dict):
        """Callback from voice background thread."""
        self.signal_bridge.voice_status_updated.emit(data)

    def _update_voice_ui(self, data: dict):
        """Update UI based on voice status."""
        status_msg = data.get("status", "")
        is_active = data.get("is_active", False)
        command = data.get("command", None)

        # Update status bar
        if is_active:
            self.status_label.setText(f"● {status_msg}")
            self.status_label.setStyleSheet("color: #f43f5e; font-size: 9px;") # Red for listening
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(244, 63, 94, 0.3);
                    border: 1px solid rgba(244, 63, 94, 0.6);
                    border-radius: 14px;
                    font-size: 14px;
                }
            """)
        else:
            self.status_label.setText("● Online")
            self.status_label.setStyleSheet("color: #34d399; font-size: 9px;") # Green
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(139, 92, 246, 0.2);
                    border: 1px solid rgba(139, 92, 246, 0.4);
                    border-radius: 14px;
                    font-size: 14px;
                }
                QPushButton:hover { background: rgba(139, 92, 246, 0.4); }
                QPushButton:pressed { background: rgba(139, 92, 246, 0.6); }
            """)

        # If a command was processed, show it in the greeting label briefly
        if command:
            self.greeting_label.setText(f'🗣️ "{command}"\n{status_msg}')
            # Send to avatar speech bubble
            try:
                js = f'window.airiAvatar && window.airiAvatar.showSpeech("Memproses: {command}...", 3000);'
                self.avatar_view.page().runJavaScript(js)
            except Exception:
                pass

    # ── Actions ───────────────────────────────────────────────────

    def _trigger_voice(self):
        """Manually trigger voice listening."""
        if not self.voice_executor.is_listening:
            self.voice_executor.trigger_listen()

    def _on_refresh_wallet(self):
        """Force wallet refresh (unused currently, but placeholder)."""
        if hasattr(self, 'scheduler') and self.scheduler:
            self.scheduler._fetch_user_data()

    def set_scheduler(self, scheduler):
        """Set the scheduler reference for refresh buttons."""
        self.scheduler = scheduler

    # ── Clock ─────────────────────────────────────────────────────

    def _start_clock(self):
        """Start the clock timer."""
        self._update_clock()
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

    def _update_clock(self):
        """Update the clock display."""
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M"))

    # ── Global Hotkey ─────────────────────────────────────────────

    def _setup_global_hotkey(self):
        """Setup global hotkey listener correctly."""
        try:
            keyboard.add_hotkey('ctrl+shift+a', self._trigger_voice)
        except Exception as e:
            print(f"[UI] Warning: Could not register hotkey: {e}")

    # ── Window Dragging ───────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── System Tray ───────────────────────────────────────────────

    def setup_tray(self):
        """Setup system tray icon and menu."""
        self.tray_icon = QSystemTrayIcon(self)

        # Create a simple colored icon
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setBrush(QColor(139, 92, 246))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(8, 8, 16, 16)
        painter.end()

        self.tray_icon.setIcon(QIcon(pixmap))
        self.tray_icon.setToolTip("Airi AI Assistant")

        # Tray menu
        tray_menu = QMenu()

        show_action = QAction("Show Airi", self)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)

        refresh_action = QAction("Refresh Wallet", self)
        refresh_action.triggered.connect(self._on_refresh_wallet)
        tray_menu.addAction(refresh_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _minimize_to_tray(self):
        """Minimize to system tray."""
        self.hide()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage(
                "Airi",
                "Airi is still running in the background~",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

    def _show_window(self):
        """Show and activate the window."""
        self.show()
        self.activateWindow()

    def _tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    # ── Close Event ───────────────────────────────────────────────

    def closeEvent(self, event):
        """Handle window close."""
        if hasattr(self, 'scheduler') and self.scheduler:
            self.scheduler.stop()
        event.accept()
