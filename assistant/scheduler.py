"""
Airi Scheduler Module (Minebean Agent)
Runs the background loop, manages API data, SSE events, and invokes Strategy -> Web3 Deploy.
"""

import os
import time
import threading
from datetime import datetime

from assistant.ore_api import OreAPI
from assistant.ore_solana import OreSolana
from assistant.strategy import calculate_ev, select_random_blocks
from assistant.greeting import get_greeting
from assistant.telegram_bot import TelegramAgent


class AiriScheduler:
    """Background agent for Minebean."""

    def __init__(self, callback=None):
        self.callback = callback
        self._running = False
        self._thread = None
        
        # Ore modules
        rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        priv_key = os.getenv("PRIVATE_KEY", "")
        self.api = OreAPI(sse_callback=self._handle_sse)
        self.api.set_rpc(rpc_url)  # Share the RPC URL for on-chain reads
        self.web3 = OreSolana(rpc_url, priv_key)
        
        # Telegram Bot Integration
        tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.telegram_bot = TelegramAgent(tg_token, tg_chat_id, self) if tg_token and tg_chat_id else None
        
        # State
        self.wallet_addr = self.web3.wallet_addr
        self.global_stats = {}
        self.ore_price = {}
        self.current_round = {}
        self.user_rewards = {}
        
        self.last_round_id = ""

        # Bot config
        self.num_blocks_to_play = 20
        self.bet_per_block = 0.0001
        self.bet_amount_sol = self.bet_per_block * self.num_blocks_to_play
        
        # Win/Loss & P&L tracking
        self.last_winning_block = -1
        self.last_deployed_round_id = ""
        self.rounds_played = 0
        self.rounds_won = 0
        self.total_sol_spent = 0.0
        self.total_sol_won = 0.0
        self.total_ore_earned = 0.0
        self.mining_active = True
        
        # Auto-claim config
        self.auto_claim_sol_threshold = 0.01  # Claim automatically if pending SOL >= 0.01

    def _emit(self, event_type: str, data):
        """Emit an event to the UI callback."""
        if self.callback:
            try:
                self.callback(event_type, data)
            except Exception as e:
                print(f"[Scheduler] Callback error: {e}")

    def _handle_sse(self, sse_data: dict):
        """Handle incoming real-time events from SSE stream."""
        event_type = sse_data.get("type")
        payload = sse_data.get("data", {})
        
        if event_type == "deployed":
            # Grid updated by someone else
            self.current_round = payload
            self._emit("ore_grid_update", payload)
            
        elif event_type == "roundTransition":
            # Round ended, new one started
            settled = payload.get("settled", {})
            new_round = payload.get("newRound", {})
            
            # Log winning block result
            if settled:
                # Visually display +1 so user sees 1-25 instead of 0-24
                winning_block_id = settled.get("winningBlock", "?")
                winning_block = str(int(winning_block_id) + 1) if winning_block_id != "?" else "?"
                
                # Save the last winning block id for exclusion in the next round
                if winning_block_id != "?":
                    self.last_winning_block = int(winning_block_id)
                else:
                    self.last_winning_block = -1
                
                total_winnings = settled.get("totalWinnings", "0")
                top_miner = settled.get("topMiner", "")
                beanpot_hit = settled.get("beanpotAmount", "0") != "0"
                
                # Check if WE won (our deployed blocks contained the winning block)
                deployed_formatted = self.current_round.get("userDeployedFormatted", "0")
                we_played = float(deployed_formatted) > 0
                
                if we_played:
                    self.rounds_played += 1
                    self.total_sol_spent += self.bet_amount_sol
                    
                    # Check if our address is among winners
                    we_won = self.wallet_addr.lower() == top_miner.lower() if top_miner else False
                    
                    if we_won:
                        self.rounds_won += 1
                        # Track SOL winnings (assuming Ore API returns lamports in totalWinnings)
                        try:
                            win_sol = float(total_winnings) / 1e9
                            self.total_sol_won += win_sol
                        except:
                            pass
                        self._emit("ore_ai_log", f"🏆 R#{self.last_round_id} WIN! Block #{winning_block}")
                    else:
                        self._emit("ore_ai_log", f"💀 R#{self.last_round_id} LOSE | Block #{winning_block}")
                    
                    # ORE is earned every round you play
                    self.total_ore_earned += 1.0 / max(1, settled.get("totalMiners", 1))
                    
                    # Emit round history stats
                    win_rate = (self.rounds_won / self.rounds_played * 100) if self.rounds_played > 0 else 0
                    pnl = self.total_sol_won - self.total_sol_spent
                    self._emit("ore_winrate", {
                        "played": self.rounds_played,
                        "won": self.rounds_won,
                        "rate": win_rate,
                        "total_ore": self.total_ore_earned,
                        "total_pnl": pnl,
                    })
                else:
                    self._emit("ore_ai_log", f"⏭️ R#{self.last_round_id} skipped | Winner: Block #{winning_block}")
                
                if beanpot_hit:
                    self._emit("ore_ai_log", f"🫘🎉 OREPOT HIT! Jackpot triggered!")
                    if getattr(self, "telegram_bot", None) and we_won:
                        self.telegram_bot.send_notification("🎉 *JACKPOT! Motherlode terpicu dan kita menang!*\nCek `/status` untuk melihat pending rewards.")
            else:
                self._emit("ore_ai_log", f"⏩ R#{self.last_round_id} empty round (no deploys)")
            
            print(f"[Agent] Round {self.last_round_id} ended. Winner block: {settled.get('winningBlock', '?')}")
            
            self.current_round = new_round
            self.last_round_id = new_round.get("roundId", "")
            self._emit("ore_round_start", new_round)
            
            # Fetch updated wallet info/rewards when round ends
            self._fetch_user_data()

    def _fetch_user_data(self):
        """Fetch wallet balance and pending rewards."""
        sol_bal = self.web3.get_sol_balance()
        if self.wallet_addr:
            rewards = self.api.get_user_rewards(self.wallet_addr)
            self.user_rewards = rewards
            self._emit("ore_wallet_update", {
                "address": self.wallet_addr,
                "sol_balance": sol_bal,
                "rewards": rewards
            })
            
            # Check for Auto-Claim SOL
            pending_sol = float(rewards.get("pendingSOLFormatted", "0"))
            if pending_sol >= self.auto_claim_sol_threshold:
                self._emit("ore_ai_log", f"💰 Auto-Claiming {pending_sol:.4f} SOL...")
                tx = self.web3.claim_sol()
                if tx:
                    self._emit("ore_ai_log", f"✅ Claimed SOL! TX: {tx[:16]}...")
                    self.total_sol_spent = 0.0  # Reset session P&L logic
        else:
            self._emit("ore_wallet_update", {"error": "No wallet loaded"})

    def _agent_loop(self):
        """Main AI loop running continuously."""
        # Initial greeting
        greeting = get_greeting()
        self._emit("greeting", greeting)

        # Initial data fetch
        stats_price = self.api.get_stats_and_price()
        self.global_stats = stats_price.get("stats", {})
        self.ore_price = stats_price.get("price", {})
        
        self.current_round = self.api.get_current_round(self.wallet_addr)
        self.last_round_id = self.current_round.get("roundId", "")
        
        self._fetch_user_data()
        
        # Start SSE (handles grid updates silently in background)
        self.api.start_sse_stream()
        
        print("[Agent] Mining loop started.")
        
        last_wallet_refresh = 0
        last_round_refresh = 0

        while self._running:
            now_ts = int(time.time())
            
            # Re-fetch price/stats every 60 seconds
            if now_ts % 60 == 0:
                sp = self.api.get_stats_and_price()
                if sp:
                    self.global_stats = sp.get("stats", {})
                    self.ore_price = sp.get("price", {})

            # Re-fetch wallet balance + rewards every 30 seconds
            if now_ts - last_wallet_refresh >= 30:
                self._fetch_user_data()
                last_wallet_refresh = now_ts

            # Re-fetch round state every 10 seconds (in case SSE lags)
            if now_ts - last_round_refresh >= 10:
                fresh_round = self.api.get_current_round(self.wallet_addr)
                if fresh_round:
                    new_round_id = fresh_round.get("roundId", "")
                    if new_round_id != self.last_round_id:
                        self._emit("ore_ai_log", f"🔄 New round detected: R#{new_round_id}")
                        self._emit("ore_round_start", fresh_round)
                    self.current_round = fresh_round
                    self.last_round_id = new_round_id
                last_round_refresh = now_ts

            # Deploy only if mining is active
            if self.current_round and self.wallet_addr and self.mining_active:
                # Check if we already deployed this round (API level or Local state)
                already_deployed_api = float(self.current_round.get("userDeployedFormatted", "0")) > 0
                already_deployed_local = self.last_deployed_round_id == self.last_round_id
                
                if not already_deployed_api and not already_deployed_local:
                    # Check timing: deploy near the end of the round (10-15s remaining)
                    end_time = self.current_round.get("endTime", 0)
                    now_ts = int(time.time())
                    time_remaining = end_time - now_ts
                    
                    # Log status
                    if time_remaining > 0 and time_remaining % 10 == 0:
                        self._emit("ore_ai_log", f"[{datetime.now().strftime('%H:%M:%S')}] R#{self.last_round_id} | {time_remaining}s remaining")
                    
                    # Deploy when 20-30 seconds remaining (late deploy strategy)
                    if 20 <= time_remaining <= 30:
                        # Pick random squares, excluding previous winner
                        blocks_to_play = select_random_blocks(self.num_blocks_to_play, self.last_winning_block)
                        
                        self._emit("ore_ai_log", f"🚀 Deploying {self.bet_amount_sol} SOL → squares {blocks_to_play}")
                        
                        # Check if miner needs to checkpoint a previous round
                        miner_round_id = self.user_rewards.get("roundId", 0)
                        checkpoint_id = self.user_rewards.get("checkpointId", 0)
                        needs_checkpoint = False
                        
                        if miner_round_id > 0 and checkpoint_id != miner_round_id:
                            if miner_round_id != int(self.last_round_id):
                                needs_checkpoint = True
                        
                        # Execute on-chain
                        tx_hash = self.web3.deploy(
                            block_ids=blocks_to_play, 
                            total_sol_bet=self.bet_amount_sol, 
                            round_id=int(self.last_round_id),
                            needs_checkpoint=needs_checkpoint,
                            miner_round_id=miner_round_id
                        )
                        
                        if tx_hash:
                            self._emit("ore_ai_log", f"✅ TX: {tx_hash[:16]}...")
                            self.current_round["userDeployedFormatted"] = str(self.bet_amount_sol)
                            self.last_deployed_round_id = self.last_round_id
                        else:
                            self._emit("ore_ai_log", f"❌ Deploy gagal, coba ronde berikutnya")

            # Sleep briefly
            time.sleep(2)


    def start(self):
        """Start the agent in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._agent_loop, daemon=True)
        self._thread.start()
        
        if getattr(self, "telegram_bot", None):
            self.telegram_bot.start()
            
        print("[Scheduler] Agent Started")

    def stop(self):
        """Stop the agent."""
        self._running = False
        self.api.stop_sse_stream()
        if self._thread:
            self._thread.join(timeout=5)
            
        if getattr(self, "telegram_bot", None):
            self.telegram_bot.stop()
            
        print("[Scheduler] Agent Stopped")
