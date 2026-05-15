from __future__ import annotations

from rich.console import Console
from rich.table import Table

from .tracker import ProgressTracker

console = Console()


def print_summary(tracker: ProgressTracker) -> None:
    console.print()
    console.rule("[bold green]Solve Session Complete")
    console.print(f"  Total attempted: {tracker.total}")
    console.print(f"  Solved: [green]{tracker.solved_count}[/green]")
    console.print(f"  Failed: [red]{tracker.failed_count}[/red]")
    rate = (tracker.solved_count / tracker.total * 100) if tracker.total else 0
    console.print(f"  Solve rate: {rate:.1f}%")
    console.print(f"  Elapsed: {tracker.elapsed:.1f}s")
    console.print()

    table = Table(title="Results by Category")
    table.add_column("Category", style="cyan")
    table.add_column("Solved", style="green")
    table.add_column("Failed", style="red")
    table.add_column("Skipped", style="yellow")

    for cat, stats in sorted(tracker.stats_by_category().items()):
        table.add_row(cat, str(stats["solved"]), str(stats["failed"]), str(stats["skipped"]))

    console.print(table)
    console.print()

    table2 = Table(title="Results by Difficulty")
    table2.add_column("Difficulty", style="cyan")
    table2.add_column("Solved", style="green")
    table2.add_column("Failed", style="red")

    for diff, stats in sorted(tracker.stats_by_difficulty().items()):
        stars = "*" * diff
        table2.add_row(stars, str(stats["solved"]), str(stats["failed"]))

    console.print(table2)


def print_challenge_result(
    name: str, status: str, solver: str, attempts: int
) -> None:
    if status == "solved":
        console.print(f"  [green]SOLVED[/green] {name} (solver={solver}, attempts={attempts})")
    elif status == "failed":
        console.print(f"  [red]FAILED[/red] {name} (solver={solver}, attempts={attempts})")
    else:
        console.print(f"  [yellow]SKIPPED[/yellow] {name}")
