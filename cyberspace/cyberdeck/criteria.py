"""Success criteria: measurable checks the Cyberdeck always evaluates against.

A tool "running without error" is NOT the same as it succeeding. nmap returning
empty output, sqlmap finding no injection, or a packet capture with zero packets
all "succeed" under the old definition - which corrupts both the report and what
the Cyberdeck learns. This module defines measurable per-tool and per-stage criteria
and evaluates every task result against them.

Grounded in the Anthropic prompt-engineering prerequisite: before any prompt/run,
define clear success criteria and ways to empirically test against them. The
Cyberdeck applies this platform-wide: every execution, every tool, every objective.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class CriterionResult:
    criterion_id: str
    status: str          # 'pass' | 'fail' | 'uncertain'
    reason: str = ""
    evidence: str = ""

    def to_dict(self) -> dict:
        return {"criterion_id": self.criterion_id, "status": self.status,
                "reason": self.reason, "evidence": self.evidence}


@dataclass
class Criterion:
    """A measurable success test for a tool or a stage.

    ``check(output, context)`` returns a CriterionResult. Checks are heuristic
    (pattern/count based on real tool output) - deliberately conservative: when
    evidence is ambiguous they return 'uncertain' rather than guessing.
    """
    id: str
    tool: str                       # binary name, or '' for an objective/stage
    description: str
    check: Callable[[str, dict], CriterionResult]


# ---------------------------------------------------------------------------
# Primitive check builders
# ---------------------------------------------------------------------------
def _has_any(text: str, needles) -> bool:
    t = text.lower()
    return any(n.lower() in t for n in needles)


def _count_matches(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def _no_error_lines(text: str) -> bool:
    t = text.lower()
    return not any(k in t for k in (
        "command not found", "no such file", "syntax error",
        "unable to resolve", "could not connect", "permission denied",
        "you don't have permission", "operation not permitted"))


def _pass(reason: str, evidence: str = "") -> CriterionResult:
    return CriterionResult("", "pass", reason, evidence)


def _fail(reason: str, evidence: str = "") -> CriterionResult:
    return CriterionResult("", "fail", reason, evidence)


def _uncertain(reason: str, evidence: str = "") -> CriterionResult:
    return CriterionResult("", "uncertain", reason, evidence)


def _count_success(min_count: int, patterns: tuple, what: str, blank_msg: str):
    """Build a check that requires >= min_count matches of any pattern."""
    def check(output: str, ctx: dict) -> CriterionResult:
        if not _no_error_lines(output):
            return _fail(f"tool reported an error; {what} not produced", output[:200])
        total = sum(_count_matches(output, p) for p in patterns)
        if total >= min_count:
            return _pass(f"found {total} {what}", output[:200])
        if total > 0:
            return _uncertain(f"only {total} {what} found (need {min_count})", output[:200])
        return _fail(blank_msg, output[:200])
    return check


# ---------------------------------------------------------------------------
# Per-tool criteria registry
# ---------------------------------------------------------------------------
# Each entry maps a binary name to a list of measurable criteria. These are the
# platform-wide defaults; the Cyberdeck applies them to every relevant task.
def _tool_criteria() -> list[Criterion]:
    C: list[Criterion] = []

    # --- Reconnaissance / discovery (AirBender) ---------------------------
    def _nmap_check(output, ctx):
        if not _no_error_lines(output):
            return _fail("nmap reported an error", output[:200])
        host_up = bool(re.search(r"(?im)^Host is up(?:\s|\.|$)", output))
        ports = bool(re.search(
            r"(?im)^\d+/(?:tcp|udp)\s+(?:open|filtered|open\|filtered)\b", output))
        if host_up and ports:
            return _pass("at least one host responded with enumerated ports", output[:200])
        if host_up:
            return _uncertain("host(s) up but no open/filtered ports reported", output[:200])
        return _fail("no hosts reported up - target may be down or out of scope", output[:200])
    C.append(Criterion("nmap.hosts_responding", "nmap", ">=1 host responds with ports", _nmap_check))

    C.append(Criterion("masscan.ports_found", "masscan", ">=1 open port discovered",
        _count_success(1, (r"\d+/tcp", r"\d+/udp", r"Discovered open port"),
                       "open ports", "no open ports found - check target/rate")))

    def _ping_check(output, ctx):
        up = _has_any(output, ("is alive", "host is up", "1 packets received",
                               "bytes received", "reply"))
        return _pass("at least one host replied", output[:160]) if up else \
            _fail("no hosts replied to the sweep", output[:160])
    C.append(Criterion("pingsweep.host_replied", "ping-sweep", ">=1 host replied", _ping_check))

    C.append(Criterion("dig.resolved", "dig", "DNS record resolved",
        _count_success(1, (r"ANSWER SECTION", r"IN\s+A\s+", r"IN\s+CNAME", r"IN\s+MX"),
                       "DNS records", "no DNS records returned")))
    C.append(Criterion("whois.data", "whois", "registration data returned",
        _count_success(1, (r"Registrant", r"Registry", r"Updated Date", r"Name Server"),
                       "registration fields", "no registration data returned")))

    # --- Web application testing (ShadowDragon) ---------------------------
    def _sqlmap_check(output, ctx):
        if _has_any(output, ("is vulnerable", "injectable", "the back-end DBMS is",
                             "available databases", "banner:")):
            return _pass("SQL injection confirmed", output[:200])
        if _has_any(output, ("does not seem to be injectable", "all tested parameters do not appear")):
            return _pass("test completed with an explicit not-injectable verdict", output[:200])
        return _uncertain("sqlmap did not reach a clear vulnerable/not-vulnerable verdict", output[:200])
    C.append(Criterion("sqlmap.injection_confirmed", "sqlmap", "injection confirmed", _sqlmap_check))

    def _discovery_check(output, ctx):
        if not _no_error_lines(output):
            return _fail("content discovery reported an error", output[:200])
        found = _count_matches(output, r"Status:\s*(?:200|301|302)") + _count_matches(output, r"Found")
        if found:
            return _pass(f"content discovery completed with {found} path findings", output[:200])
        if _has_any(output, ("0 found", "no results", "finished", "completed")):
            return _pass("content discovery completed with zero paths", output[:200])
        return _uncertain("content discovery did not show completion or findings", output[:200])
    C.append(Criterion("gobuster.completed", "gobuster", "discovery completed with a verdict", _discovery_check))
    C.append(Criterion("ffuf.paths_found", "ffuf", ">=1 path discovered",
        _count_success(1, (r"Status:\s*200", r"Status:\s*301", r"Status:\s*302"),
                       "discoverable paths", "no paths discovered")))
    def _scan_verdict(output, ctx):
        if not _no_error_lines(output):
            return _fail("scanner reported an error", output[:200])
        if _has_any(output, ("OSVDB", "[critical]", "[high]", "[medium]", "[low]", "[info]", "Server:")):
            return _pass("scanner completed with findings", output[:200])
        if _has_any(output, ("0 findings", "0 matched", "no templates matched", "scan completed", "finished")):
            return _pass("scanner completed with zero findings", output[:200])
        return _uncertain("scanner did not provide a clear completion verdict", output[:200])
    C.append(Criterion("nikto.completed", "nikto", "scan completed with a verdict", _scan_verdict))
    C.append(Criterion("nuclei.completed", "nuclei", "scan completed with a verdict", _scan_verdict))
    C.append(Criterion("whatweb.tech", "whatweb", ">=1 technology identified",
        _count_success(1, (r"Apache", r"nginx", r"PHP", r"WordPress", r"\[[A-Za-z][A-Za-z0-9.-]*"),
                       "technologies", "no technologies identified")))

    # --- Passwords --------------------------------------------------------
    def _crack_check(output, ctx):
        if _has_any(output, ("cracked", "recovered", "Session completed",
                             "complete", "Password hash")) and \
           _has_any(output, (":", "->", "=") if True else ()):
            # Look for an actual hash:password pair.
            if re.search(r"[0-9a-fA-F]{32}.*:.*", output) or \
               re.search(r"\$[0-9]+\$.*\$.*:.*", output) or \
               _has_any(output, ("cracked", "recovered")):
                return _pass("at least one hash/credential recovered", output[:200])
        if _has_any(output, ("no hashes loaded", "no password")):
            return _fail("input hashes/credentials were not loadable", output[:200])
        if _has_any(output, ("0 recovered", "recovered 0", "exhausted", "session completed")):
            return _pass("credential test completed with zero recoveries", output[:200])
        return _uncertain("cracker ran but did not clearly recover anything", output[:200])
    C.append(Criterion("john.recovered", "john", ">=1 credential recovered", _crack_check))
    C.append(Criterion("hashcat.recovered", "hashcat", ">=1 credential recovered", _crack_check))
    def _hydra_check(output, ctx):
        if not _no_error_lines(output):
            return _fail("credential test reported an error", output[:200])
        if re.search(r"login:\s*\S+", output, re.I) or _has_any(output, ("valid password",)):
            return _pass("credential test completed with valid login evidence", output[:200])
        if _has_any(output, ("0 valid passwords found", "0 valid password", "finished")):
            return _pass("credential test completed with zero valid logins", output[:200])
        return _uncertain("credential test did not provide a clear completion verdict", output[:200])
    C.append(Criterion("hydra.completed", "hydra", "credential test completed with a verdict", _hydra_check))

    # --- Packet capture ---------------------------------------------------
    def _capture_check(output, ctx):
        if not _no_error_lines(output):
            return _fail("capture tool reported an error (often permissions)", output[:200])
        if _has_any(output, ("0 packets captured", "0 packets received", "captured 0")):
            return _fail("capture ran but captured 0 packets - no traffic in scope", output[:200])
        if _count_matches(output, r"\d+\.\d+\.\d+\.\d+") >= 1 or \
           _has_any(output, ("packet", "packets")):
            return _pass("at least one packet captured for an in-scope host", output[:200])
        return _uncertain("capture ran but no packet evidence present", output[:200])
    C.append(Criterion("tshark.captured", "tshark", ">=1 packet captured", _capture_check))
    C.append(Criterion("tcpdump.captured", "tcpdump", ">=1 packet captured", _capture_check))

    # --- Exploitation -----------------------------------------------------
    def _msf_check(output, ctx):
        if _has_any(output, ("meterpreter session", "session 1 opened",
                             "command shell session", "win")):
            return _pass("a session/shell was opened", output[:200])
        if _has_any(output, ("exploit failed", "no session", "completed, but no session")):
            return _pass("exploit test completed with an explicit no-session verdict", output[:200])
        return _uncertain("msf ran but no clear session outcome", output[:200])
    C.append(Criterion("msfconsole.session", "msfconsole", "session opened", _msf_check))

    C.append(Criterion("searchsploit.results", "searchsploit", ">=1 exploit found",
        _count_success(1, (r"Exploit\\s+Title", r"exploit/", r"shellcodes/"),
                       "exploit entries", "no matching exploits found")))

    # --- OSINT / recon ----------------------------------------------------
    C.append(Criterion("theharvester.results", "theHarvester", ">=1 host/email found",
        _count_success(1, (r"@", r"https?://", r"\d+\.\d+\.\d+\.\d+"),
                       "hosts/emails/IPs", "no hosts/emails discovered")))
    C.append(Criterion("amass.subdomains", "amass", ">=1 subdomain found",
        _count_success(1, (r"[a-z0-9.-]+\.[a-z]{2,}",), "names", "no names enumerated")))

    def _chain_check(output, ctx):
        if not _no_error_lines(output):
            return _fail("pipeline reported an error", output[:200])
        positive = (r"(?im)^Host is up", r"(?im)^\d+/(?:tcp|udp)\s+open\b",
                    r"(?im)^findings?:\s*[^\s0]", r"(?im)^results?:\s*[^\s0]")
        if any(re.search(pattern, output) for pattern in positive):
            return _pass("pipeline returned correlated findings", output[:200])
        return _uncertain("pipeline returned no recognizable finding evidence", output[:200])
    C.append(Criterion("chain.findings", "chain", "pipeline returned findings", _chain_check))

    def _report_check(output, ctx):
        if output.strip().lower() not in ("", "none", "null") and not output.lstrip().lower().startswith("error"):
            return _pass("non-empty report produced", output[:200])
        return _fail("report output was empty or errored", output[:200])
    C.append(Criterion("report.nonempty", "report", "non-empty report produced", _report_check))
    return C


_TOOL_TABLE: dict[str, list[Criterion]] = {}
for _c in _tool_criteria():
    _TOOL_TABLE.setdefault(_c.tool, []).append(_c)


# ---------------------------------------------------------------------------
# Per-stage / objective criteria
# ---------------------------------------------------------------------------
def _stage_criteria() -> dict[str, list[Criterion]]:
    """Criteria a whole Kill Chain stage must meet to count as successful."""
    def recon(output, ctx):
        found = bool(re.search(
            r"(?im)(^Host is up|^\d+/(?:tcp|udp)\s+open\b|"
            r"\b\d{1,3}(?:\.\d{1,3}){3}\b|^[a-z0-9.-]+\.[a-z]{2,}\s*$)", output))
        zero = _has_any(output, ("no hosts found", "0 hosts", "scan completed", "0 results"))
        return _pass("recon completed with an explicit surface verdict") if found or zero else \
            _uncertain("recon produced no clear completion verdict")
    def weapon(output, ctx):
        found = _has_any(output, ("exploit", "payload", "vulnerability", "candidate", "CVE"))
        zero = _has_any(output, ("no matching exploits", "0 candidates", "search completed"))
        return _pass("weapon search completed with an explicit verdict") if found or zero else \
            _uncertain("weapon search produced no clear completion verdict")
    def exploit(output, ctx):
        found = _has_any(output, ("confirmed", "vulnerable", "session", "exploited", "injectable"))
        negative = _has_any(output, ("not injectable", "no session", "not vulnerable",
                                     "0 findings", "test completed"))
        return _pass("exploit assessment completed with an explicit verdict") if found or negative else \
            _uncertain("exploit assessment produced no clear verdict")
    def objectives(output, ctx):
        valid = output.strip().lower() not in ("", "none", "null")
        return _pass("report compiled") if valid else _fail("empty report")
    def delivery(output, ctx):
        found = _has_any(output, ("delivered", "delivery confirmed", "request sent", "uploaded"))
        return _pass("delivery evidence recorded") if found else _uncertain("delivery not confirmed")
    def install(output, ctx):
        found = _has_any(output, ("installed", "persistence confirmed", "implant active", "service created"))
        return _pass("installation/persistence evidenced") if found else _uncertain("installation not confirmed")
    def c2(output, ctx):
        found = _has_any(output, ("channel established", "connected", "callback received", "session opened"))
        return _pass("C2 channel evidenced") if found else _uncertain("C2 channel not confirmed")
    return {
        "recon": [Criterion("recon.surface_mapped", "", "attack surface mapped", recon)],
        "weapon": [Criterion("weapon.candidate", "", "weapon candidate identified", weapon)],
        "exploit": [Criterion("exploit.confirmed", "", "exploitable finding confirmed", exploit)],
        "delivery": [Criterion("delivery.confirmed", "", "delivery confirmed", delivery)],
        "install": [Criterion("install.confirmed", "", "installation confirmed", install)],
        "c2": [Criterion("c2.confirmed", "", "C2 channel confirmed", c2)],
        "objectives": [Criterion("objectives.report", "", "report compiled", objectives)],
    }


_STAGE_TABLE = _stage_criteria()


# ---------------------------------------------------------------------------
# Evaluation API (used by the executor for every task)
# ---------------------------------------------------------------------------
def criteria_for_task(task) -> list[Criterion]:
    """Collect the PER-TOOL criteria that apply to a task.

    Stage/objective criteria are evaluated separately against the stage's
    aggregated output (see evaluate_stage) - applying them per task would wrongly
    fail sub-tasks (e.g. a packet-capture task has no 'host' keyword).
    """
    out: list[Criterion] = []
    for tool in task.tools:
        binname = str(tool).rsplit("::", 1)[-1].rsplit(".", 1)[-1].replace("_", "-")
        out.extend(_TOOL_TABLE.get(binname, []))
    return out


def evaluate_tool(tool: str, output: str, *, stage: str = "",
                  description: str = "") -> list[CriterionResult]:
    """Evaluate only one tool's criteria against only that tool's output."""
    binary = str(tool).rsplit("::", 1)[-1].rsplit(".", 1)[-1].replace("_", "-")
    results: list[CriterionResult] = []
    for crit in _TOOL_TABLE.get(binary, []):
        try:
            result = crit.check(output, {"stage": stage, "description": description})
        except Exception as exc:
            result = CriterionResult(
                crit.id, "uncertain", f"criterion check error: {exc}", "")
        result.criterion_id = crit.id
        results.append(result)
    return results


def evaluate_task(task, result) -> list[CriterionResult]:
    """Compatibility helper for one-tool tasks; multi-tool callers use evaluate_tool."""
    if len(task.tools) != 1:
        raise ValueError("multi-tool tasks must evaluate each tool's individual output")
    return evaluate_tool(task.tools[0], result.output, stage=task.stage,
                         description=task.description)


def evaluate_stage(stage: str, combined_output: str) -> list[CriterionResult]:
    """Run the PER-STAGE criteria against a stage's aggregated output."""
    results: list[CriterionResult] = []
    for crit in _STAGE_TABLE.get(stage, []):
        try:
            r = crit.check(combined_output, {"stage": stage})
        except Exception as e:
            r = CriterionResult(crit.id, "uncertain", f"criterion check error: {e}", "")
        r.criterion_id = crit.id
        results.append(r)
    return results


