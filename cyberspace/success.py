"""Platform-wide success contracts and the execution protocol.

Anthropic's prompt-engineering guidance starts with a clear definition of
success and an empirical way to test it.  Cyberspace keeps that requirement in
code so it is present in every agent session and every registered tool schema.
"""
from __future__ import annotations


SUCCESS_PROTOCOL = """
## Mandatory success protocol
Before acting, translate the request into specific, measurable, achievable, and
relevant acceptance criteria. Preserve criteria the user supplied; do not silently
weaken them. If a material criterion is missing or ambiguous, ask one focused
question before taking an irreversible or paid action. For routine reversible work,
state reasonable criteria and proceed.

For every tool call: (1) choose it because its success contract matches a criterion,
(2) inspect the returned evidence rather than assuming no exception means success,
(3) cross-check important or surprising findings with an independent method when
practical, and (4) stop, retry, or report a blocker when a criterion fails. Never
claim an action, artifact, fact, or outcome without evidence. Distinguish pass,
fail, uncertain, and not-tested. A final answer must map evidence to each acceptance
criterion, disclose uncertainty and failed checks, and give artifact/source links.
""".strip()


# Each built-in operation has a task-specific outcome and an empirical check.
# The registry also creates a description-derived contract for external tools.
_OUTCOMES = {
    "airbender": {
        "chain": ("Every requested pipeline stage completes and produces a merged, deduplicated finding set.", "Check stage statuses and compare the merged findings with each stage output."),
        "dig": ("The requested DNS record type is returned for the intended domain, or an authoritative no-record result is shown.", "Check the answer/status section, queried name, and record type."),
        "masscan": ("The requested address and port range is scanned and any open ports are reported with host evidence.", "Check the scanned range, completion/error output, and host:port findings."),
        "nmap": ("The intended target is scanned and responsive hosts, ports, states, and requested service details are reported.", "Check target scope, host-up evidence, port table, and scan completion/errors."),
        "ping_sweep": ("The intended subnet is probed and responsive hosts are listed without duplicates.", "Check probe completion and count unique replying addresses."),
        "whois": ("Registration or registry data is returned for the exact requested domain, or an authoritative absence is shown.", "Check queried domain and registry/registrant/name-server fields."),
    },
    "shadowdragon": {
        "chain": ("Every selected security-test stage runs in authorized scope and findings are correlated into one result.", "Check per-stage status, scope, and corroborating findings."),
        "gobuster": ("Content discovery completes for the intended URL and reports paths with HTTP status evidence.", "Check target URL, completion/errors, and path/status rows."),
        "hashcat": ("The requested hash job completes and recovered candidates are explicitly distinguished from exhausted/not-tested hashes.", "Check hash mode, status, recovered count, and potfile/output evidence."),
        "hydra": ("The authorized authentication test completes and valid credentials are evidenced or zero matches is explicitly reported.", "Check target/service, attempt status, and credential-hit lines."),
        "john": ("The requested hash job completes and recovered candidates are evidenced or zero matches is explicitly reported.", "Check format, session status, and --show-style recovery evidence."),
        "kali_catalog": ("Relevant Kali tools are listed with enough identity and purpose information to select one.", "Check that returned entries have names and descriptions/categories."),
        "kali_installed": ("Installed-state evidence is returned for the requested Kali tools.", "Check each requested tool has an explicit installed/missing result."),
        "kali_run": ("The selected allow-listed tool executes with the intended arguments and returns stdout, stderr, and status evidence.", "Check invoked command, scope, exit/error output, and substantive result."),
        "msf_run": ("The selected module runs against the authorized target and explicitly reports session/finding/no-session status.", "Check module, target options, job completion, and session/failure evidence."),
        "msf_search": ("Metasploit returns relevant modules for the query with module identity and ranking/details.", "Check query and at least one module row, or an explicit zero-result response."),
        "nikto": ("The web scan completes for the intended host and reports tested findings with URL/status evidence.", "Check target, scan completion, and finding rows or explicit no-findings result."),
        "searchsploit": ("Relevant exploit candidates are returned for the exact product/version query.", "Check query terms and exploit title/path rows or explicit zero results."),
        "secretsdump": ("The authorized credential extraction attempt explicitly reports extracted artifacts or a verified failure.", "Check target/scope, extraction status, and hash/artifact evidence without exposing it beyond scope."),
        "sqlmap": ("The intended parameter is tested and injectable/not-injectable/untested status is explicit.", "Check URL/parameter, test completion, DBMS evidence, and final verdict."),
        "theharvester": ("OSINT collection completes for the intended domain and deduplicated hosts/emails/IPs are reported.", "Check domain/sources and count unique evidenced results."),
        "whatweb": ("The intended URL responds and detected technologies are reported with confidence/evidence.", "Check URL, HTTP response, and technology/plugin findings."),
    },
    "iceberg": {
        "browse": ("The intended URL is opened in the requested isolated profile and launch status is explicit.", "Check profile identity, URL, process/session status, and errors."),
        "find": ("Relevant privacy/security resources are returned for the query with usable locations.", "Check query match and that each result has an identifiable source/location."),
        "new_profile": ("A loadable isolated browser profile is created with the requested identity settings.", "Check saved profile path/name and reload or validate its fields."),
        "opsec_check": ("Every OPSEC control is reported as pass, fail, or warning with no silent checks.", "Check the complete control list and investigate every fail/warning."),
        "privacy_audit": ("The full privacy audit runs and reports coverage, pass/fail/warning counts, and remediation.", "Check all audit sections executed and each issue has evidence and a recommendation."),
        "status": ("Current IceBerg readiness and profile/session state are reported accurately.", "Check component availability and explicit ready/missing state."),
    },
    "stickem": {
        "deauth": ("The authorized lab deauthentication request is sent to the selected SSID for the requested count.", "Check selected SSID, authorization boundary, device acknowledgement, and transmitted count."),
        "hardware_status": ("ESP32, FT232, and router each have an explicit connected/ready/error state.", "Check all three components are present in the status response."),
        "help": ("Supported Marauder commands are returned from the connected device.", "Check device response contains command names/help rather than only connection text."),
        "list_ports": ("Available serial ports are enumerated with stable device identifiers.", "Check unique port paths and device metadata, or explicit zero ports."),
        "router_leases": ("Current DHCP leases are returned with client identity and addressing evidence.", "Check unique IP/MAC/hostname rows or an explicit empty lease table."),
        "router_status": ("Router uptime, interfaces, and Wi-Fi state are returned from the configured router.", "Check router identity plus explicit status for each requested subsystem."),
        "scan_ap": ("Nearby access points are enumerated with SSID/BSSID/channel/signal evidence.", "Check device completion and deduplicate AP rows by BSSID."),
        "select_ssid": ("The exact owned lab SSID is selected and acknowledged by the ESP32.", "Check requested SSID equals acknowledged selected SSID."),
        "sniff_pmkid": ("The authorized capture attempt completes and a PMKID/EAPOL artifact is evidenced or absence is explicit.", "Check selected SSID, capture status, packet evidence, and artifact path."),
    },
    "robodaddy": {
        "connect": ("The selected served model becomes the active Swarm provider and passes a configuration check.", "Reload provider configuration and verify model name/base URL."),
        "custom": ("A custom model plan containing user success criteria, data, parameters, guardrails, cost, and evaluation approach is persisted.", "Reload the plan and check every required design field before launch."),
        "cyber": ("A scoped cyber-model plan containing user success criteria, authorization, data, parameters, cost, and evaluations is persisted.", "Reload the plan and check criteria, scope, authorization, and training fields."),
        "datasets": ("Relevant datasets are returned with repository ID, size, schema, license, and access status.", "Check metadata completeness and relevance to the stated model criteria."),
        "discover": ("Current dataset candidates are ranked for the stated intent with provenance and access metadata.", "Check source/revision, rank rationale, license, and access for each candidate."),
        "jobs": ("Every training job has an explicit current state and progress/error evidence.", "Cross-check registry state with progress files and worker status."),
        "keys": ("The requested key operation completes without printing or persisting plaintext secrets insecurely.", "Check prefix/status in registry and native secret-store operation."),
        "latest": ("The most recent cached datasets are listed in descending recency with provenance metadata.", "Check timestamps/order, repository IDs, and cache freshness."),
        "models": ("Registered models are listed with training/serving state and identity.", "Cross-check model records with their job and serving artifacts."),
        "parameters": ("Parameter changes validate, persist, and appear in the composed system prompt/config.", "Reload parameters and compare requested fields and generated prompt."),
        "plan": ("The plan includes user success criteria, model/data choices, estimates, guardrails, and an empirical evaluation approach.", "Validate required fields and map each success criterion to an evaluation before training."),
        "recommend": ("Recommendations are compatible, evidence-based, and tied to the stated intent and success criteria.", "Validate ranges/compatibility and show rationale; label heuristic or AI-derived advice."),
        "refresh": ("Dataset refresh completes and atomically stores current, provenance-bearing cache entries.", "Reload cache and verify count, timestamp, IDs, and revisions."),
        "serve": ("The trained model is configured for serving and responds through the intended local endpoint.", "Check model artifact, generated configuration, process/API health, and authentication."),
        "train": ("Training reaches a terminal state with progress, metrics, artifacts, cost, and criterion-based evaluation results.", "Check worker state, logs, checkpoints/model artifact, spend, and evaluation report."),
    },
    "cyberdeck": {
        "acquire": ("A provenance-checked install candidate is found without installing untrusted software.", "Check source, package-manager command, provenance verdict, and confirmation boundary."),
        "plan": ("The objective is decomposed into ordered, scoped tasks with criteria, tools, dependencies, and verification.", "Check every objective criterion maps to at least one task and empirical check."),
        "recall": ("Relevant prior outcomes are returned with success state, evidence summary, and project scope.", "Check query relevance and never treat failed/uncertain outcomes as proven successes."),
        "run": ("All objective criteria are evaluated and the report contains evidence, failures, uncertainty, and artifacts.", "Require task and stage criterion results; success only when mandatory checks pass."),
        "stats": ("Playbook totals and tool history are calculated from persisted entries.", "Recount persisted entries and compare successes/failures/tool set."),
        "prompts": ("Ordered prompt records are returned with sequence, label, source, and prompt text.", "Check sequence order and match query/label filters against persisted records."),
    },
    "project": {
        "create": ("A uniquely named project is persisted and becomes active.", "Reload the project index and active-project pointer."),
        "open": ("The intended existing project is resolved unambiguously and becomes active.", "Read back the active project and match its canonical name."),
        "search": ("Relevant project/chat matches are returned with project identity and snippets.", "Check query match, project scope, and result locations."),
    },
    "swarm": {
        "delegate": ("The correct specialist receives the task, acceptance criteria, context, and returns criterion-linked evidence.", "Check stage identity and require a pass/fail/uncertain verdict for every delegated criterion."),
    },
}


