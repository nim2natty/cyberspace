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

from pathlib import Path
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
from .registry import list_keys, list_models, issue_key, revoke_key


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
    app = typer.Typer(help="RoboDaddy: guided data, GPU pricing, background training, serving, and keys.")

    @app.command("usecases")
    def usecases():
        """Show use-case presets + their recommended recipe."""
        t = Table("key", "use case", "base", "method", "datasets")
        for k, p in PRESETS.items():
            t.add_row(k, p["label"], p["base"], p["method"], p["datasets"])
        console.print(t)

    @app.command("build")
    def guided_build(
        use_case: str = typer.Argument("", help="short use case, e.g. coding assistant"),
        provider: str = typer.Option("dry-run", "--provider", "-p", help="dry-run|vastai"),
        offer: Optional[int] = typer.Option(None, "--offer", help="Vast.ai offer ID for paid training"),
        no_ai: bool = typer.Option(False, "--no-ai", help="rank data without the configured provider"),
    ):
        """Guided use case → intent → datasets → GPU/price → background training."""
        if provider not in ("dry-run", "vastai"):
            console.print("[red]provider must be dry-run or vastai[/red]"); raise typer.Exit(2)
        if not use_case:
            use_case = Prompt.ask("What kind of AI do you want to build?", default="coding assistant")
        intent = Prompt.ask("What should this AI do, for whom, and what matters most?",
                            default=use_case)
        uc = resolve_use_case(use_case + " " + intent)
        preset = preset_for(uc)
        console.print(f"\n[cyan]Searching live Hugging Face datasets for:[/cyan] {intent}")
        from .discovery import discover_datasets, expand_search_terms, rank_datasets
        terms = [intent] if no_ai else expand_search_terms(intent)
        candidates = discover_datasets(intent, limit=15, search_terms=terms)
        ranked = candidates[:8] if no_ai else rank_datasets(intent, candidates, limit=8)
        if not ranked:
            console.print("[red]No suitable datasets were found.[/red]"); raise typer.Exit(1)
        _print_search_results(console, ranked)
        choices = [str(i) for i in range(1, len(ranked) + 1)]
        selected = ranked[int(Prompt.ask("Dataset #", choices=choices, default="1")) - 1]

        base = preset["base"]
        if Confirm.ask(f"Use recommended base model {base}?", default=True) is False:
            base = Prompt.ask("Base model", choices=list(BASE_MODELS), default=base)
        days = int(Prompt.ask("Training budget in days", default="1"))
        num_gpus = int(Prompt.ask("Number of GPUs", default="1"))
        bparams = BASE_MODELS[base]["billion"]
        gpu = best_value_gpu(bparams, preset["method"]) or "A100_40"
        plan = build_plan(uc, base_model=base, dataset_id=selected["id"],
                          dataset_revision=selected.get("revision", "main"), gpu=gpu,
                          days=days, num_gpus=num_gpus)
        plan.notes.append(f"intent: {intent}")
        plan.notes.append(f"dataset source={selected.get('source', 'unknown')} "
                          f"revision={selected.get('revision', 'main')}")
        plan.notes.append(f"dataset access={selected.get('access', 'unknown')}")
        console.print(Panel.fit(
            f"[bold]{plan.name}[/bold]\nintent: {intent}\nbase: {base}   "
            f"dataset: {selected['id']}\nlicense/access: {selected.get('license')} / "
            f"{selected.get('access')}\nGPU: {num_gpus}x {gpu}   estimated time: {plan.hours}h\n"
            f"estimated price: ${plan.cost_low:.2f}-${plan.cost_high:.2f} "
            f"(mid ${plan.cost_mid:.2f})", title="RoboDaddy recommendation", border_style="cyan"))
        if provider == "vastai" and offer is None:
            from .vast import VAST_GPU_NAMES, VastClient
            console.print(f"\n[cyan]Finding live {gpu} offers on Vast.ai...[/cyan]")
            try:
                offers = VastClient().search(gpu_name=VAST_GPU_NAMES.get(gpu, gpu),
                                             num_gpus=num_gpus, limit=5)
            except Exception as exc:
                console.print(f"[red]Could not load live offers: {exc}[/red]"); raise typer.Exit(1)
            if not offers:
                console.print("[red]No compatible rentable offers are currently available.[/red]")
                raise typer.Exit(1)
            table = Table("#", "GPU", "$/hr", "projected total", "reliability", "location")
            for index, candidate in enumerate(offers, 1):
                table.add_row(str(index), candidate.gpu_name, f"${candidate.dph_total:.3f}",
                              f"${candidate.dph_total * plan.hours:.2f}",
                              f"{candidate.reliability:.2f}", candidate.geolocation)
            console.print(table)
            choice = int(Prompt.ask("Offer #", choices=[str(i) for i in range(1, len(offers) + 1)],
                                    default="1")) - 1
            chosen_offer = offers[choice]
            offer = chosen_offer.id
            plan.cost_low = plan.cost_mid = plan.cost_high = round(chosen_offer.dph_total * plan.hours, 2)
            console.print(f"[yellow]Selected offer #{offer}: ${chosen_offer.dph_total:.3f}/hr, "
                          f"projected ${plan.cost_mid:.2f} total.[/yellow]")
        question = "Rent the GPU and launch paid training?" if provider == "vastai" else "Launch this training dry-run?"
        if not Confirm.ask(question, default=False):
            console.print("[dim]Plan reviewed; nothing was launched.[/dim]"); return
        from .jobs import launch_background
        model = launch_background(plan, dry_run=(provider == "dry-run"), vast_offer_id=offer)
        console.print(Panel.fit(
            f"[green]launched in background:[/green] {model.name}\nstatus: {model.status}\n"
            "You may close this terminal; the worker runs independently.\n"
            "Check progress: cyberspace robodaddy dashboard",
            border_style="green"))

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
        console.print("\n[dim]Save a key securely: cyberspace robodaddy provider-key vastai "
                      "(get one at cloud.vast.ai/account/settings/)[/dim]")

    @app.command("instances")
    def instances(gpu: str = typer.Option("", "--gpu", "-g", help="e.g. RTX_4090"),
                  num_gpus: int = typer.Option(1, "--num-gpus", "-n"),
                  max_dph: float = typer.Option(0.0, "--max-dph", help="max $/hr"),
                  limit: int = typer.Option(12, "--limit")):
        """Search LIVE Vast.ai GPU offers (real prices; rent needs a key)."""
        from .vast import VAST_GPU_NAMES, VastClient
        vc = VastClient()
        vast_name = VAST_GPU_NAMES.get(gpu, gpu)
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
              foreground: bool = typer.Option(False, "--foreground",
                                                help="keep this terminal attached"),
              offer: Optional[list[int]] = typer.Option(
                  None, "--offer", help="Vast.ai offer id; repeat once per model for batches")):
        """Launch detached fine-tune jobs; use --foreground to keep the terminal attached."""
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

        if not foreground:
            from .jobs import launch_background
            models = [launch_background(plan, dry_run=dry,
                        vast_offer_id=(offer_ids[index] if offer_ids else None))
                      for index, plan in enumerate(plans)]
            for model in models:
                console.print(f"[green]background job queued:[/green] {model.name} "
                              f"(PID {model.stats.get('pid', 'starting')})")
            console.print("[bold]You may close this terminal.[/bold] Training continues independently.\n"
                          "Check all jobs: cyberspace robodaddy dashboard")
            return
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
        from .jobs import refresh_jobs
        models = refresh_jobs()
        if not models:
            console.print("[dim]no jobs yet. Run: cyberspace robodaddy plan[/dim]"); return
        t = Table("model", "status", "base", "end_loss", "samples", "hours", "$mid", "progress")
        for m in models:
            s = m.stats
            display_status = "done" if m.status in ("trained", "served") else m.status
            t.add_row(m.name, display_status, m.base_model,
                      str(s.get("end_loss", "-")), str(s.get("samples_trained", "-")),
                      str(s.get("hours", "-")), str(s.get("cost_mid", "-")),
                      str(s.get("progress_file", "-")))
        console.print(t)

    @app.command("dashboard")
    def dashboard(
        watch: bool = typer.Option(False, "--watch", "-w", help="refresh until Ctrl-C"),
        interval: float = typer.Option(2.0, "--interval", min=0.5),
    ):
        """Show concurrent training progress; --watch refreshes live."""
        import time
        from .jobs import refresh_jobs

        def render() -> None:
            models = refresh_jobs()
            t = Table("model", "status", "provider", "PID/instance", "loss", "cost", "progress/log")
            for model in models:
                stats = model.stats
                identity = stats.get("vast_instance_id") or stats.get("pid") or "-"
                progress = stats.get("progress_file") or stats.get("log_file") or "-"
                display_status = "done" if model.status in ("trained", "served") else model.status
                t.add_row(model.name, display_status, str(stats.get("provider", "-")), str(identity),
                          str(stats.get("end_loss", "-")),
                          str(stats.get("cost_mid", stats.get("estimated_cost", "-"))), str(progress))
            console.print(t if models else "[dim]No jobs. Run: cyberspace robodaddy build[/dim]")
            done = sum(model.status in ("trained", "served") for model in models)
            failed = sum(model.status == "failed" for model in models)
            active = sum(model.status in ("queued", "training") for model in models)
            console.print(f"[dim]{done} done · {active} active · {failed} failed[/dim]")

        if not watch:
            render(); return
        try:
            while True:
                console.clear()
                render()
                time.sleep(interval)
        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard closed; background jobs continue.[/dim]")

    @app.command("worker", hidden=True)
    def worker(plan_file: Path = typer.Argument(..., exists=True, dir_okay=False),
               dry_run: bool = typer.Option(False, "--dry-run"),
               offer: Optional[int] = typer.Option(None, "--offer")):
        """Internal detached worker entry point."""
        from .jobs import run_worker
        raise typer.Exit(run_worker(plan_file, dry_run=dry_run, vast_offer_id=offer))

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
            f"api key:  {key[:24]}...  [dim](retrieve later: robodaddy keys show {key[:12]})[/dim]",
            border_style="green"))
        console.print(f"[dim]use it: cyberspace robodaddy use {m.name}[/dim]")

    keys_app = typer.Typer(help="Create, show, list, and revoke served-model API keys.")
    app.add_typer(keys_app, name="keys")

    @keys_app.command("list")
    def keys_list():
        """List key prefixes and metadata (never prints secret values)."""
        ks = list_keys()
        if not ks:
            console.print("[dim]no keys issued yet. Serve a model first.[/dim]"); return
        t = Table("prefix", "id", "model", "endpoint", "created")
        for k in ks:
            t.add_row(k.prefix + "...", k.key_id[:10], k.model_name, k.endpoint, k.created[:10])
        console.print(t)

    @keys_app.command("new")
    def keys_new(model_name: str = typer.Argument(...)):
        """Create another API key for a served model; secret is stored in the OS keyring."""
        from .registry import get_model
        model = get_model(model_name)
        if not model or model.status != "served" or not model.endpoint:
            console.print("[red]Model must be served before a key can be issued.[/red]")
            raise typer.Exit(1)
        key = issue_key(model_name, model.endpoint, note="issued from RoboDaddy CLI")
        console.print(Panel.fit(
            f"[green]new key created[/green]\n{key.key}\n\n"
            "Stored in your native credential store. Copy it now; `keys list` shows only prefixes.",
            border_style="green"))

    @keys_app.command("show")
    def keys_show(prefix: str = typer.Argument(...)):
        """Explicitly retrieve one key from the native credential store."""
        matches = [key for key in list_keys() if key.prefix.startswith(prefix)
                   or key.key_id.startswith(prefix)]
        if len(matches) != 1:
            console.print("[red]Key prefix is missing or ambiguous.[/red]"); raise typer.Exit(1)
        secret = matches[0].key
        if not secret:
            console.print("[red]Secret is unavailable in this user's credential store.[/red]")
            raise typer.Exit(1)
        console.print(secret)

    @keys_app.command("revoke")
    def keys_revoke(prefix: str = typer.Argument(...)):
        """Revoke keys matching an ID/prefix and remove their credential-store secrets."""
        count = revoke_key(prefix)
        console.print(f"[green]revoked {count} key(s)[/green]" if count else "[yellow]no matching key[/yellow]")

    @app.command("provider-key")
    def provider_key(provider: str = typer.Argument("vastai")):
        """Securely save a GPU-provider key (currently Vast.ai)."""
        if provider != "vastai":
            console.print("[red]Only Vast.ai lifecycle automation is implemented.[/red]"); raise typer.Exit(2)
        from ...credentials import set_secret
        value = Prompt.ask("Vast.ai API key", password=True)
        set_secret("robodaddy:vast-api-key", value)
        console.print("[green]Vast.ai key stored in the native credential store.[/green]")

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

    app.command("connect")(use)

    return app
