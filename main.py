import argparse
import sys
from scripts.run_backtest import main as run_backtest_script
from interface.recommender import RecommendationEngine
from models.conversion import ConversionModel
from interface.dashboard import TerminalDashboard

def main():
    parser = argparse.ArgumentParser(description="NFL Context-Aware Analytics System")
    subparsers = parser.add_subparsers(dest="command")

    # Backtest command
    bt_parser = subparsers.add_parser("backtest")
    bt_parser.add_argument("--seasons", nargs="+", type=int, default=[2022, 2023])

    # Live command
    live_parser = subparsers.add_parser("live")
    live_parser.add_argument("--game-id", type=str)
    live_parser.add_argument("--team", type=str)

    # Demo command
    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--game-id", type=str, default="401547654")

    # Report command
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--output", type=str, default="results.md")

    args = parser.parse_args()

    if args.command == "backtest":
        run_backtest_script()
    elif args.command == "live":
        print(f"Starting live tracking for game {args.game_id or args.team}...")
        # Initialize components and run dashboard
        model = ConversionModel() # Should load base rates first
        engine = RecommendationEngine(model)
        dash = TerminalDashboard(engine)
        dash.run()
    elif args.command == "demo":
        print(f"Running demo for game {args.game_id}...")
        # Demo logic
    elif args.command == "report":
        print(f"Generating report to {args.output}...")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