def contract_for_tool(name: str, description: str = "") -> tuple[list[str], str]:
    """Return success criteria and verification for a built-in or external tool."""
    module, _, action = name.partition(".")
    contract = _OUTCOMES.get(module, {}).get(action)
    if contract:
        return [contract[0]], contract[1]
    purpose = (description or f"perform {name}").strip().rstrip(".")
    return ([f"The tool completes its stated operation: {purpose}; it returns substantive evidence or an explicit no-result state."],
            "Check the requested inputs, error/status output, and returned evidence; do not infer success from absence of an exception.")


def tool_contract_text(name: str, criteria: list[str], verification: str) -> str:
    lines = [f"Success contract for {name}:"]
    lines.extend(f"- {criterion}" for criterion in criteria)
    lines.append(f"Verification: {verification}")
    return "\n".join(lines)


def assess_tool_output(output: object) -> tuple[str, str]:
    """Return a conservative runtime verdict without inventing semantic proof.

    Arbitrary non-empty text is *uncertain*, never pass. A pass requires an
    explicit structured status from the tool; semantic contracts still need review.
    """
    text = str(output or "").strip()
    low = text.lower()
    if not text:
        return "fail", "tool returned no evidence"
    explicit_pass = ('"status": "pass"', "status=pass", "[status: pass]", "status: passed")
    hard_errors = (
        "error executing", "traceback (most recent call last)", "permission denied",
        "command not found", "not found in registry", "stage error",
        "success_criteria required", "success criteria required", "intent required",
        "name required", "tool name required", "query required",
        "must be ", "invalid ", "outside this ai mode", "could not ", "failed:",
    )
    if any(marker in low for marker in hard_errors):
        return "fail", "tool reported a runtime or availability error"
    no_result = ("no results", "no matching", "not tested", "nothing found", "no cached")
    if any(marker in low for marker in no_result):
        return "uncertain", "tool completed but reported no positive result; verify scope and inputs"
    if any(marker in low for marker in explicit_pass):
        return "pass", "tool explicitly reported pass; verify its evidence against the contract"
    return "uncertain", "tool returned output, but no structured criterion verdict; inspect its evidence"
