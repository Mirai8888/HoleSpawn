"""
HoleSpawn scraper package — multi-platform social media data collection.

Platforms:
  - Twitter/X: GraphQL interception via Playwright (twitter.py)
  - Reddit: JSON API via old.reddit.com (reddit.py)
  - GitHub: REST API v3 (github_scraper.py)
  - Hacker News: Algolia search API (hackernews.py)
  - Mastodon/Fediverse: ActivityPub API (mastodon.py)
  - Substack: Publication API (substack.py)
  - Community edges: Following/followers network mapping (community_edges.py)
  - GraphQL: Raw Twitter GraphQL operations (graphql.py)
"""

from .twitter import TwitterScraper
from .reddit import scrape_reddit_user
from .github_scraper import scrape_github_user
from .hackernews import scrape_hn_user
from .mastodon import scrape_mastodon_user
from .substack import scrape_substack

__all__ = [
    "TwitterScraper",
    "scrape_reddit_user",
    "scrape_github_user",
    "scrape_hn_user",
    "scrape_mastodon_user",
    "scrape_substack",
]
