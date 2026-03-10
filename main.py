"""
Airi AI Desktop Assistant
══════════════════════════

A desktop assistant with Live2D avatar, crypto price tracking,
and AI-powered market analysis.

Usage:
    python main.py

Configuration:
    - config/settings.json  → App settings
    - .env                  → API keys (OPENROUTER_API_KEY)
    - system_prompt.txt     → AI system prompt
"""

import sys
import os
from pathlib import Path

# Ensure the project root is in the path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.main_window import AiriMainWindow
from assistant.scheduler import AiriScheduler


def main():
    """Main entry point for Airi AI Assistant."""
    # High DPI scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Airi AI Assistant")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # Create main window
    window = AiriMainWindow()

    # Create scheduler with UI callback
    scheduler = AiriScheduler(callback=window.signal_bridge_callback)
    window.set_scheduler(scheduler)

    # Setup system tray
    window.setup_tray()

    # Start scheduler (will begin fetching data)
    scheduler.start()

    # Show window
    window.show()

    print("=" * 50)
    print("  ✦ AIRI AI Assistant v1.0.0")
    print("  ✦ Desktop assistant is running!")
    print("  ✦ Minimize to tray with the — button")
    print("=" * 50)

    # Run the app
    exit_code = app.exec()

    # Cleanup
    scheduler.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
