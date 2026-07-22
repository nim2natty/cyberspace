"""cyberspace brain - the evolving orchestration backbone.

The Brain is the flagship layer that sits above the platforms (swarm,
airbender, shadowdragon, stickem, iceberg). It turns a plain-language request
into a multi-tool, multi-threaded operation organized by the Cyber Kill Chain:

  request  ->  plan (Kill Chain stages, multiple tools per task)
            ->  acquire any missing software (Iceberg + web, confirmed install)
            ->  execute sub-tasks concurrently via swarm delegates
            ->  compile a comprehensive report with artifact links
            ->  learn what succeeded/failed into a playbook
            ->  feed that learning back as context for the next request

Over time the playbook makes the operator's instance more precise and faster on
recurring intents. Everything stays within the operator's authorized scope.
"""
__version__ = "0.1.0"
