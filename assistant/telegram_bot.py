import os
import threading
import telebot

class TelegramAgent:
    def __init__(self, token, chat_id, scheduler):
        self.bot = telebot.TeleBot(token)
        self.chat_id = chat_id
        self.scheduler = scheduler
        self._thread = None
        self._running = False
        
        self._register_handlers()
        
    def _register_handlers(self):
        @self.bot.message_handler(commands=['start', 'help'])
        def send_welcome(message):
            if str(message.chat.id) != str(self.chat_id):
                return
            
            help_text = (
                "🤖 *Airi Ore Agent Bot*\n\n"
                "Available commands:\n"
                "/status - Check wallet balance, total mined, and pending rewards\n"
            )
            self.bot.reply_to(message, help_text, parse_mode="Markdown")

        @self.bot.message_handler(commands=['status', 'balance', 'rewards'])
        def send_status(message):
            if str(message.chat.id) != str(self.chat_id):
                return
            
            wallet = self.scheduler.wallet_addr
            if not wallet:
                self.bot.reply_to(message, "⚠️ Wait, wallet is not loaded yet.")
                return
            
            # Formulate the response
            sol_bal = self.scheduler.web3.get_sol_balance()
            
            # Attempt to pull from the scheduler's cached rewards and stats
            rewards = self.scheduler.user_rewards
            
            pending_ore = rewards.get("pendingFormatted", "0.0")
            pending_sol = rewards.get("pendingSOLFormatted", "0.0")
            
            total_played = self.scheduler.rounds_played
            total_won = self.scheduler.rounds_won
            total_ore = self.scheduler.total_ore_earned
            pnl = self.scheduler.total_sol_won - self.scheduler.total_sol_spent
            
            win_rate = (total_won / total_played * 100) if total_played > 0 else 0
            
            status_text = (
                f"💳 *Wallet Settings*\n"
                f"`{wallet[:8]}...{wallet[-8:]}`\n"
                f"Balance: `{sol_bal:.4f} SOL`\n\n"
                f"🎁 *Pending Unclaimed Rewards*\n"
                f"ORE: `{pending_ore}`\n"
                f"SOL: `{pending_sol}`\n\n"
                f"📊 *Session Logs*\n"
                f"Win Rate: `{win_rate:.1f}% ({total_won}/{total_played})`\n"
                f"P&L: `{pnl:+.4f} SOL`\n"
                f"Total ORE Earned: `{total_ore:.4f}`"
            )
            
            self.bot.reply_to(message, status_text, parse_mode="Markdown")
            
    def send_notification(self, message_text):
        """Send a push notification to the authorized chat ID."""
        try:
            self.bot.send_message(self.chat_id, message_text, parse_mode="Markdown")
        except Exception as e:
            print(f"[Telegram] Failed to send notification: {e}")

    def _poll(self):
        try:
            print("[Telegram] Bot polling started...")
            self.bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"[Telegram] Bot polling error: {e}")

    def start(self):
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self.bot.stop_polling()
        if self._thread:
            self._thread.join(timeout=2)
