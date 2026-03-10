"""
Ore Supply Solana Web3 Adapter
Handles RPC communication, wallet balances, and transaction building/signing for Ore v3 on Solana.
Based on the official regolith-labs/ore Rust smart contract source code.
"""

import struct
import traceback
import base58
import time

from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts, TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
from solders.transaction import Transaction
from solders.message import Message
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price


# ── Ore Program Constants (from ore/api/src/consts.rs) ──────────────
ORE_PROGRAM_ID = Pubkey.from_string("oreV3EG1i9BEgiAJ8b177Z2S2rMarzak4NMv1kULvWv")
ORE_MINT       = Pubkey.from_string("oreoU2P8bN6jkk3jbaiVxYnG1dCXcYxwhwyK9jSybcp")
EXECUTOR_ADDR  = Pubkey.from_string("executor11111111111111111111111111111111112")

# PDA seeds (from ore/api/src/consts.rs)
AUTOMATION_SEED = b"automation"
BOARD_SEED      = b"board"
CONFIG_SEED     = b"config"
MINER_SEED      = b"miner"
ROUND_SEED      = b"round"

# Instruction discriminators (from ore/api/src/instruction.rs OreInstruction enum)
IX_DEPLOY    = 6
IX_CLAIM_SOL = 3
IX_CLAIM_ORE = 4
IX_CHECKPOINT = 2


