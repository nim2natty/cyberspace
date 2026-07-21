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

from .datasets import recommend_datasets, register_dataset, custom_datasets
from .gpus import (GPUS, best_value_gpu, gpus_for_model, compare_gpus,
                   pick_best_gpu)
from .parameters import (PARAMETER_PROFILES, PARAMETER_GUIDE, ModelParameters,
                         build_system_prompt, guide_text, load_parameters,
                         profile as parameter_profile, save_parameters,
                         merge_overrides)
from .plan import build_plan, _dataset_size_hint
from .presets import BASE_MODELS, PRESETS, preset_for, resolve_use_case
from .recommend import (recommend_parameters, enhance_parameters,
                        heuristic_recommend)
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


def _print_parameters(console: Console, params) -> None:
    """Pretty-print a ModelParameters profile so the user can see what's set."""
    console.print(f"[bold]{params.label}[/bold]")
    console.print(f"base_model: {params.base_model or '(preset default)'}   method: {params.method or '(preset default)'}")
    hp = {k: getattr(params, k) for k in ("epochs", "learning_rate", "batch_size",
           "max_seq_len", "lora_r", "weight_decay", "warmup_ratio",
           "gradient_accumulation_steps", "lr_scheduler", "optimizer", "seed")}
    hp = {k: v for k, v in hp.items() if v is not None}
    console.print(f"hyperparameters: {hp}")
    if params.dataset_ids:
        console.print(f"datasets: {', '.join(params.dataset_ids)}")
    f = params.focus
    enabled = [k for k in ("offensive_reasoning", "adversary_modeling", "attack_path_reasoning",
                "multi_turn_scenarios", "sensitive_content", "foothold_analysis",
                "operator_tasks", "real_attack_vectors") if getattr(f, k)]
    console.print(f"focus: {', '.join(enabled) or '(none)'}")
    g = params.guardrails
    console.print(f"guardrails: level={g.guardrail_level}  "
                  f"scope={g.authorization_scope}  authorized={g.authorization_confirmed}")
    if g.allowed_categories:
        console.print(f"  allowed: {', '.join(g.allowed_categories)}")
    if g.denied_categories:
        console.print(f"  denied: {', '.join(g.denied_categories)}")
    if params.system_prompt:
        console.print(f"system prompt override: {len(params.system_prompt)} chars")


def _coerce_value(params, key: str, value: str):
    """Coerce a CLI string value to the right type for a parameter key."""
    if not value:
        return value
    if "." in key:
        section, field_name = key.split(".", 1)
        container = getattr(params, section, None)
        if container is not None and field_name in container.__dict__:
            return _coerce_known(getattr(container, field_name), value)
        return value
    if hasattr(params, key):
        return _coerce_known(getattr(params, key), value)
    return value


def _coerce_known(current, value: str):
    if isinstance(current, bool):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    if isinstance(current, int):
        try:
            return int(value)
        except ValueError:
            return value
    if isinstance(current, float):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _launch_plan(console: Console, plan, *, provider: str, offer: Optional[int]) -> None:
    """Show a plan summary and launch a background training job (dry-run default)."""
    console.print(Panel.fit(
        f"[bold]{plan.name}[/bold]\n"
        f"base: {plan.base_model}   dataset: {plan.dataset_id}\n"
        f"method: {plan.method} on {plan.num_gpus}x {plan.gpu}   epochs: {plan.epochs}\n"
        f"est. time: {plan.hours}h   est. cost: ${plan.cost_low:.2f}-${plan.cost_high:.2f}\n"
        + ("\n".join("  " + n for n in plan.notes)),
        title="RoboDaddy plan", border_style="cyan"))
    question = ("Rent the GPU and launch paid training?" if provider == "vastai"
                else "Launch this training dry-run?")
    if not Confirm.ask(question, default=False):
        console.print("[dim]Plan reviewed; nothing was launched.[/dim]")
        return
    from .jobs import launch_background
    model = launch_background(plan, dry_run=(provider == "dry-run"), vast_offer_id=offer)
    console.print(Panel.fit(
        f"[green]launched in background:[/green] {model.name}\nstatus: {model.status}\n"
        "You may close this terminal; the worker runs independently.\n"
        "Check progress: cyberspace robodaddy dashboard",
        border_style="green"))


