"""
Minebean Logic & Strategy Engine
Calculates Expected Value (EV) and decides which blocks to deploy.
"""

def calculate_ev(price_data: dict, current_round: dict, total_bet_sol: float) -> float:
    """
    Calculate the Expected Value (EV) of a round for Ore Supply.
    Net EV ≈ ORE_value + Orepot_EV - (SOL_deployed * effective_house_edge)
    """
    try:
        # Parse ORE price in Native SOL
        ore_price_sol = float(price_data.get("ore", {}).get("priceNative", 0))
        
        # 1 ORE distributed proportionally per round based on miners
        ore_value = 1.0 * ore_price_sol

        # Orepot probability (1/777 chance) - ensure we pull the correct pool formatted string if it exists
        # In minebean it was beanpotPool / 1e18, but it's safer to use beanpotPoolFormatted if available or just assume 11 decimals for ORE
        # For now, let's keep the raw division assuming 1e9 (lamports) or 1e11 (ore) depending on what the API sends.
        # Actually it's best to use the formatted string if the API returns 
        orepot_raw = float(current_round.get("beanpotPool", 0)) / 1e11 # ORE has 11 decimals typically
        orepot_ev = (1 / 777.0) * orepot_raw * ore_price_sol

        # Effective house edge logic (1% admin from everyone, 10% from losers)
        effective_house_edge = 0.11
        
        net_ev = ore_value + orepot_ev - (total_bet_sol * effective_house_edge)
        return net_ev
    except Exception as e:
        print(f"[Strategy] EV calculation error: {e}")
        return -1.0

def select_best_blocks(current_round: dict, num_blocks: int = 10) -> list[int]:
    """
    Select the least crowded squares for maximum profit share.
    
    All 25 squares have equal 1/25 win probability (Entropy VRF uniform random).
    Picking 15 squares = 15/25 = 60% chance one of ours is the winner.
    
    Strategy: Choose the squares with the LEAST total SOL deployed by others.
    If our square wins and we're the only/biggest miner on it, our proportional 
    payout is maximized.
    
    Ore uses 0-based square IDs (0-24) which map to a u32 bitmask.
    """
    blocks = current_round.get("blocks", [])
    if not blocks:
        # If no grid data, pick random squares (0-24)
        import random
        return random.sample(range(25), min(num_blocks, 25))
    
    # Sort blocks by total deployed SOL (ascending = least crowded first)
    sorted_blocks = sorted(blocks, key=lambda b: float(b.get("deployed", "0")))
    
    # Take the least crowded N blocks (ensure int IDs)
    selected_ids = [int(b["id"]) for b in sorted_blocks[:num_blocks]]
    return selected_ids
