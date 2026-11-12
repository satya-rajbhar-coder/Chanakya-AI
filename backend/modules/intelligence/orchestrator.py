"""Hybrid orchestrator entry point.

Kept for backward compatibility with the original module layout. The
orchestration logic lives in :mod:`modules.intelligence.service`.
"""

from modules.intelligence.service import IntelligenceService

__all__ = ["IntelligenceService"]
