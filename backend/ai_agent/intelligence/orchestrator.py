"""Hybrid orchestrator entry point.

Kept for backward compatibility with the original module layout. The
orchestration logic lives in :mod:`modules.intelligence.service`.
"""

from ai_agent.intelligence.service import IntelligenceService

__all__ = ["IntelligenceService"]
