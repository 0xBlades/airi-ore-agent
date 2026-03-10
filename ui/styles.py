"""
Airi UI Styles
Dark theme with glassmorphism effects for the desktop assistant.
"""

MAIN_STYLESHEET = """
/* ═══ Global ═══ */
QMainWindow, QWidget {
    background-color: transparent;
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Noto Sans JP', sans-serif;
}

/* ═══ Main Container ═══ */
#mainContainer {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(15, 10, 30, 240),
        stop: 0.5 rgba(20, 15, 40, 235),
        stop: 1 rgba(10, 8, 25, 245)
    );
    border: 1px solid rgba(139, 92, 246, 0.25);
    border-radius: 20px;
}

/* ═══ Header ═══ */
#headerWidget {
    background: transparent;
    padding: 8px 16px;
}

#appTitle {
    color: #c4b5fd;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 1px;
}

#appSubtitle {
    color: #64748b;
    font-size: 10px;
}

#clockLabel {
    color: #8b5cf6;
    font-size: 22px;
    font-weight: 300;
    letter-spacing: 2px;
}

/* ═══ Avatar Container ═══ */
#avatarContainer {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(139, 92, 246, 0.08),
        stop: 1 rgba(79, 70, 229, 0.05)
    );
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 16px;
    margin: 4px 12px;
}

/* ═══ Greeting Card ═══ */
#greetingCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(139, 92, 246, 0.15),
        stop: 1 rgba(79, 70, 229, 0.1)
    );
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 14px;
    padding: 12px 16px;
    margin: 4px 12px;
}

#greetingText {
    color: #e2e8f0;
    font-size: 13px;
    font-weight: 500;
}

/* ═══ Section Cards ═══ */
.sectionCard {
    background: rgba(30, 25, 55, 0.6);
    border: 1px solid rgba(139, 92, 246, 0.12);
    border-radius: 14px;
    padding: 12px 14px;
    margin: 4px 12px;
}

#cryptoCard {
    background: rgba(30, 25, 55, 0.6);
    border: 1px solid rgba(139, 92, 246, 0.12);
    border-radius: 14px;
    padding: 12px 14px;
    margin: 4px 12px;
}

#analysisCard {
    background: rgba(30, 25, 55, 0.6);
    border: 1px solid rgba(139, 92, 246, 0.12);
    border-radius: 14px;
    padding: 12px 14px;
    margin: 4px 12px;
}

/* ═══ Section Headers ═══ */
.sectionTitle {
    color: #8b5cf6;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding-bottom: 6px;
}

/* ═══ Crypto Price Row ═══ */
.cryptoRow {
    background: rgba(139, 92, 246, 0.06);
    border-radius: 10px;
    padding: 8px 12px;
    margin: 3px 0;
}

.coinSymbol {
    color: #c4b5fd;
    font-size: 13px;
    font-weight: 700;
}

.coinPrice {
    color: #e2e8f0;
    font-size: 13px;
    font-weight: 600;
}

.changePositive {
    color: #34d399;
    font-size: 11px;
    font-weight: 600;
}

.changeNegative {
    color: #f87171;
    font-size: 11px;
    font-weight: 600;
}

/* ═══ Analysis Text ═══ */
#analysisText {
    color: #cbd5e1;
    font-size: 12px;
    line-height: 1.5;
}

/* ═══ Buttons ═══ */
QPushButton {
    background: rgba(139, 92, 246, 0.15);
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 10px;
    color: #c4b5fd;
    font-size: 11px;
    font-weight: 600;
    padding: 6px 14px;
    letter-spacing: 0.5px;
}

QPushButton:hover {
    background: rgba(139, 92, 246, 0.3);
    border-color: rgba(139, 92, 246, 0.5);
}

QPushButton:pressed {
    background: rgba(139, 92, 246, 0.4);
}

#closeBtn {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #fca5a5;
    border-radius: 12px;
    padding: 2px 8px;
    font-size: 14px;
    font-weight: bold;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
}

#closeBtn:hover {
    background: rgba(239, 68, 68, 0.4);
}

#minimizeBtn {
    background: rgba(250, 204, 21, 0.15);
    border: 1px solid rgba(250, 204, 21, 0.3);
    color: #fde047;
    border-radius: 12px;
    padding: 2px 8px;
    font-size: 14px;
    font-weight: bold;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
}

#minimizeBtn:hover {
    background: rgba(250, 204, 21, 0.4);
}

/* ═══ Scroll Area ═══ */
QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: rgba(30, 25, 55, 0.3);
    width: 6px;
    margin: 4px 2px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: rgba(139, 92, 246, 0.4);
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(139, 92, 246, 0.6);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

/* ═══ Status Bar ═══ */
#statusBar {
    background: transparent;
    padding: 4px 16px;
}

#statusText {
    color: #475569;
    font-size: 9px;
}

/* ═══ Loading Indicator ═══ */
#loadingLabel {
    color: #8b5cf6;
    font-size: 11px;
    font-style: italic;
}

/* ═══ System Tray Menu ═══ */
QMenu {
    background-color: rgba(20, 15, 40, 240);
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    color: #e2e8f0;
    padding: 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background: rgba(139, 92, 246, 0.3);
}
"""
