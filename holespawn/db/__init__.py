"""
SQLite storage for profiles (and optional network reports) after scrape/run.
Agenda-based search: filter profiles by descriptive query for research/product understanding.
"""

from .store import init_db, store_profile, store_network_report
from .search import search_by_agenda

__all__ = ["init_db", "store_profile", "store_network_report", "search_by_agenda"]
