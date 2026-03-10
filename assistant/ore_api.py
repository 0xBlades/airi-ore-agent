"""
Ore Supply On-Chain Data Reader
Reads Board, Round, and Miner state directly from the Solana blockchain via RPC.
No REST API dependency — everything comes straight from the program accounts.
"""

import struct
import time
import threading
from typing import Optional
from solana.rpc.api import Client
from solders.pubkey import Pubkey

# Ore Program
ORE_PROGRAM_ID = Pubkey.from_string("oreV3EG1i9BEgiAJ8b177Z2S2rMarzak4NMv1kULvWv")

# PDA Seeds
BOARD_SEED  = b"board"
ROUND_SEED  = b"round"
MINER_SEED  = b"miner"

# Account discriminator size (Steel framework uses 8 bytes)
DISC_SIZE = 8


def _find_pda(seeds: list[bytes]) -> Pubkey:
    pda, _ = Pubkey.find_program_address(seeds, ORE_PROGRAM_ID)
    return pda


def parse_board(data: bytes) -> dict:
    """
    Board struct (32 bytes after 8-byte discriminator):
        round_id:   u64
        start_slot: u64
        end_slot:   u64
        epoch_id:   u64
    """
    if len(data) < DISC_SIZE + 32:
        return {}
    d = data[DISC_SIZE:]
    round_id, start_slot, end_slot, epoch_id = struct.unpack_from("<QQQQ", d, 0)
    return {
        "roundId": round_id,
        "startSlot": start_slot,
        "endSlot": end_slot,
        "epochId": epoch_id,
    }


def parse_round(data: bytes) -> dict:
    """
    Round struct (after 8-byte discriminator):
        id:              u64
        deployed:        [u64; 25]  (200 bytes)
        slot_hash:       [u8; 32]
        count:           [u64; 25]  (200 bytes)
        expires_at:      u64
        motherlode:      u64
        rent_payer:      Pubkey (32 bytes)
        top_miner:       Pubkey (32 bytes)
        top_miner_reward: u64
        total_deployed:  u64
        total_miners:    u64
        total_vaulted:   u64
        total_winnings:  u64
    """
    if len(data) < DISC_SIZE + 8:
        return {}
    d = data[DISC_SIZE:]
    
    offset = 0
    round_id = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    
    deployed = list(struct.unpack_from("<25Q", d, offset)); offset += 200
    
    slot_hash = d[offset:offset+32]; offset += 32
    
    count = list(struct.unpack_from("<25Q", d, offset)); offset += 200
    
    expires_at = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    motherlode = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    
    # rent_payer (Pubkey 32 bytes)
    offset += 32
    # top_miner (Pubkey 32 bytes)
    top_miner_bytes = d[offset:offset+32]; offset += 32
    top_miner = str(Pubkey.from_bytes(top_miner_bytes))
    
    top_miner_reward = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    total_deployed = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    total_miners = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    total_vaulted = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    total_winnings = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    
    # Build blocks array for strategy compatibility
    blocks = []
    for i in range(25):
        blocks.append({
            "id": i,
            "deployed": str(deployed[i] / 1e9),  # Convert lamports to SOL
            "count": count[i],
        })
    
    return {
        "roundId": str(round_id),
        "startSlot": start_slot if 'start_slot' in dir() else 0,
        "endSlot": expires_at,
        "deployed": deployed,
        "count": count,
        "blocks": blocks,
        "totalDeployed": total_deployed,
        "totalMiners": total_miners,
        "totalWinnings": total_winnings,
        "motherlode": motherlode,
        "motherlodeFormatted": f"{motherlode / 1e9:.6f}",
        "topMiner": top_miner,
        "beanpotPoolFormatted": f"{motherlode / 1e9:.6f}",  # For UI compatibility
        "userDeployedFormatted": "0",  # Will be updated by caller
    }


def parse_miner(data: bytes) -> dict:
    """
    Miner struct (after 8-byte discriminator):
        authority:           Pubkey (32)
        deployed:            [u64; 25] (200)
        cumulative:          [u64; 25] (200)
        checkpoint_fee:      u64
        checkpoint_id:       u64
        last_claim_ore_at:   i64
        last_claim_sol_at:   i64
        rewards_factor:      Numeric (16 bytes - u128)
        rewards_sol:         u64
        rewards_ore:         u64
        refined_ore:         u64
        round_id:            u64
        lifetime_rewards_sol: u64
        lifetime_rewards_ore: u64
        lifetime_deployed:   u64
    """
    if len(data) < DISC_SIZE + 32:
        return {}
    d = data[DISC_SIZE:]
    
    offset = 0
    authority = str(Pubkey.from_bytes(d[offset:offset+32])); offset += 32
    
    deployed = list(struct.unpack_from("<25Q", d, offset)); offset += 200
    cumulative = list(struct.unpack_from("<25Q", d, offset)); offset += 200
    
    checkpoint_fee = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    checkpoint_id = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    last_claim_ore_at = struct.unpack_from("<q", d, offset)[0]; offset += 8
    last_claim_sol_at = struct.unpack_from("<q", d, offset)[0]; offset += 8
    
    # Numeric is a u128 (16 bytes)
    offset += 16
    
    rewards_sol = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    rewards_ore = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    refined_ore = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    round_id = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    lifetime_rewards_sol = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    lifetime_rewards_ore = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    lifetime_deployed = struct.unpack_from("<Q", d, offset)[0]; offset += 8
    
    return {
        "authority": authority,
        "rewardsSOL": rewards_sol,
        "rewardsORE": rewards_ore,
        "refinedORE": refined_ore,
        "pendingSOLFormatted": f"{rewards_sol / 1e9:.6f}",
        "pendingOREFormatted": f"{(rewards_ore + refined_ore) / 1e11:.6f}",  # ORE has 11 decimals
        "roundId": round_id,
        "checkpointId": checkpoint_id,
        "lifetimeRewardsSOL": lifetime_rewards_sol,
        "lifetimeRewardsORE": lifetime_rewards_ore,
        "lifetimeDeployed": lifetime_deployed,
        "deployed": deployed,
    }


