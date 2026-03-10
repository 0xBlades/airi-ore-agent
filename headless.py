import time
import os
from assistant.scheduler import AiriScheduler

def main():
    print("="*50)
    print("  ✦ AIRI AI HEADLESS MINING AGENT")
    print("  ✦ Running on Railway / Cloud")
    print("="*50)
    
    # Ensure PRIVATE_KEY is available (Railway sets it via environment variables)
    if not os.getenv("PRIVATE_KEY"):
        print("⚠️ WARNING: PRIVATE_KEY environment variable is not set!")
        print("Please add it in your Railway project settings -> Variables")
    
    def on_event(event_type, data):
        # Print logs directly to the console so Railway logs can capture them
        if event_type == "ore_ai_log":
            print(data)
        elif event_type == "ore_winrate":
            rate = data.get("rate", 0)
            played = data.get("played", 0)
            won = data.get("won", 0)
            pnl = data.get("total_pnl", 0)
            ore = data.get("total_ore", 0)
            print(f"📊 [STATS] WR: {rate:.0f}% ({won}/{played}) | P&L: {pnl:+.4f} SOL | ORE: {ore:.2f}")

    # Launch the scheduler with our console callback
    agent = AiriScheduler(callback=on_event)
    agent.start()
    
    # Keep the main thread alive since agent runs in background thread
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Agent...")
        agent.stop()

if __name__ == "__main__":
    main()
