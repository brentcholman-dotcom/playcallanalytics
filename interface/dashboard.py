from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
import time

console = Console()

class TerminalDashboard:
    def __init__(self, recommender):
        self.recommender = recommender

    def make_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        layout["main"].split_column(
            Layout(name="situation", size=5),
            Layout(name="options"),
            Layout(name="factors")
        )
        return layout

    def generate_content(self, layout, rec):
        if not rec:
            layout["main"].update(Panel("Waiting for data..."))
            return

        sit = rec['situation']
        
        # Header
        layout["header"].update(Panel(f"LIVE ANALYTICS: {sit.get('posteam')} ball", style="white on blue"))
        
        # Situation
        layout["situation"].update(Panel(
            f"SITUATION: 4th & {sit.get('ydstogo')} at {sit.get('yardline_100')}",
            title="Current Drive"
        ))
        
        # Options
        opt_table = Table(show_header=False, expand=True)
        opt_table.add_column("Option")
        opt_table.add_column("Details")
        
        go = rec['options']['go_for_it']
        strength = "BOLD GREEN" if rec['recommendation'] == 'go_for_it' else "WHITE"
        opt_table.add_row(Text("GO FOR IT", style=strength), f"Conv: {go['conversion_prob']:.1%}")
        opt_table.add_row("PUNT", "Expected net: 38 yds")
        
        layout["options"].update(Panel(opt_table, title="Recommendations"))
        
        # Factors
        factor_table = Table(show_header=True, expand=True)
        factor_table.add_column("Factor")
        factor_table.add_column("Impact")
        
        for f in rec['key_factors']:
            factor_table.add_row(f['factor'], f['impact'])
            
        layout["factors"].update(Panel(factor_table, title="Context Factors"))
        
        # Footer
        layout["footer"].update(Panel("[I] Add injury  [D] Enter dB  [Q] Quit", style="dim"))

    def run(self):
        layout = self.make_layout()
        with Live(layout, refresh_per_second=1, screen=True):
            while True:
                rec = self.recommender.get_recommendation()
                self.generate_content(layout, rec)
                time.sleep(5)
                # Keyboard input handling would go here (requires complex non-blocking input)