def _gpu_and_launch(console, *, params, use_case, intent, provider, offer):
    """Show a GPU time/cost table, auto-pick the best, and launch training.

    Used by the guided `start` flow. Lets the user choose a GPU row, set a custom
    training time (days), or accept the program's best pick.
    """
    from .gpus import compare_gpus, pick_best_gpu
    from .presets import BASE_MODELS
    base = params.base_model or "qwen2.5-7b"
    if base not in BASE_MODELS:
        base = "qwen2.5-7b"
    b = BASE_MODELS[base]["billion"]
    method = params.method or "qlora"
    ds_id = params.dataset_ids[0] if params.dataset_ids else "tatsu-lab/alpaca"
    samples = min(200000, max(5000, _dataset_size_hint(ds_id)))
    epochs = params.epochs or 3
    seq_len = params.max_seq_len or 2048
    rows = compare_gpus(b, method, samples, epochs, seq_len, num_gpus=1)
    if not rows:
        console.print("[red]No compatible GPU for this configuration.[/red]")
        return
    best = pick_best_gpu(b, method, samples, epochs, seq_len, num_gpus=1)

    console.print("\n[bold]Step 7:[/bold] GPUs available (training time + cost).")
    t = Table("#", "GPU", "VRAM", "hours", "$ low", "$ mid", "$ high", "class", "")
    for i, r in enumerate(rows, 1):
        star = "[green]<-- best[/green]" if r["gpu"] == best else ""
        t.add_row(str(i), r["gpu"], f"{r['vram_gb']}GB", f"{r['hours']}",
                  f"${r['cost_low']:.2f}", f"${r['cost_mid']:.2f}",
                  f"${r['cost_high']:.2f}", r["class"], star)
    console.print(t)
    console.print(f"[green]Recommended (best value):[/green] {best}")
    console.print("[dim]Pick a row #, set a custom training time (days), or accept the best.[/dim]")

    choice = Prompt.ask("Pick a GPU (row #), 'best', or custom days like 'd3'",
                        default="best").strip().lower()
    chosen_gpu = best
    days = 1
    if choice in ("best", "b", ""):
        chosen_gpu = best
    elif choice.startswith("d") and choice[1:].isdigit():
        days = max(1, int(choice[1:]))
        chosen_gpu = best
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(rows):
            chosen_gpu = rows[idx]["gpu"]
        else:
            console.print("[red]Invalid row.[/red]"); return
    else:
        console.print("[red]Invalid choice.[/red]"); return

    plan = build_plan(use_case, parameters=params, days=days, gpu=chosen_gpu,
                      dataset_id=ds_id)
    plan.notes.append(f"intent: {intent}")
    _launch_plan(console, plan, provider=provider, offer=offer)