def task_succeeded(crit_results: list[CriterionResult]) -> tuple[bool, str]:
    """Decide whether a task genuinely succeeded.

    Pass only when every applicable criterion passes. Uncertain means the evidence
    is insufficient and must never be learned or reported as success.
    """
    if not crit_results:
        return True, "no specific criteria; ran without error"
    fails = [r for r in crit_results if r.status == "fail"]
    if fails:
        return False, "; ".join(f"{r.criterion_id}: {r.reason}" for r in fails)
    uncertain = [r for r in crit_results if r.status == "uncertain"]
    if uncertain:
        return False, "uncertain: " + "; ".join(r.reason for r in uncertain)
    return True, "all criteria passed"


def register_tool_criterion(binary: str, criterion_id: str, description: str,
                            check: Callable[[str, dict], CriterionResult]) -> None:
    """Let platforms add/override a per-tool criterion (platform-wide extension)."""
    c = Criterion(criterion_id, binary, description, check)
    lst = _TOOL_TABLE.setdefault(binary, [])
    lst[:] = [x for x in lst if x.id != criterion_id] + [c]


def all_criteria() -> dict:
    """Return the full registry for display ('criteria list')."""
    return {
        "tools": {tool: [{"id": c.id, "description": c.description} for c in lst]
                  for tool, lst in _TOOL_TABLE.items()},
        "stages": {stage: [{"id": c.id, "description": c.description} for c in lst]
                   for stage, lst in _STAGE_TABLE.items()},
    }
