"""Cyberdeck planning, prompt records, execution reports, and operation history.

Cyberdeck coordinates Swarm, AirBender, ShadowDragon, StickEm, and Iceberg. It
turns a security objective into a multi-tool operation organized by Kill Chain stage:

  request  ->  plan (Kill Chain stages, multiple tools per task)
            ->  acquire any missing software (Iceberg + web, confirmed install)
            ->  execute dependency-ready tool tasks concurrently
            ->  compile an evidence report with artifact links
            ->  learn what succeeded/failed into a playbook
            ->  feed that learning back as context for the next request

The playbook records verified task outcomes for reuse on similar objectives.
"""
__version__ = "0.1.0"
