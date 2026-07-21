"""CLI for RoboDaddy.

  cyberspace robodaddy <command>:

  usecases   browse use-case presets (offensive, defensive, assistant, ...)
  datasets   browse public training datasets for a model request
  gpus       browse GPU hardware + what each can train
  providers  browse GPU-rental marketplaces
  instances  search LIVE Vast.ai GPU offers (real prices, no key needed to browse)
  plan       interactive wizard: usecase -> data -> GPU -> days -> cost estimate
  train      run one or more fine-tune jobs (dry-run with stats, or Vast.ai)
  jobs       list training jobs + statistics (loss, samples, $, hours)
  models     registry of trained models
  serve      write a local Ollama Modelfile and API-key record
  keys       manage API keys for served models
  use        set a trained+served model as cyberbot's active LLM
"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .datasets import recommend_datasets
from .gpus import GPUS, best_value_gpu, gpus_for_model
from .plan import build_plan
from .presets import BASE_MODELS, PRESETS, preset_for, resolve_use_case
from .providers import PROVIDERS
from .registry import list_keys, list_models


def _print_dataset_table(console: Console, datasets: list[dict]) -> None:
    t = Table("#", "dataset", "HF repo", "size", "license/access", "schema")
    for i, d in enumerate(datasets):
        access = d.get("access", "-")
        t.add_row(str(i), d["name"], d["id"], d["size"],
                  f"{d['license']} / {access}", d.get("schema", "-"))
    console.print(t)
    console.print("\n[bold]notes[/bold]")
    for i, d in enumerate(datasets):
        marker = "recommended" if i == 0 else "candidate"
        console.print(f"  [{i}] {marker}: {d['id']} - {d['note']}")


def _print_search_results(console: Console, results: list[dict]) -> None:
    t = Table("#", "dataset", "HF repo", "use case", "size", "license/access")
    for i, d in enumerate(results):
        access = d.get("access", "-")
        t.add_row(str(i + 1), d["name"], d["id"], d.get("use_case_label", d.get("use_case", "-")),
                  d["size"], f"{d['license']} / {access}")
    console.print(t)
    console.print("\n[bold]notes[/bold]")
    for i, d in enumerate(results):
        console.print(f"  [{i + 1}] {d['id']} - {d['note']} "
                      f"[dim](use case: {d.get('use_case_label', d.get('use_case', '-'))})[/dim]")


def build_robodaddy_cli(console: Console) -> typer.Typer:
    app = typer.Typer(help="RoboDaddy: plan, dry-run, and dispatch model fine-tunes.")

    @app.command("usecases")
    def usecases():
        """Show use-case presets + their recommended recipe."""
        t = Table("key", "use case", "base", "method", "datasets")
        for k, p in PRESETS.items():
            t.add_row(k, p["label"], p["base"], p["method"], p["datasets"])
        console.print(t)

    @app.command("datasets")
    def datasets(
        request: str = typer.Argument("", help="what you want the model to do (free text)"),
        use_case: str = typer.Option("", "-u", "--use-case",
                                     help="restrict to a use-case preset (offensive_pentest, code, ...)"),
        limit: int = typer.Option(10, "--limit", help="max rows"),
    ):
        """Search public training datasets by relevance to your query.

        Type anything you want the model to be good at (e.g. "python coding",
        "blue team alert triage", "chatty assistant") and we pull the most
        relevant datasets from across all use-cases. Add --use-case to restrict
        to a single preset instead.
        """
        if use_case:
            # Explicit preset path: show the curated recommendation for that use case.
            rec = recommend_datasets(request, use_case=use_case, limit=limit)
            console.print(f"[green]use case:[/green] {rec['label']}  [dim]({rec['use_case']})[/dim]")
            console.print(f"[dim]recommended base: {rec['base_model']}   method: {rec['method']}[/dim]\n")
            _print_dataset_table(console, rec["datasets"])
            console.print(f"\n[dim]plan it: cyberspace robodaddy plan \"{use_case}\"[/dim]")
            return

        # Default: fuzzy search across ALL datasets by query.
        from .datasets import search_datasets
        results = search_datasets(request, limit=limit)
        if request:
            console.print(f"[green]search:[/green] \"{request}\"  "
                          f"[dim]({len(results)} relevant dataset(s))[/dim]\n")
        else:
            console.print(f"[green]all datasets[/green]  [dim](top {len(results)})[/dim]\n")
        _print_search_results(console, results)
        hint = request or "general"
        console.print(f"\n[dim]plan it: cyberspace robodaddy plan \"{hint}\"[/dim]")

    @app.command("gpus")
    def gpus():
        """Show GPU hardware + QLoRA/LoRA capacity."""
        t = Table("GPU", "VRAM", "QLoRA max", "Full-FT max", "$/hr (low-hi)", "class")
        for gid, s in GPUS.items():
            t.add_row(gid, f"{s['vram_gb']}GB", f"{s['qlora_max_b']}B",
                      f"{s['full_ft_max_b']}B",
                      f"${s['dph_low']:.2f}-${s['dph_high']:.2f}", s["class"])
        console.print(t)

    @app.command("providers")
    def providers():
        """Show GPU-rental marketplaces."""
        t = Table("provider", "API base", "live", "note")
        for k, p in PROVIDERS.items():
            t.add_row(k, p["api_base"] or "(none)", "yes" if p["live"] else "no", p["note"])
        console.print(t)
        console.print("\n[dim]Set keys: export VAST_API_KEY=...  "
                      "(get one at cloud.vast.ai/account/settings/)[/dim]")

    @app.command("instances")
    def instances(gpu: str = typer.Option("", "--gpu", "-g", help="e.g. RTX_4090"),
                  num_gpus: int = typer.Option(1, "--num-gpus", "-n"),
                  max_dph: float = typer.Option(0.0, "--max-dph", help="max $/hr"),
                  limit: int = typer.Option(12, "--limit")):
        """Search LIVE Vast.ai GPU offers (real prices; rent needs a key)."""
        from .vast import VastClient
        vc = VastClient()
        # Map our GPU ids to Vast's gpu_name strings.
        vast_name = {"RTX_4090": "RTX_4090", "RTX_3090": "RTX_3090", "A100_80": "A100_SXM4_80GB",
                     "A100_40": "A100_PCIE_40GB", "A6000": "RTX_A6000", "H100": "H100_SXM5_80GB",
                     "L40S": "L40", "H200": "H200"}.get(gpu.upper()) if gpu else None
        console.print(f"[dim]searching Vast.ai offers...[/dim]")
        try:
            offers = vc.search(gpu_name=vast_name, num_gpus=num_gpus,
                               max_dph=(max_dph or None), limit=limit)
        except Exception as e:
            console.print(f"[red]Vast.ai search failed:[/red] {e}\n"
                          "[dim]The public offer API may be rate-limited. Try again later.[/dim]")
            raise typer.Exit(1)
        if not offers:
            console.print("[yellow]no offers matched. Try without --gpu to see all.[/yellow]")
            return
        t = Table("#", "GPU", "x", "$/hr", "dlperf", "disk GB", "reliability", "location")
        for o in offers:
            t.add_row(str(o.id), o.gpu_name, str(o.num_gpus), f"${o.dph_total:.3f}",
                      f"{o.dlperf:.0f}", f"{o.disk_space:.0f}",
                      f"{o.reliability:.2f}", o.geolocation)
        console.print(t)
        console.print(f"\n[dim]Rent one with: cyberspace robodaddy train <use-case> "
                      f"--provider vastai --offer {offers[0].id}[/dim]")

    # --- interactive plan wizard -----------------------------------------
    @app.command("plan")
    def plan(prompt_text: str = typer.Argument("", help="what you want your AI to do")):
        """Interactive: pick use case, dataset, model, GPU, days -> cost estimate."""
        if not prompt_text:
            prompt_text = Prompt.ask("What do you want your AI to do?",
                default="offensive pen security")
        uc = resolve_use_case(prompt_text)
        preset = preset_for(uc)
        console.print(f"[green]matched use case:[/green] {preset['label']}  [dim]({uc})[/dim]")

        # base model
        console.print("\nBase models:")
        for k, bm in BASE_MODELS.items():
            mark = " <-- recommended" if k == preset["base"] else ""
            console.print(f"  {k:<16} {bm['billion']}B params  {bm['note']}{mark}")
        base = Prompt.ask("Base model", default=preset["base"])

        # dataset
        ds = recommend_datasets(prompt_text, use_case=uc)["datasets"]
        console.print("\nDataset recommendations:")
        for i, d in enumerate(ds):
            mark = " <-- recommended" if i == 0 else ""
            console.print(
                f"  [{i}] {d['name']}  [dim]({d['id']})[/dim]  {d['size']}  "
                f"{d.get('license', 'unknown')}  {d.get('access', 'unknown')}{mark}"
            )
        di = int(Prompt.ask("Dataset #", default="0", choices=[str(i) for i in range(len(ds))]))
        dataset_id = ds[di]["id"]

        # GPU (auto-recommend)
        bparams = BASE_MODELS[base]["billion"]
        recommended = best_value_gpu(bparams, preset["method"]) or "A100_40"
        compatible = gpus_for_model(bparams, preset["method"])
        console.print(f"\nCompatible GPUs: {', '.join(compatible) or 'none - model too big'}")
        gpu = Prompt.ask("GPU", default=recommended)

        days = int(Prompt.ask("How many days to train?", default="1"))
        num_gpus = int(Prompt.ask("Number of GPUs", default="1"))

        p = build_plan(uc, base_model=base, dataset_id=dataset_id, gpu=gpu,
                       days=days, num_gpus=num_gpus)
        console.print(Panel.fit(
            f"[bold]{p.name}[/bold]\n"
            f"base: {p.base_model} ({BASE_MODELS[p.base_model]['billion']}B)   "
            f"dataset: {p.dataset_id}\n"
            f"method: {p.method} on {p.num_gpus}x {p.gpu}   epochs: {p.epochs}\n"
            f"est. time: {p.hours}h   est. cost: ${p.cost_low:.2f}-${p.cost_high:.2f}\n"
            + ("\n".join("  " + n for n in p.notes)),
            title="training plan", border_style="cyan"))
        console.print(f"\n[dim]train it: cyberspace robodaddy train {uc} "
                      f"--base {base} --gpu {gpu} --days {days}[/dim]")

    # --- train -----------------------------------------------------------
    @app.command("train")
    def train(use_cases: list[str] = typer.Argument(..., help="one or more use-case keys or requests"),
              base: str = typer.Option("", "--base", "-b"),
              dataset: str = typer.Option("", "--dataset", "-d"),
              gpu: str = typer.Option("", "--gpu", "-g"),
              days: int = typer.Option(1, "--days"),
              num_gpus: int = typer.Option(1, "--num-gpus"),
              epochs: int = typer.Option(3, "--epochs"),
              provider: str = typer.Option("dry-run", "--provider", "-p",
                                          help="dry-run|vastai"),
              offer: Optional[list[int]] = typer.Option(
                  None, "--offer", help="Vast.ai offer id; repeat once per model for batches")):
        """Run one or more fine-tune jobs. Dry-run is simulated and concurrent."""
        if provider not in ("dry-run", "vastai"):
            console.print("[red]provider must be dry-run or vastai[/red]")
            raise typer.Exit(1)
        plans = [
            build_plan(use_case, base_model=(base or None), dataset_id=(dataset or None),
                       gpu=(gpu or None), days=days, num_gpus=num_gpus, epochs=epochs)
            for use_case in use_cases
        ]
        dry = provider == "dry-run"
        offer_ids = list(offer or [])
        if provider == "vastai":
            if len(offer_ids) != len(plans):
                console.print("[red]Vast.ai training needs one --offer value per model.[/red]\n"
                              "[dim]Find offers with: cyberspace robodaddy instances[/dim]")
                raise typer.Exit(1)
            total_mid = sum(p.cost_mid for p in plans)
            console.print(f"[yellow]WARNING: will rent {len(plans)} Vast.ai offer(s) "
                          f"(estimated mid cost ${total_mid:.2f}). Proceed?[/yellow]")
            if not Confirm.ask("Rent GPU(s) + train?", default=False):
                raise typer.Exit(0)

        def on_event(stage, msg):
            console.print(f"[dim]{stage:>8}[/dim]  {msg}")

        def on_batch(job, stage, msg):
            console.print(f"[dim]{job} {stage:>8}[/dim]  {msg}")

        if len(plans) == 1:
            from .train import run_training
            models = [run_training(plans[0], dry_run=dry,
                                   vast_offer_id=(offer_ids[0] if offer_ids else None),
                                   on_event=on_event)]
        else:
            console.print(f"[dim]starting {len(plans)} training jobs concurrently[/dim]")
            from .train import run_training_batch
            models = run_training_batch(plans, dry_run=dry, vast_offer_ids=offer_ids,
                                        on_event=on_batch)

        for m in models:
            console.print(Panel.fit(
                f"[green]model:[/green] {m.name}  status: {m.status}\n"
                f"end_loss: {m.stats.get('end_loss','n/a')}   "
                f"samples: {m.stats.get('samples_trained','n/a')}   "
                f"hours: {m.stats.get('hours','n/a')}\n"
                f"progress: {m.stats.get('progress_file','n/a')}\n"
                f"vast: {m.stats.get('vast_console_url','n/a')}",
                border_style="green" if m.status == "trained" else "yellow"))
            if m.status == "trained":
                console.print(f"[dim]serve it: cyberspace robodaddy serve {m.name}[/dim]")

    # --- jobs + models ---------------------------------------------------
    @app.command("jobs")
    def jobs():
        """List training jobs + their statistics."""
        models = list_models()
        if not models:
            console.print("[dim]no jobs yet. Run: cyberspace robodaddy plan[/dim]"); return
        t = Table("model", "status", "base", "end_loss", "samples", "hours", "$mid", "progress")
        for m in models:
            s = m.stats
            t.add_row(m.name, m.status, m.base_model,
                      str(s.get("end_loss", "-")), str(s.get("samples_trained", "-")),
                      str(s.get("hours", "-")), str(s.get("cost_mid", "-")),
                      str(s.get("progress_file", "-")))
        console.print(t)

    @app.command("models")
    def models():
        """List trained models in the registry."""
        ms = list_models()
        if not ms:
            console.print("[dim]no models yet.[/dim]"); return
        t = Table("name", "status", "base", "use_case", "endpoint")
        for m in ms:
            t.add_row(m.name, m.status, m.base_model, m.use_case, m.endpoint or "-")
        console.print(t)

    @app.command("serve")
    def serve(model_name: str = typer.Argument(...),
              target: str = typer.Option("ollama", "--target", "-t",
                                         help="ollama"),
              port: int = typer.Option(11435, "--port")):
        """Write a local Ollama Modelfile and API-key record."""
        from .serve import serve as do_serve
        def on_event(stage, msg):
            console.print(f"[dim]{stage:>8}[/dim]  {msg}")
        try:
            m, key = do_serve(model_name, target=target, port=port, on_event=on_event)
        except ValueError as e:
            console.print(f"[red]{e}[/red]"); raise typer.Exit(1)
        console.print(Panel.fit(
            f"[green]served:[/green] {m.name}\n"
            f"endpoint: {m.endpoint}\n"
            f"api key:  {key[:24]}...  [dim](full: robodaddy keys)[/dim]",
            border_style="green"))
        console.print(f"[dim]use it: cyberspace robodaddy use {m.name}[/dim]")

    @app.command("keys")
    def keys():
        """List/revoke API keys for served models."""
        ks = list_keys()
        if not ks:
            console.print("[dim]no keys issued yet. Serve a model first.[/dim]"); return
        t = Table("key (prefix)", "model", "endpoint", "created")
        for k in ks:
            t.add_row(k.key[:20] + "...", k.model_name, k.endpoint, k.created[:10])
        console.print(t)

    @app.command("use")
    def use(model_name: str = typer.Argument(...)):
        """Set a trained+served model as cyberbot's active LLM."""
        from .serve import use_as_cyberbot
        try:
            endpoint, api_key = use_as_cyberbot(model_name)
        except ValueError as e:
            console.print(f"[red]{e}[/red]"); raise typer.Exit(1)
        console.print(Panel.fit(
            f"[green]cyberbot now uses your trained model.[/green]\n"
            f"model: {model_name}\nendpoint: {endpoint}\napi_key: {api_key[:16]}...",
            border_style="green"))
        console.print("[dim]test it: cyberspace agent[/dim]")

    return app