def _run_start_remaining(console, *, params, kind, flavor, intent, latest,
                         provider, offer):
    """Steps 4-7 of the guided start flow (AI recommend -> prompt -> enhance -> GPU)."""
    from .parameters import build_system_prompt
    from .recommend import recommend_parameters, enhance_parameters
    from .presets import BASE_MODELS, resolve_use_case
    from ...agent.config import is_configured

    # STEP 4: AI scans the config and recommends the best parameters.
    console.print("\n[bold]Step 4:[/bold] recommending the best parameters...")
    if is_configured():
        console.print("[cyan]AI provider scanning your option/config...[/cyan]")
    else:
        console.print("[yellow]No AI provider configured - using built-in heuristics.[/yellow]\n"
                      "[dim](configure one with `cyberspace setup` for AI-tuned params)[/dim]")
    b = BASE_MODELS.get(params.base_model, {}).get("billion", 8)
    params = recommend_parameters(intent, params, latest, model_size_b=b)
    save_parameters(params)
    _print_parameters(console, params)

    # STEP 5: system prompt input (structure the AI).
    console.print("\n[bold]Step 5:[/bold] set the system prompt that structures your AI.")
    auto_prompt = build_system_prompt(params)
    console.print("[dim]Auto-composed system prompt (from your focus + guardrails):[/dim]")
    console.print(Panel(auto_prompt[:600] + ("..." if len(auto_prompt) > 600 else ""),
                        border_style="dim"))
    if Confirm.ask("Edit / write your own system prompt?", default=False):
        entered = Prompt.ask("Paste your system prompt (one line; blank keeps the auto prompt)")
        if entered.strip():
            params.system_prompt = entered.strip()
    else:
        params.system_prompt = ""  # use auto-composed at build time

    # STEP 6: AI pulls similar/effective params to enhance accuracy.
    console.print("\n[bold]Step 6:[/bold] enhancing parameters from your prompt...")
    final_prompt = params.system_prompt or auto_prompt
    enhanced, changes = enhance_parameters(params, final_prompt)
    params = enhanced
    save_parameters(params)
    for c in changes:
        console.print(f"  [green]*[/green] {c}")
    _print_parameters(console, params)

    # STEP 7: GPU table + auto-pick / custom time.
    uc = ("cyber_redteam" if kind == "cyber" and flavor == "redteam"
          else "defensive_pentest" if kind == "cyber" else resolve_use_case(intent))
    _gpu_and_launch(console, params=params, use_case=uc, intent=intent,
                    provider=provider, offer=offer)


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

    # --- guided start: refresh datasets -> intent -> AI recommend -> prompt -> GPU ----
    @app.command("start")
    def start(
        skip_refresh: bool = typer.Option(False, "--skip-refresh", help="skip the latest-dataset refresh"),
        provider: str = typer.Option("dry-run", "--provider", "-p", help="dry-run|vastai"),
        offer: Optional[int] = typer.Option(None, "--offer"),
    ):
        """Guided, AI-assisted build: the recommended way to design your model."""
        from .refresh import refresh_datasets_cache, latest_datasets, cache_info
        from .parameters import CyberFocus

        console.print(Panel.fit(
            "[bold magenta]RoboDaddy guided start[/bold magenta]\n"
            "Design your own open source model - step by step, AI-assisted.",
            border_style="magenta"))

        # STEP 1: refresh the latest datasets so the user can view current data.
        console.print("\n[bold]Step 1:[/bold] refreshing the most recent Hugging Face datasets...")
        info = cache_info()
        if info:
            console.print(f"[dim]last refresh: {info.get('refreshed','?')[:19]} "
                          f"({info.get('count',0)} cached)[/dim]")
        if not skip_refresh:
            def on_event(stage, msg):
                console.print(f"[dim]{stage:>8}[/dim]  {msg}")
            cached = refresh_datasets_cache(on_event=on_event)
            console.print(f"[green]Cached {len(cached)} of the most recent datasets.[/green] "
                          "[dim](view anytime: cyberspace robodaddy latest)[/dim]")
        else:
            console.print("[dim]skipped refresh.[/dim]")

        # STEP 2: state the intention with friendly options.
        console.print("\n[bold]Step 2:[/bold] what do you want to build?")
        kind = Prompt.ask("Choose a bot type", choices=["cyber", "custom"], default="cyber")
        flavor = "redteam"
        if kind == "cyber":
            flavor = Prompt.ask("Cyber flavor", choices=["redteam", "defensive"], default="redteam")
            params = parameter_profile("cyber_redteam" if flavor == "redteam" else "cyber_defensive")
        else:
            params = parameter_profile("custom_blank")
            console.print("\n[cyan]Integrate cyber capabilities?[/cyan] (toggle each on/off)")
            focus = params.focus
            toggles = [
                ("offensive_reasoning", focus.offensive_reasoning),
                ("adversary_modeling", focus.adversary_modeling),
                ("attack_path_reasoning", focus.attack_path_reasoning),
                ("multi_turn_scenarios", focus.multi_turn_scenarios),
                ("sensitive_content", focus.sensitive_content),
                ("foothold_analysis", focus.foothold_analysis),
                ("operator_tasks", focus.operator_tasks),
                ("real_attack_vectors", focus.real_attack_vectors),
            ]
            chosen = [n for n, dv in toggles if Confirm.ask(f"  enable {n}?", default=dv)]
            params.focus = CyberFocus(**{n: (n in chosen) for n, _ in toggles})
        intent = Prompt.ask("Describe what your robot should do (free text)",
                            default=("authorized red-team adversary emulation"
                                     if kind == "cyber" else "a helpful assistant"))

        # STEP 3: pick dataset(s) from the latest cache (+ live + custom).
        console.print("\n[bold]Step 3:[/bold] pick your training data.")
        latest = latest_datasets()
        if latest:
            console.print(f"[green]Latest cached datasets (showing top {min(10, len(latest))}):[/green]")
            shown = latest[:10]
            _print_search_results(console, shown)
            if Confirm.ask("Use one of the latest datasets above?", default=True):
                choices = [str(i) for i in range(1, len(shown) + 1)]
                idx = int(Prompt.ask("Dataset #", choices=choices, default="1")) - 1
                params.dataset_ids = [shown[idx]["id"]]
            else:
                params.dataset_ids = [Prompt.ask("Enter any HF dataset repo id (owner/name)",
                                                 default="trendmicro-ailab/Primus-Instruct")]
        else:
            params.dataset_ids = [Prompt.ask("Enter any HF dataset repo id (owner/name)",
                                             default="trendmicro-ailab/Primus-Instruct")]

        _run_start_remaining(console, params=params, kind=kind, flavor=flavor,
                              intent=intent, latest=latest, provider=provider, offer=offer)

    @app.command("latest")
    def latest_cmd(limit: int = typer.Option(15, "--limit")):
        """View the most recent Hugging Face datasets cached by the last refresh."""
        from .refresh import latest_datasets, cache_info, refresh_datasets_cache
        info = cache_info()
        datasets = latest_datasets(limit=limit)
        if not datasets and Confirm.ask("No cached datasets yet. Refresh now?", default=True):
            datasets = refresh_datasets_cache()
        if datasets:
            console.print(f"[green]Latest datasets[/green] "
                          f"[dim](refreshed {info.get('refreshed','?')[:19]})[/dim]")
            _print_search_results(console, datasets[:limit])
        else:
            console.print("[dim]still none - check your network and try again.[/dim]")

    # --- design your own model (parameters + cyber/custom bots) ------------
    @app.command("parameters")
    def parameters(
        action: str = typer.Argument("show", help="show | guide | profiles | set | reset"),
        key: str = typer.Option("", "--key", "-k", help="parameter name, e.g. epochs or guardrails.guardrail_level"),
        value: str = typer.Option("", "--value", "-v", help="value for the parameter (set action)"),
        profile_name: str = typer.Option("", "--profile", help="start from cyber_redteam | cyber_defensive | custom_blank"),
    ):
        """View, set, or reset the full set of model-design parameters.

        RoboDaddy does not limit what you can configure: training hyperparameters,
        the cyber capability focus, and the guardrails applied before use are all
        yours to set. `parameters guide` for help, `parameters set` to change any
        value, and the chosen values attune every training run.
        """
        if action == "guide":
            console.print(guide_text()); return
        if action == "profiles":
            for name, mp in PARAMETER_PROFILES.items():
                console.print(f"  [bold]{name}[/bold] - {mp.label}")
            console.print("\n[dim]cyberspace robodaddy parameters set --profile <name>[/dim]")
            return
        if action == "reset":
            from .parameters import PARAMS_FILE
            try:
                PARAMS_FILE.unlink()
            except OSError:
                pass
            console.print("[green]parameter profile cleared. Defaults/presets will be used.[/green]")
            return
        if action == "set":
            current = parameter_profile(profile_name) if profile_name else (load_parameters() or parameter_profile("custom_blank"))
            if key:
                coerced = _coerce_value(current, key, value)
                from .parameters import merge_overrides
                current = merge_overrides(current, **{key: coerced})
            path = save_parameters(current)
            console.print(f"[green]saved parameter profile:[/green] {path}")
            _print_parameters(console, current)
            return
        current = load_parameters()
        if current is None:
            console.print("[dim]no saved parameter profile yet. Defaults are used.[/dim]")
            console.print("[dim]Start: cyberspace robodaddy parameters set --profile cyber_redteam[/dim]")
            console.print("[dim]Help:  cyberspace robodaddy parameters guide[/dim]")
            return
        _print_parameters(console, current)

    @app.command("cyber")
    def cyber(
        flavor: str = typer.Argument("redteam", help="redteam | defensive"),
        use_case: str = typer.Option("", "--use-case", "-u", help="extra intent text"),
        dataset: str = typer.Option("", "--dataset", "-d", help="Hugging Face dataset repo id to train on"),
        days: int = typer.Option(1, "--days"),
        provider: str = typer.Option("dry-run", "--provider", "-p", help="dry-run|vastai"),
        offer: Optional[int] = typer.Option(None, "--offer"),
        interactive: bool = typer.Option(True, "--interactive/--no-interactive"),
    ):
        """Build a CYBER BOT for red-team / adversary emulation or defense.

        Attunes training to full offensive reasoning, realistic adversary
        modeling, and attack-path reasoning (analyze footholds, explore
        exploitability, chain findings, reason through full attack paths) using
        operator-inspired, multi-turn scenarios - while YOU set the guardrails
        applied before the model is used. Produces your own open source model.
        """
        prof_name = "cyber_redteam" if flavor.startswith("red") else "cyber_defensive"
        params = parameter_profile(prof_name)
        console.print(Panel.fit(
            f"[bold]{params.label}[/bold]\n"
            "Full attack-path reasoning, adversary modeling, and operator-inspired "
            "multi-turn scenarios - for authorized use, with guardrails you set.",
            title="RoboDaddy Cyber Bot", border_style="magenta"))
        if interactive:
            scope = Prompt.ask("Authorized scope this model may operate in",
                               default=params.guardrails.authorization_scope)
            level = Prompt.ask("Guardrail level",
                               choices=["authorized-lab", "red-team-engagement",
                                        "research-only", "unrestricted-with-disclosure"],
                               default=params.guardrails.guardrail_level)
            authorized = Confirm.ask("Confirm you are authorized to operate within this "
                                     "scope (written permission / owned lab / engagement)?",
                                     default=False)
            from .parameters import merge_overrides
            params = merge_overrides(params, **{
                "guardrails.authorization_scope": scope,
                "guardrails.guardrail_level": level,
                "guardrails.authorization_confirmed": authorized,
            })
            if dataset:
                params.dataset_ids = [dataset]
            elif not params.dataset_ids:
                intent = use_case or "cyber red team adversary emulation datasets"
                console.print(f"\n[cyan]Searching live Hugging Face datasets for:[/cyan] {intent}")
                from .discovery import discover_datasets, rank_datasets
                candidates = discover_datasets(intent, limit=15)
                ranked = rank_datasets(intent, candidates, limit=8) if candidates else []
                if ranked:
                    _print_search_results(console, ranked)
                    choices = [str(i) for i in range(1, len(ranked) + 1)]
                    sel = ranked[int(Prompt.ask("Dataset #", choices=choices, default="1")) - 1]
                    params.dataset_ids = [sel["id"]]
                else:
                    custom_ds = Prompt.ask("Enter any Hugging Face dataset repo id (owner/name)",
                                           default="trendmicro-ailab/Primus-Instruct")
                    params.dataset_ids = [custom_ds]
            if Confirm.ask("Tune hyperparameters (epochs, lr, seq_len, lora_r)?", default=False):
                params.epochs = int(Prompt.ask("epochs", default=str(params.epochs or 4)))
                params.learning_rate = float(Prompt.ask("learning_rate", default=str(params.learning_rate or 2e-4)))
                params.max_seq_len = int(Prompt.ask("max_seq_len", default=str(params.max_seq_len or 4096)))
                params.lora_r = int(Prompt.ask("lora_r", default=str(params.lora_r or 32)))
            params.base_model = Prompt.ask("Base model", choices=list(BASE_MODELS),
                                           default=params.base_model or "llama3.1-8b")
        elif dataset:
            params.dataset_ids = [dataset]
        save_parameters(params)
        uc = "cyber_redteam" if prof_name == "cyber_redteam" else "defensive_pentest"
        plan = build_plan(use_case or uc, parameters=params, days=days,
                          dataset_id=(params.dataset_ids[0] if params.dataset_ids else None))
        plan.notes.append(f"cyber flavor: {prof_name}")
        _launch_plan(console, plan, provider=provider, offer=offer)

    @app.command("custom")
    def custom(
        use_case: str = typer.Argument("general", help="free-text use case or preset key"),
        dataset: str = typer.Option("", "--dataset", "-d", help="Hugging Face dataset repo id"),
        base: str = typer.Option("", "--base", "-b"),
        days: int = typer.Option(1, "--days"),
        provider: str = typer.Option("dry-run", "--provider", "-p", help="dry-run|vastai"),
        offer: Optional[int] = typer.Option(None, "--offer"),
        interactive: bool = typer.Option(True, "--interactive/--no-interactive"),
    ):
        """Build a CUSTOM BOT with fully user-defined parameters - no limits."""
        params = load_parameters() or parameter_profile("custom_blank")
        if interactive:
            console.print("[cyan]Custom bot builder[/cyan] - set any parameters you like.")
            console.print("[dim](run `cyberspace robodaddy parameters guide` for the full list)[/dim]\n")
            params.base_model = Prompt.ask("Base model", choices=list(BASE_MODELS),
                                           default=params.base_model or "qwen2.5-7b")
            params.method = Prompt.ask("Method", choices=["qlora", "lora", "full"],
                                       default=params.method or "qlora")
            params.epochs = int(Prompt.ask("epochs", default=str(params.epochs or 3)))
            params.learning_rate = float(Prompt.ask("learning_rate", default=str(params.learning_rate or 2e-4)))
            params.batch_size = int(Prompt.ask("batch_size", default=str(params.batch_size or 4)))
            params.max_seq_len = int(Prompt.ask("max_seq_len", default=str(params.max_seq_len or 2048)))
            params.lora_r = int(Prompt.ask("lora_r", default=str(params.lora_r or 16)))
            ds_input = dataset or Prompt.ask("Hugging Face dataset repo id (owner/name) - pick anything",
                                             default="tatsu-lab/alpaca")
            params.dataset_ids = [ds_input]
            params.system_prompt = Prompt.ask("Custom system prompt (blank = auto-compose)",
                                              default=params.system_prompt)
        else:
            if dataset:
                params.dataset_ids = [dataset]
            if base:
                params.base_model = base
        save_parameters(params)
        plan = build_plan(use_case, parameters=params, days=days,
                          dataset_id=(params.dataset_ids[0] if params.dataset_ids else None))
        _launch_plan(console, plan, provider=provider, offer=offer)

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
