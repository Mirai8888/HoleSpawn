#!/usr/bin/env python3
"""
Community Edge Scraper — builds the internal adjacency matrix for network analysis.

For each account in a target's following list, scrapes their Following list and
cross-references against the network to find internal edges. This reveals
sub-communities, bridge nodes, and cluster structure.

Strategy:
- Single browser context (avoids session creation overhead)
- GraphQL cursor pagination for complete Following extraction
- Incremental saves (checkpoint every 10 accounts)
- Skip accounts with >5000 following (too expensive, use sample)
- Rate limiting with configurable delays

Output: JSON edge map { "handle": ["follows_handle1", "follows_handle2", ...] }
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

DEFAULT_COOKIE_PATH = Path.home() / ".config" / "twitter" / "cookies.json"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _clean_cookies(raw):
    clean = []
    for c in raw:
        cc = {"name": c["name"], "value": c["value"], "domain": c.get("domain", ".x.com"), "path": c.get("path", "/")}
        ss = c.get("sameSite", "Lax")
        cc["sameSite"] = ss if ss in ("Strict", "Lax", "None") else "Lax"
        if c.get("expires") and c["expires"] > 0:
            cc["expires"] = c["expires"]
        clean.append(cc)
    return clean


def _parse_following_names(data):
    """Extract screen_names + cursor from a Following GraphQL response."""
    names = set()
    cursor = None
    try:
        for inst in data["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]:
            for entry in inst.get("entries", []):
                eid = entry.get("entryId", "")
                content = entry.get("content", {})
                if "cursor-bottom" in eid:
                    cursor = content.get("value")
                    continue
                ur = content.get("itemContent", {}).get("user_results", {}).get("result", {})
                if ur:
                    sn = ur.get("core", {}).get("screen_name")
                    if sn:
                        names.add(sn.lower())
    except (KeyError, TypeError):
        pass
    return names, cursor


async def scrape_community_edges(
    network_file: str,
    output_file: str,
    cookie_path: str = None,
    max_accounts: int = 100,
    max_following_per_account: int = 5000,
    page_delay: float = 0.5,
    account_delay: float = 2.0,
    headless: bool = True,
):
    """
    Build internal edge map for a network.

    Args:
        network_file: Path to JSON from graphql.py scrape_network output
        output_file: Path to save edge map JSON
        cookie_path: Twitter cookies JSON
        max_accounts: Max accounts to scrape (by follower count priority)
        max_following_per_account: Skip accounts following more than this
        page_delay: Delay between pagination requests (seconds)
        account_delay: Delay between accounts (seconds)
        headless: Run browser headless
    """
    cookie_file = Path(cookie_path) if cookie_path else DEFAULT_COOKIE_PATH
    raw_cookies = json.loads(cookie_file.read_text())
    cookies = _clean_cookies(raw_cookies)
    req_cookies = {c["name"]: c["value"] for c in raw_cookies}

    # Load network
    network = json.loads(Path(network_file).read_text())
    following_list = network.get("following", [])
    network_handles = {u["screen_name"].lower() for u in following_list}

    # Sort by follower count (most influential first)
    by_followers = sorted(following_list, key=lambda x: x.get("followers_count", 0), reverse=True)

    # Load existing progress
    output_path = Path(output_file)
    edges = {}
    if output_path.exists():
        edges = json.loads(output_path.read_text())
        logger.info(f"Resuming: {len(edges)} accounts already scraped")

    targets = []
    for u in by_followers[:max_accounts]:
        handle = u["screen_name"]
        if handle.lower() in {k.lower() for k in edges}:
            continue
        fc = u.get("following_count", 0)
        if fc > max_following_per_account:
            logger.debug(f"Skipping @{handle} (follows {fc} > {max_following_per_account})")
            continue
        targets.append(u)

    if not targets:
        logger.info("All accounts already scraped or filtered out")
        return edges

    logger.info(f"Network: {len(network_handles)} accounts, scraping {len(targets)} remaining")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=DEFAULT_USER_AGENT,
        )
        await ctx.add_cookies(cookies)

        # Reuse a single page to minimize context switching
        page = await ctx.new_page()

        for i, user in enumerate(targets):
            handle = user["screen_name"]
            fc = user.get("following_count", 0)

            sys.stdout.write(f"\r[{i+1:3d}/{len(targets)}] @{handle:25s} (follows {fc:>5d}) ")
            sys.stdout.flush()

            internal_edges, status = await _scrape_one_following(
                page, req_cookies, handle, fc,
                network_handles, max_following_per_account, page_delay
            )

            edges[handle] = sorted(internal_edges)
            sys.stdout.write(f"→ {len(internal_edges):3d} edges ({status})\n")
            sys.stdout.flush()

            # Checkpoint
            if (i + 1) % 10 == 0:
                output_path.write_text(json.dumps(edges, indent=2))
                total_e = sum(len(v) for v in edges.values())
                logger.info(f"Checkpoint: {len(edges)} accounts, {total_e} total edges")

            await asyncio.sleep(account_delay)

        await browser.close()

    # Final save
    output_path.write_text(json.dumps(edges, indent=2))
    total_edges = sum(len(v) for v in edges.values())
    non_empty = sum(1 for v in edges.values() if v)
    logger.info(f"Complete: {len(edges)} accounts, {non_empty} with edges, {total_edges} total internal edges")

    return edges


async def _scrape_one_following(page, req_cookies, handle, following_count,
                                 network_handles, max_following, page_delay):
    """Scrape one account's Following list, return (internal_edges_set, status_str)."""
    intercepted = {"url": None, "headers": None, "body": None}

    async def cap_req(request):
        if "graphql" in request.url.lower() and "Following" in request.url:
            if not intercepted["url"]:
                intercepted["url"] = request.url
                intercepted["headers"] = dict(request.headers)

    async def cap_resp(response):
        if "graphql" in response.url.lower() and "Following" in response.url:
            if not intercepted["body"]:
                try:
                    intercepted["body"] = await response.json()
                except Exception:
                    pass

    page.on("request", cap_req)
    page.on("response", cap_resp)

    try:
        await page.goto(
            f"https://x.com/{handle}/following",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        await asyncio.sleep(3)
    except Exception as e:
        page.remove_listener("request", cap_req)
        page.remove_listener("response", cap_resp)
        return set(), f"timeout: {e}"

    page.remove_listener("request", cap_req)
    page.remove_listener("response", cap_resp)

    if not intercepted["body"]:
        return set(), "no_data"

    all_names = set()
    names, cursor = _parse_following_names(intercepted["body"])
    all_names.update(names)

    # Paginate if reasonable size
    if cursor and intercepted["url"] and following_count <= max_following:
        base_url = intercepted["url"].split("?")[0]
        headers = intercepted["headers"]
        parsed = urlparse(intercepted["url"])
        params = parse_qs(parsed.query)
        orig_vars = json.loads(params["variables"][0])
        features = params["features"][0]

        max_pages = min(following_count // 50 + 2, 100)
        for pg in range(max_pages):
            new_vars = orig_vars.copy()
            new_vars["cursor"] = cursor

            new_params = {
                "variables": json.dumps(new_vars, separators=(",", ":")),
                "features": features,
            }
            if "fieldToggles" in params:
                new_params["fieldToggles"] = params["fieldToggles"][0]

            try:
                resp = requests.get(
                    base_url,
                    headers=headers,
                    cookies=req_cookies,
                    params=new_params,
                    timeout=15,
                )
                if resp.status_code == 200:
                    names, cursor = _parse_following_names(resp.json())
                    all_names.update(names)
                    if not names or not cursor:
                        break
                    time.sleep(page_delay)
                elif resp.status_code == 429:
                    logger.warning(f"Rate limited on @{handle}, waiting 60s...")
                    time.sleep(60)
                else:
                    break
            except Exception:
                break

    internal = {n for n in all_names if n in network_handles}
    status = f"full({len(all_names)})" if following_count <= max_following else f"sample({len(all_names)})"
    return internal, status


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Community Edge Scraper")
    parser.add_argument("network_file", help="Network JSON from graphql.py")
    parser.add_argument("-o", "--output", default="/tmp/community_edges.json", help="Output edge map")
    parser.add_argument("-n", "--max-accounts", type=int, default=100, help="Max accounts to scrape")
    parser.add_argument("--max-following", type=int, default=5000, help="Skip accounts following more")
    parser.add_argument("--page-delay", type=float, default=0.5, help="Delay between pages")
    parser.add_argument("--account-delay", type=float, default=2.0, help="Delay between accounts")
    parser.add_argument("--cookies", default=str(DEFAULT_COOKIE_PATH))
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    result = asyncio.run(scrape_community_edges(
        network_file=args.network_file,
        output_file=args.output,
        cookie_path=args.cookies,
        max_accounts=args.max_accounts,
        max_following_per_account=args.max_following,
        page_delay=args.page_delay,
        account_delay=args.account_delay,
        headless=not args.visible,
    ))

    total = sum(len(v) for v in result.values())
    print(f"\nEdge map: {len(result)} accounts, {total} internal edges")
