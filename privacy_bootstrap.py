"""
privacy_bootstrap.py

Process-level privacy defaults that must be applied BEFORE importing CrewAI.
CrewAI telemetry is opt-out upstream; this project is local-first, so the
project default is the reverse: no CrewAI telemetry unless the owner
explicitly overrides the environment before process start.
"""
import os

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