class OreAPI:
    """Reads Ore state directly from Solana RPC (no REST API needed)."""
    
    def __init__(self, sse_callback=None):
        self.sse_callback = sse_callback
        self._poll_running = False
        self._poll_thread = None
        self.rpc_url = ""
        self.client = None
        self.last_round_id = 0
    
    def set_rpc(self, rpc_url: str):
        """Set the RPC client (called by scheduler after initialization)."""
        self.rpc_url = rpc_url
        self.client = Client(rpc_url)
    
    def _get_account_data(self, pubkey: Pubkey) -> Optional[bytes]:
        """Fetch raw account data from RPC."""
        if not self.client:
            return None
        try:
            resp = self.client.get_account_info(pubkey)
            if resp.value and resp.value.data:
                return bytes(resp.value.data)
        except Exception as e:
            print(f"[OreAPI] RPC error for {pubkey}: {e}")
        return None

    def get_board(self) -> dict:
        """Read the Board account to get current round_id and timing."""
        board_pda = _find_pda([BOARD_SEED])
        data = self._get_account_data(board_pda)
        if data:
            return parse_board(data)
        return {}

    def get_current_round(self, user_addr: str = None) -> dict:
        """Read the current round from on-chain data."""
        board = self.get_board()
        if not board:
            return {}
        
        round_id = board["roundId"]
        round_pda = _find_pda([ROUND_SEED, struct.pack("<Q", round_id)])
        data = self._get_account_data(round_pda)
        
        if data:
            round_data = parse_round(data)
            
            # Estimate endTime in unix seconds from endSlot
            # Solana slot time ~400ms. Get current slot to calculate remaining time.
            try:
                slot_resp = self.client.get_slot()
                current_slot = slot_resp.value
                end_slot = board["endSlot"]
                remaining_slots = max(0, end_slot - current_slot)
                remaining_seconds = int(remaining_slots * 0.4)  # ~400ms per slot
                round_data["endTime"] = int(time.time()) + remaining_seconds
                round_data["remainingSeconds"] = remaining_seconds
            except:
                round_data["endTime"] = int(time.time()) + 60
            
            # Check if user has deployed this round
            if user_addr:
                miner_data = self.get_user_rewards(user_addr)
                if miner_data and miner_data.get("roundId") == round_id:
                    user_deployed = sum(miner_data.get("deployed", []))
                    round_data["userDeployedFormatted"] = f"{user_deployed / 1e9:.6f}"
            
            return round_data
        return {}

    def get_user_rewards(self, user_addr: str) -> dict:
        """Read the Miner PDA to get pending rewards."""
        try:
            authority = Pubkey.from_string(user_addr)
            miner_pda = _find_pda([MINER_SEED, bytes(authority)])
            data = self._get_account_data(miner_pda)
            if data:
                return parse_miner(data)
        except Exception as e:
            print(f"[OreAPI] Error reading miner: {e}")
        return {}

    def get_stats_and_price(self) -> dict:
        """Get basic stats from on-chain data."""
        board = self.get_board()
        return {"stats": board, "price": {"ore": {"priceNative": "0"}}}

    def start_sse_stream(self):
        """Start polling for round transitions (replaces SSE)."""
        if self._poll_running:
            return
        self._poll_running = True
        self._poll_thread = threading.Thread(target=self._poll_worker, daemon=True)
        self._poll_thread.start()

    def stop_sse_stream(self):
        self._poll_running = False

    def _poll_worker(self):
        """Poll the board every 5 seconds to detect round transitions."""
        while self._poll_running:
            try:
                board = self.get_board()
                if board:
                    current_round_id = board["roundId"]
                    if self.last_round_id > 0 and current_round_id != self.last_round_id:
                        # Round changed! Fetch new round data and emit event
                        new_round = self.get_current_round()
                        if self.sse_callback and new_round:
                            self.sse_callback({
                                "type": "roundTransition",
                                "data": {
                                    "settled": {"winningBlock": "?", "totalMiners": 0},
                                    "newRound": new_round,
                                }
                            })
                    self.last_round_id = current_round_id
            except Exception as e:
                print(f"[OreAPI] Poll error: {e}")
            time.sleep(5)
