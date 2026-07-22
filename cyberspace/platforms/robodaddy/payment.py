"""User-friendly payment/cost display for RoboDaddy.

Every place RoboDaddy shows what a training run costs goes through these helpers
so the operator gets a consistent, readable summary: what they are paying for,
the GPU, the time, the total cost range, and a clear signal that a dry-run is
free and no money is spent until explicit confirmation.
"""
from __future__ import annotations


def cost_summary_lines(plan) -> list[str]:
    """Return a list of human-readable lines describing a plan's cost."""
    # Hourly rate is the GPU's $/hr; derived from the cost range and hours.
    hours = max(plan.hours, 0.01)
    hr_low = plan.cost_low / hours
    hr_mid = plan.cost_mid / hours
    hr_high = plan.cost_high / hours
    uncertainty = plan.cost_high - plan.cost_low
    lines = [
        f"[bold]What you are training:[/bold] {plan.base_model} on {plan.dataset_id}",
        f"[bold]Hardware:[/bold] {plan.num_gpus}x {plan.gpu}",
        f"[bold]Method:[/bold] {plan.method} for {plan.epochs} epochs (~{plan.samples:,} samples/epoch)",
        f"[bold]Hourly rate:[/bold] ~${hr_mid:.3f}/hr "
        f"[dim](${hr_low:.3f}-${hr_high:.3f}/hr)[/dim]",
        f"[bold]Estimated runtime:[/bold] {plan.hours:.1f} hours",
        f"[bold]Projected total:[/bold] about ${plan.cost_mid:.2f} "
        f"[dim](range ${plan.cost_low:.2f}-${plan.cost_high:.2f}, "
        f"+/-${uncertainty/2:.2f} uncertainty)[/dim]",
    ]
    return lines


def payment_panel_text(plan, provider: str) -> str:
    """Full payment summary text for a panel, including the cost/no-cost signal."""
    lines = [f"[bold cyan]{plan.name}[/bold cyan]", ""]
    lines.extend(cost_summary_lines(plan))
    lines.append("")
    if provider == "dry-run":
        lines.append("[green bold]COST: $0.00 — this is a FREE dry-run.[/green bold]")
        lines.append("[dim]No GPU is rented and no money is charged. A realistic "
                     "simulated training run is produced so you can preview the flow.[/dim]")
    else:
        lines.append("[yellow bold]This will RENT a real GPU and charge money.[/yellow bold]")
        lines.append(f"[dim]Projected charge: about ${plan.cost_mid:.2f} "
                     f"(range ${plan.cost_low:.2f}-${plan.cost_high:.2f}). "
                     "You will be asked to confirm before anything is rented.[/dim]")
    return "\n".join(lines)


def confirm_spend(console, plan, provider: str) -> bool:
    """Print a friendly payment panel and ask the operator to confirm.

    Returns True if the user wants to proceed. Dry-runs default to proceeding;
    paid runs default to declining (you must opt in to spending).
    """
    from rich.panel import Panel
    from rich.prompt import Confirm
    title = "RoboDaddy — payment summary" if provider == "vastai" else "RoboDaddy — dry-run preview"
    console.print(Panel(payment_panel_text(plan, provider), title=title, border_style="cyan"))
    if provider == "dry-run":
        return Confirm.ask("Launch this FREE dry-run?", default=True)
    return Confirm.ask("Rent the GPU and start PAID training? (this charges money)",
                       default=False)


def gpu_table_text(rows, best) -> str:
    """Human-readable text version of the GPU comparison for terminals/log files."""
    lines = [f"{'GPU':<12} {'VRAM':>6} {'hours':>7} {'$ low':>8} {'$ mid':>8} {'$ high':>8}  best"]
    for r in rows:
        star = "  <-- recommended" if r["gpu"] == best else ""
        lines.append(f"{r['gpu']:<12} {r['vram_gb']:>5}GB {r['hours']:>7} "
                     f"${r['cost_low']:>7.2f} ${r['cost_mid']:>7.2f} ${r['cost_high']:>7.2f}{star}")
    return "\n".join(lines)