class OreSolana:
    def __init__(self, rpc_url: str, private_key: str):
        self.rpc_url = rpc_url
        self.client = Client(rpc_url)
        self.keypair = None
        self.wallet_addr = ""

        if private_key:
            try:
                if not private_key.startswith("["):
                    secret_bytes = base58.b58decode(private_key)
                    self.keypair = Keypair.from_bytes(secret_bytes)
                else:
                    import json
                    secret_bytes = bytes(json.loads(private_key))
                    self.keypair = Keypair.from_bytes(secret_bytes)

                self.wallet_addr = str(self.keypair.pubkey())
                print(f"[OreSolana] Connected Wallet: {self.wallet_addr}")
            except Exception as e:
                print(f"[OreSolana] Invalid Private Key format: {e}")

    # ── PDA Derivations ─────────────────────────────────────────────
    def _find_pda(self, seeds: list[bytes]) -> Pubkey:
        """Derive a Program Derived Address for the Ore program."""
        pda, _ = Pubkey.find_program_address(seeds, ORE_PROGRAM_ID)
        return pda

    def _get_automation_pda(self, authority: Pubkey) -> Pubkey:
        return self._find_pda([AUTOMATION_SEED, bytes(authority)])

    def _get_board_pda(self) -> Pubkey:
        return self._find_pda([BOARD_SEED])

    def _get_config_pda(self) -> Pubkey:
        return self._find_pda([CONFIG_SEED])

    def _get_miner_pda(self, authority: Pubkey) -> Pubkey:
        return self._find_pda([MINER_SEED, bytes(authority)])

    def _get_round_pda(self) -> Pubkey:
        return self._find_pda([ROUND_SEED])

    # ── Balance Queries ─────────────────────────────────────────────
    def get_sol_balance(self) -> float:
        if not self.wallet_addr:
            return 0.0
        try:
            pubkey = Pubkey.from_string(self.wallet_addr)
            res = self.client.get_balance(pubkey)
            if res.value is not None:
                return res.value / 1e9
        except Exception as e:
            print(f"[OreSolana] Error fetching SOL balance: {e}")
        return 0.0

    def get_ore_balance(self) -> float:
        if not self.wallet_addr:
            return 0.0
        try:
            pubkey = Pubkey.from_string(self.wallet_addr)
            opts = TokenAccountOpts(mint=ORE_MINT)
            res = self.client.get_token_accounts_by_owner_json_parsed(pubkey, opts)
            if res.value:
                total = 0.0
                for account in res.value:
                    amount = account.account.data.parsed['info']['tokenAmount']['uiAmount']
                    total += float(amount)
                return total
        except Exception as e:
            print(f"[OreSolana] Error fetching ORE balance: {e}")
        return 0.0

    # ── Instruction Builders ────────────────────────────────────────
    def _build_deploy_ix(self, amount_lamports: int, block_ids: list[int]) -> Instruction:
        """
        Build the Deploy instruction for the Ore v3 program.
        
        Data layout (from ore/api/src/instruction.rs):
            u8  discriminator = 6 (Deploy)
            u64 amount         (little-endian, lamports per square)
            u32 squares        (little-endian, bitmask of 25 squares)
        
        Accounts (from ore/program/src/deploy.rs):
            0. signer       (signer, writable)
            1. authority     (writable)  – same as signer for manual deploy
            2. automation    (writable)  – PDA [b"automation", authority]
            3. board         (writable)  – PDA [b"board"]
            4. config        (readonly)  – PDA [b"config"]
            5. miner         (writable)  – PDA [b"miner", authority]
            6. round         (writable)  – PDA [b"round"]
            7. system_program
            8. ore_program
        """
        authority = self.keypair.pubkey()

        # Build the 25-bit bitmask. Block IDs are 0-24.
        mask = 0
        for block_id in block_ids:
            if 0 <= block_id <= 24:
                mask |= (1 << block_id)

        # Pack data: discriminator (u8) + amount (u64 LE) + squares (u32 LE)
        data = struct.pack("<BqI", IX_DEPLOY, amount_lamports, mask)

        accounts = [
            AccountMeta(authority, is_signer=True, is_writable=True),      # signer
            AccountMeta(authority, is_signer=False, is_writable=True),     # authority
            AccountMeta(self._get_automation_pda(authority), is_signer=False, is_writable=True),  # automation
            AccountMeta(self._get_board_pda(), is_signer=False, is_writable=True),               # board
            AccountMeta(self._get_config_pda(), is_signer=False, is_writable=False),             # config
            AccountMeta(self._get_miner_pda(authority), is_signer=False, is_writable=True),      # miner
            AccountMeta(self._get_round_pda(), is_signer=False, is_writable=True),               # round
            AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),                  # system_program
            AccountMeta(ORE_PROGRAM_ID, is_signer=False, is_writable=False),                     # ore_program
        ]

        return Instruction(ORE_PROGRAM_ID, data, accounts)

    def _build_claim_sol_ix(self) -> Instruction:
        """
        Build ClaimSOL instruction.
        
        Data: u8 discriminator = 3
        Accounts: signer, miner PDA, system_program
        """
        authority = self.keypair.pubkey()
        data = struct.pack("<B", IX_CLAIM_SOL)

        accounts = [
            AccountMeta(authority, is_signer=True, is_writable=True),
            AccountMeta(self._get_miner_pda(authority), is_signer=False, is_writable=True),
            AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ]

        return Instruction(ORE_PROGRAM_ID, data, accounts)

    def _build_claim_ore_ix(self) -> Instruction:
        """
        Build ClaimORE instruction.
        
        Data: u8 discriminator = 4
        Accounts: signer, miner PDA, system_program
        """
        authority = self.keypair.pubkey()
        data = struct.pack("<B", IX_CLAIM_ORE)

        accounts = [
            AccountMeta(authority, is_signer=True, is_writable=True),
            AccountMeta(self._get_miner_pda(authority), is_signer=False, is_writable=True),
            AccountMeta(SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ]

        return Instruction(ORE_PROGRAM_ID, data, accounts)

    # ── Transaction Senders ────────────────────────────────────────
    def _send_tx(self, instructions: list[Instruction], compute_units: int = 200_000, priority_fee_lamports: int = 10_000) -> str:
        """Build, sign, and send a transaction."""
        if not self.keypair:
            return ""

        try:
            # Prepend compute budget instructions
            compute_ix = set_compute_unit_limit(compute_units)
            priority_ix = set_compute_unit_price(priority_fee_lamports)

            all_ixs = [compute_ix, priority_ix] + instructions

            # Get recent blockhash
            blockhash_resp = self.client.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            msg = Message.new_with_blockhash(
                all_ixs,
                self.keypair.pubkey(),
                recent_blockhash
            )
            tx = Transaction.new_unsigned(msg)
            tx.sign([self.keypair], recent_blockhash)

            # Send with skip_preflight for speed
            opts = TxOpts(skip_preflight=True, max_retries=3)
            result = self.client.send_transaction(tx, opts)

            sig = str(result.value)
            print(f"[OreSolana] TX sent: {sig}")
            return sig

        except Exception as e:
            print(f"[OreSolana] TX Error: {e}")
            traceback.print_exc()
            return ""

    # ── Public Interface ────────────────────────────────────────────
    def deploy(self, block_ids: list, total_sol_bet: float) -> str:
        """Deploy SOL to the Ore Grid."""
        if not self.keypair:
            print("[OreSolana] Cannot deploy: Wallet not initialized.")
            return ""

        num_blocks = len(block_ids)
        if num_blocks == 0:
            return ""

        # Calculate lamports per square
        total_lamports = int(total_sol_bet * 1e9)
        amount_per_square = total_lamports // num_blocks

        print(f"[OreSolana] Deploying {total_sol_bet} SOL ({amount_per_square} lamports/square) to {num_blocks} blocks: {block_ids}")

        ix = self._build_deploy_ix(amount_per_square, block_ids)
        return self._send_tx([ix])

    def claim_sol(self) -> str:
        """Claim pending SOL rewards."""
        if not self.keypair:
            return ""
        print("[OreSolana] Claiming pending SOL...")
        ix = self._build_claim_sol_ix()
        return self._send_tx([ix], compute_units=50_000)

    def claim_ore(self) -> str:
        """Claim pending ORE rewards."""
        if not self.keypair:
            return ""
        print("[OreSolana] Claiming pending ORE...")
        ix = self._build_claim_ore_ix()
        return self._send_tx([ix], compute_units=50_000)
