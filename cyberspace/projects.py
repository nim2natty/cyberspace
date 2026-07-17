"""cyberspace projects - named workspaces that save every prompt.

A project is a named folder under ~/.cyberspace/projects/<name>/ that collects
every prompt you send to the AI while working on a specific task. This lets you
keep separate histories for separate engagements — e.g. one folder for
"surveillance in chicago", another for "home lab pentest".

Structure:
  ~/.cyberspace/projects/
    surveillance-in-chicago/
      project.json        # name, created, tags, description
      prompts.jsonl       # every prompt + the AI's response, timestamped
    home-lab-pentest/
      ...

When a project is "active", the agent and swarm auto-append every prompt to it.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import HOME, ensure_dirs

PROJECTS_DIR = HOME / "projects"
ACTIVE_FILE = HOME / "active_project"


def _project_dir(name: str) -> Path:
    return PROJECTS_DIR / name


def create(name: str, description: str = "", tags: list[str] = None) -> Path:
    """Create a new project folder. Returns the path."""
    ensure_dirs()
    name = _sanitize(name)
    pdir = _project_dir(name)
    pdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "name": name,
        "created": datetime.now().isoformat(),
        "description": description,
        "tags": tags or [],
    }
    (pdir / "project.json").write_text(json.dumps(meta, indent=2))
    if not (pdir / "prompts.jsonl").exists():
        (pdir / "prompts.jsonl").write_text("")
    # auto-activate the new project
    set_active(name)
    return pdir


def list_projects() -> list[dict]:
    """Return all projects with metadata + prompt count."""
    ensure_dirs()
    out = []
    if not PROJECTS_DIR.exists():
        return out
    for pdir in sorted(PROJECTS_DIR.iterdir()):
        if not pdir.is_dir():
            continue
        meta_file = pdir / "project.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except Exception:
                meta = {"name": pdir.name}
        else:
            meta = {"name": pdir.name}
        prompts_file = pdir / "prompts.jsonl"
        prompt_count = 0
        if prompts_file.exists():
            prompt_count = sum(1 for line in prompts_file.read_text().splitlines() if line.strip())
        meta["prompt_count"] = prompt_count
        meta["path"] = str(pdir)
        out.append(meta)
    return out


def get(name: str) -> Optional[dict]:
    """Get a single project's metadata."""
    pdir = _project_dir(_sanitize(name))
    meta_file = pdir / "project.json"
    if not meta_file.exists():
        return None
    return json.loads(meta_file.read_text())


def delete(name: str) -> bool:
    """Delete a project folder. Returns True if it existed."""
    import shutil
    pdir = _project_dir(_sanitize(name))
    if not pdir.exists():
        return False
    shutil.rmtree(pdir)
    # clear active if it was this project
    if get_active() == _sanitize(name):
        set_active(None)
    return True


def set_active(name: Optional[str]) -> None:
    """Set the active project (or None to deactivate)."""
    ensure_dirs()
    if name is None:
        ACTIVE_FILE.unlink(missing_ok=True)
    else:
        ACTIVE_FILE.write_text(_sanitize(name))


def get_active() -> Optional[str]:
    """Return the active project name, or None."""
    if not ACTIVE_FILE.exists():
        return None
    name = ACTIVE_FILE.read_text().strip()
    return name if name else None


def add_prompt(project_name: str, prompt: str, response: str = "",
               source: str = "agent") -> None:
    """Append a prompt + response to a project's prompts.jsonl."""
    ensure_dirs()
    pdir = _project_dir(_sanitize(project_name))
    if not pdir.exists():
        create(project_name)
    entry = {
        "ts": datetime.now().isoformat(),
        "prompt": prompt,
        "response": (response or "")[:5000],
        "source": source,
    }
    with (pdir / "prompts.jsonl").open("a") as f:
        f.write(json.dumps(entry) + "\n")


def get_prompts(project_name: str) -> list[dict]:
    """Return all saved prompts for a project."""
    pdir = _project_dir(_sanitize(project_name))
    pfile = pdir / "prompts.jsonl"
    if not pfile.exists():
        return []
    out = []
    for line in pfile.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _sanitize(name: str) -> str:
    """Make a name safe for a folder: lowercase, spaces -> hyphens, strip special chars."""
    return "".join(c if c.isalnum() or c in " -_" else "" for c in name).strip().lower().replace(" ", "-")
