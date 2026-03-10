"""
Airi Scheduler Module (Minebean Agent)
Runs the background loop, manages API data, SSE events, and invokes Strategy -> Web3 Deploy.
"""

import time
import threading
from datetime import datetime

from assistant.minebean_api import MinebeanAPI
from assistant.minebean_web3 import MinebeanWeb3
from assistant.strategy import calculate_ev, select_best_blocks
from assistant.greeting import get_greeting


class AiriScheduler:
    """Background agent for Minebean."""

    def __init__(self, callback=None):
        self.callback = callback
        self._running = False
        self._thread = None
        
        # Minebean modules
        self.api = MinebeanAPI(sse_callback=self._handle_sse)
        self.web3 = MinebeanWeb3()
        
        # State
        self.wallet_addr = self.web3.get_address()
        self.global_stats = {}
        self.bean_price = {}
        self.current_round = {}
        self.user_rewards = {}
        
        self.last_round_id = ""

        # Bot config
        self.num_blocks_to_play = 20
        self.bet_per_block = 0.000005
        self.bet_amount_eth = round(self.bet_per_block * self.num_blocks_to_play, 18)
        
        # Win/Loss & P&L tracking
        self.rounds_played = 0
        self.rounds_won = 0
        self.total_eth_spent = 0.0
        self.total_eth_won = 0.0
        self.total_bean_earned = 0.0
        self.mining_active = True
        
        # Auto-claim config
        self.auto_claim_eth_threshold = 0.0005  # Claim automatically if pending ETH >= 0.0005

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
            self._emit("minebean_grid_update", payload)
            
        elif event_type == "roundTransition":
            # Round ended, new one started
            settled = payload.get("settled", {})
            new_round = payload.get("newRound", {})
            
            # Log winning block result
            if settled:
                # Visually display +1 so user sees 1-25 instead of 0-24
                winning_block_id = settled.get("winningBlock", "?")
                winning_block = str(int(winning_block_id) + 1) if winning_block_id != "?" else "?"
                
                total_winnings = settled.get("totalWinnings", "0")
                top_miner = settled.get("topMiner", "")
                beanpot_hit = settled.get("beanpotAmount", "0") != "0"
                
                # Check if WE won (our deployed blocks contained the winning block)
                deployed_formatted = self.current_round.get("userDeployedFormatted", "0")
                we_played = float(deployed_formatted) > 0
                
                if we_played:
                    self.rounds_played += 1
                    self.total_eth_spent += self.bet_amount_eth
                    
                    # Check if our address is among winners
                    we_won = self.wallet_addr.lower() == top_miner.lower() if top_miner else False
                    
                    if we_won:
                        self.rounds_won += 1
                        # Track ETH winnings
                        try:
                            win_eth = float(total_winnings) / 1e18
                            self.total_eth_won += win_eth
                        except:
                            pass
                        self._emit("minebean_ai_log", f"🏆 R#{self.last_round_id} WIN! Block #{winning_block}")
                    else:
                        self._emit("minebean_ai_log", f"💀 R#{self.last_round_id} LOSE | Block #{winning_block}")
                    
                    # BEAN is earned every round you play (1 BEAN/round distributed)
                    self.total_bean_earned += 1.0 / max(1, settled.get("totalMiners", 1))
                    
                    # Emit round history stats
                    win_rate = (self.rounds_won / self.rounds_played * 100) if self.rounds_played > 0 else 0
                    pnl = self.total_eth_won - self.total_eth_spent
                    self._emit("minebean_winrate", {
                        "played": self.rounds_played,
                        "won": self.rounds_won,
                        "rate": win_rate,
                        "total_bean": self.total_bean_earned,
                        "total_pnl": pnl,
                    })
                else:
                    self._emit("minebean_ai_log", f"⏭️ R#{self.last_round_id} skipped | Winner: Block #{winning_block}")
                
                if beanpot_hit:
                    self._emit("minebean_ai_log", f"🫘🎉 BEANPOT HIT! Jackpot triggered!")
            else:
                self._emit("minebean_ai_log", f"⏩ R#{self.last_round_id} empty round (no deploys)")
            
            print(f"[Agent] Round {self.last_round_id} ended. Winner block: {settled.get('winningBlock', '?')}")
            
            self.current_round = new_round
            self.last_round_id = new_round.get("roundId", "")
            self._emit("minebean_round_start", new_round)
            
            # Fetch updated wallet info/rewards when round ends
            self._fetch_user_data()

    def _fetch_user_data(self):
        """Fetch wallet balance and pending rewards."""
        eth_bal = self.web3.get_eth_balance()
        if self.wallet_addr:
            rewards = self.api.get_user_rewards(self.wallet_addr)
            self.user_rewards = rewards
            self._emit("minebean_wallet_update", {
                "address": self.wallet_addr,
                "eth_balance": eth_bal,
                "rewards": rewards
            })
            
            # Check for Auto-Claim ETH
            pending_eth = float(rewards.get("pendingETHFormatted", "0"))
            if pending_eth >= self.auto_claim_eth_threshold:
                self._emit("minebean_ai_log", f"💰 Auto-Claiming {pending_eth:.4f} ETH...")
                tx = self.web3.claim_eth()
                if tx:
                    self._emit("minebean_ai_log", f"✅ Claimed ETH! TX: {tx[:16]}...")
                    self.total_eth_spent = 0.0  # Reset session P&L logic if desired, or keep accumulating
        else:
            self._emit("minebean_wallet_update", {"error": "No wallet loaded"})

    def _agent_loop(self):
        """Main AI loop running continuously."""
        # Initial greeting
        greeting = get_greeting()
        self._emit("greeting", greeting)

        # Initial data fetch
        stats_price = self.api.get_stats_and_price()
        self.global_stats = stats_price.get("stats", {})
        self.bean_price = stats_price.get("price", {})
        
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
                    self.bean_price = sp.get("price", {})

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
                        self._emit("minebean_ai_log", f"🔄 New round detected: R#{new_round_id}")
                        self._emit("minebean_round_start", fresh_round)
                    self.current_round = fresh_round
                    self.last_round_id = new_round_id
                last_round_refresh = now_ts

            # Deploy only if mining is active
            if self.current_round and self.wallet_addr and self.mining_active:
                # Check if we already deployed this round
                already_deployed = float(self.current_round.get("userDeployedFormatted", "0")) > 0
                
                if not already_deployed:
                    # Check timing: deploy near the end of the round (10-15s remaining)
                    end_time = self.current_round.get("endTime", 0)
                    now_ts = int(time.time())
                    time_remaining = end_time - now_ts
                    
                    # Log status
                    if time_remaining > 0 and time_remaining % 10 == 0:
                        self._emit("minebean_ai_log", f"[{datetime.now().strftime('%H:%M:%S')}] R#{self.last_round_id} | {time_remaining}s remaining")
                    
                    # Deploy when 10-15 seconds remaining (late deploy strategy)
                    if 5 <= time_remaining <= 15:
                        # Extract the previous winning block from global stats
                        prev_winner_block = -1
                        try:
                            stats = self.global_stats.get("stats", {})
                            if stats:
                                # The winningBlock string looks like "Block X (YY%)" or just "X"
                                win_str = str(stats.get("winningBlock", ""))
                                import re
                                match = re.search(r'\d+', win_str)
                                if match:
                                    prev_winner_block = int(match.group()) - 1
                        except Exception as e:
                            pass
                            
                        # Pick 24 blocks (API returns 0-24, contract needs 0-24)
                        blocks_to_play = select_best_blocks(self.current_round, self.num_blocks_to_play, prev_winner_block)
                        
                        # Visually log 1-25 so the user doesn't panic
                        visual_blocks = [b + 1 for b in blocks_to_play]
                        self._emit("minebean_ai_log", f"🚀 Deploying {self.bet_amount_eth} ETH → blocks {visual_blocks}")
                        
                        # Execute on-chain
                        tx_hash = self.web3.deploy(blocks_to_play, self.bet_amount_eth)
                        
                        if tx_hash:
                            self._emit("minebean_ai_log", f"✅ TX: {tx_hash[:16]}...")
                            self.current_round["userDeployedFormatted"] = str(self.bet_amount_eth)
                        else:
                            self._emit("minebean_ai_log", f"❌ Deploy gagal, coba ronde berikutnya")

            # Sleep briefly
            time.sleep(2)


    def start(self):
        """Start the agent in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._agent_loop, daemon=True)
        self._thread.start()
        print("[Scheduler] Agent Started")

    def stop(self):
        """Stop the agent."""
        self._running = False
        self.api.stop_sse_stream()
        if self._thread:
            self._thread.join(timeout=5)
        print("[Scheduler] Agent Stopped")
