"""
app/state.py — Mutable global runtime state.

All values here are set/mutated at runtime (not config-time).
Business logic belongs in the domain modules; this file is a shared namespace only.
"""

from typing import Optional

# Active Claude sessions: session_id -> ClaudeSession
sessions: dict = {}

# Active PTY shell sessions: shell_id -> ShellSession
shell_sessions: dict = {}

# Active pipeline runners: pipeline_id -> PipelineRunner
pipelines: dict = {}

# Active plan phases: phase_id -> PlanPhase
plan_phases: dict = {}

# Rate-limit log: client_ip -> [timestamp, ...]
_session_create_log: dict = {}

# Set to True during POST /admin/restart to block new pipeline creation
_shutting_down: bool = False

# Claude CLI executable path — discovered in lifespan startup, None if not found
CLAUDE_EXE: Optional[str] = None
