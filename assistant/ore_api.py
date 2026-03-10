"""
Ore Supply API Module
Fetches REST API data and manages SSE real-time connection from Ore Supply.
The endpoints mirror Minebean's architecture but on Solana.
"""

import requests
import json
import threading
from typing import Callable, Optional
import sseclient

REST_BASE_URL = "https://api.ore.supply"

class OreAPI:
    def __init__(self, sse_callback: Callable = None):
        self.sse_callback = sse_callback
        self._sse_running = False
        self._sse_thread = None
        
        # We need headers mimicking a browser to avoid 403 Cloudflare blocks
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def get_stats_and_price(self) -> dict:
        """Fetch global stats and ORE price."""
        try:
            r = requests.get(f"{REST_BASE_URL}/api/stats", headers=self.headers, timeout=10)
            r.raise_for_status()
            stats = r.json()

            p = requests.get(f"{REST_BASE_URL}/api/price", headers=self.headers, timeout=10)
            p.raise_for_status()
            price_data = p.json()

            return {"stats": stats, "price": price_data}
        except Exception as e:
            print(f"[OreAPI] Error fetching stats/price: {e}")
            return {}

    def get_current_round(self, user_addr: str = None) -> dict:
        """Fetch the current round state."""
        url = f"{REST_BASE_URL}/api/round/current"
        if user_addr:
            url += f"?user={user_addr}"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[OreAPI] Error fetching current round: {e}")
            return {}

    def get_user_rewards(self, user_addr: str) -> dict:
        """Fetch pending SOL and ORE for user."""
        try:
            r = requests.get(f"{REST_BASE_URL}/api/user/{user_addr}/rewards", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[OreAPI] Error fetching user rewards: {e}")
            return {}

    def start_sse_stream(self):
        """Start listening to real-time events."""
        if self._sse_running:
            return
        self._sse_running = True
        self._sse_thread = threading.Thread(target=self._sse_worker, daemon=True)
        self._sse_thread.start()

    def stop_sse_stream(self):
        """Stop SSE stream."""
        self._sse_running = False

    def _sse_worker(self):
        url = f"{REST_BASE_URL}/api/events/rounds"
        while self._sse_running:
            try:
                # SSE usually needs stream=True and careful timeout handling
                response = requests.get(url, headers=self.headers, stream=True, timeout=90)
                client = sseclient.SSEClient(response)
                for event in client.events():
                    if not self._sse_running:
                        break
                    if event.data:
                        try:
                            data = json.loads(event.data)
                            if self.sse_callback and data.get("type") in ["deployed", "roundTransition"]:
                                self.sse_callback(data)
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                print(f"[OreAPI] SSE stream error: {e}. Reconnecting in 3s...")
                import time
                time.sleep(3)
