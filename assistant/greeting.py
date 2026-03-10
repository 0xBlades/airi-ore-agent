"""
Airi Greeting Module
Generates personalized greetings based on the current time of day.
"""

import json
import random
from datetime import datetime
from pathlib import Path


def load_greetings() -> dict:
    """Load greeting messages from settings.json."""
    settings_path = Path(__file__).parent.parent / "config" / "settings.json"
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        return settings.get("greeting", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "morning": ["Ohayou, Master! ☀️ Selamat pagi!"],
            "afternoon": ["Konnichiwa, Master! 🌤️ Selamat siang!"],
            "evening": ["Konbanwa, Master! 🌅 Selamat sore!"],
            "night": ["Oyasumi, Master! 🌙 Selamat malam!"],
        }


def get_time_period(hour: int = None) -> str:
    """Determine the time period based on the hour."""
    if hour is None:
        hour = datetime.now().hour

    if 5 <= hour < 11:
        return "morning"
    elif 11 <= hour < 15:
        return "afternoon"
    elif 15 <= hour < 18:
        return "evening"
    else:
        return "night"


def get_greeting() -> dict:
    """
    Get a greeting message based on the current time.
    Returns a dict with 'period', 'message', and 'emoji'.
    """
    greetings = load_greetings()
    period = get_time_period()
    messages = greetings.get(period, ["Hello, Master!"])
    message = random.choice(messages)

    emoji_map = {
        "morning": "☀️",
        "afternoon": "🌤️",
        "evening": "🌅",
        "night": "🌙",
    }

    return {
        "period": period,
        "message": message,
        "emoji": emoji_map.get(period, "✨"),
        "timestamp": datetime.now().strftime("%H:%M"),
    }
