# ============================================
# FILE: app/scheduler/__init__.py
# ============================================
"""
Планувальник задач
"""

from .tasks import setup_scheduler

__all__ = ['setup_scheduler']