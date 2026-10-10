"""Privacy defaults applied before framework imports and telemetry initialization.

Process-level privacy defaults that must be applied BEFORE importing CrewAI.
CrewAI telemetry is opt-out upstream; this project is local-first, so the
project default is the reverse: no CrewAI telemetry unless the owner
explicitly overrides the environment before process start.
"""

import os

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

# CrewAI tracing is separate from telemetry and can inherit saved account consent.
# This local application never enables trace sharing through those global settings.
os.environ["CREWAI_TRACING_ENABLED"] = "false"
