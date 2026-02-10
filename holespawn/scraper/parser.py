"""
Parse X GraphQL responses into flat structures. Defensive .get() throughout; X changes schema often.
"""


def _dig(data: dict, *keys: str) -> dict | None:
    out = data
    for k in keys:
        if not isinstance(out, dict):
            return None
        out = out.get(k)
    return out if isinstance(out, dict) else None


def parse_tweet_response(data: dict) -> list[dict]:
    """
    Parse UserTweets / timeline GraphQL response into flat tweet dicts.
    Output: id, text, full_text, created_at, author, favorite_count, retweet_count, reply_count,
    in_reply_to, is_retweet, is_quote, quoted_user, urls, media_urls, hashtags.
    """
    tweets: list[dict] = []
    try:
        instructions = (
            _dig(data, "data", "user", "result", "timeline_v2", "timeline", "instructions")
            or _dig(data, "data", "user", "result", "timeline", "instructions")
            or []
        )
        if not isinstance(instructions, list):
            return tweets
        for instruction in instructions:
            entries = instruction.get("entries") or []
            for entry in entries:
                try:
                    content = entry.get("content") or {}
                    item_content = content.get("itemContent") or {}
                    tweet_result = (item_content.get("tweet_results") or {}).get("result")
                    if not tweet_result or not isinstance(tweet_result, dict):
                        continue
                    legacy = tweet_result.get("legacy") or {}
                    core = tweet_result.get("core") or {}
                    user_res = (core.get("user_results") or {}).get("result") or {}
                    user_legacy = user_res.get("legacy") or {}
                    full_text = legacy.get("full_text") or legacy.get("text") or ""
                    tweet = {
                        "id": tweet_result.get("rest_id") or legacy.get("id_str"),
                        "text": full_text,
                        "full_text": full_text,
                        "created_at": legacy.get("created_at", ""),
                        "author": user_legacy.get("screen_name", ""),
                        "favorite_count": int(legacy.get("favorite_count") or 0),
                        "retweet_count": int(legacy.get("retweet_count") or 0),
                        "reply_count": int(legacy.get("reply_count") or 0),
                        "in_reply_to": legacy.get("in_reply_to_screen_name"),
                        "is_retweet": "retweeted_status_result" in tweet_result,
                        "is_quote": "quoted_status_result" in tweet_result,
                        "quoted_user": None,
                        "urls": [],
                        "media_urls": [],
                        "hashtags": [],
                    }
                    entities = legacy.get("entities") or {}
                    tweet["urls"] = [
                        u.get("expanded_url") or u.get("url")
                        for u in (entities.get("urls") or [])
                        if isinstance(u, dict) and (u.get("expanded_url") or u.get("url"))
                    ]
                    for m in (entities.get("media") or []):
                        if isinstance(m, dict):
                            u = m.get("media_url_https") or m.get("media_url") or m.get("url")
                            if u and u not in tweet["media_urls"]:
                                tweet["media_urls"].append(u)
                    tweet["hashtags"] = [
                        h.get("text") for h in (entities.get("hashtags") or []) if isinstance(h, dict) and h.get("text")
                    ]
                    if tweet["is_quote"]:
                        quoted = (tweet_result.get("quoted_status_result") or {}).get("result") or {}
                        if isinstance(quoted, dict):
                            qcore = quoted.get("core") or {}
                            quser = (qcore.get("user_results") or {}).get("result") or {}
                            tweet["quoted_user"] = (quser.get("legacy") or {}).get("screen_name")
                    if tweet["is_retweet"]:
                        rt = (tweet_result.get("retweeted_status_result") or {}).get("result") or {}
                        if isinstance(rt, dict):
                            rcore = rt.get("core") or {}
                            ruser = (rcore.get("user_results") or {}).get("result") or {}
                            tweet["retweeted_status_screen_name"] = (ruser.get("legacy") or {}).get("screen_name")
                    if tweet.get("id"):
                        tweets.append(tweet)
                except (KeyError, TypeError, ValueError):
                    continue
    except (KeyError, TypeError):
        pass
    return tweets


def parse_following_response(data: dict) -> list[str]:
    """Parse Following list GraphQL response into list of screen_name."""
    usernames: list[str] = []
    try:
        instructions = (
            _dig(data, "data", "user", "result", "timeline", "timeline", "instructions")
            or _dig(data, "data", "user", "result", "timeline", "instructions")
            or []
        )
        for instruction in instructions or []:
            for entry in (instruction.get("entries") or []):
                try:
                    item = (entry.get("content") or {}).get("itemContent") or {}
                    user_res = item.get("user_results") or {}
                    result = user_res.get("result") or {}
                    legacy = result.get("legacy") or {}
                    screen_name = legacy.get("screen_name") or result.get("screen_name")
                    if screen_name:
                        usernames.append(str(screen_name).strip().lstrip("@"))
                except (KeyError, TypeError):
                    continue
    except (KeyError, TypeError):
        pass
    return usernames


def parse_followers_response(data: dict) -> list[str]:
    """Parse Followers list GraphQL response. Same structure as following in many actors."""
    return parse_following_response(data)


def parse_user_profile(data: dict) -> dict:
    """Parse UserByScreenName response into profile dict."""
    result = _dig(data, "data", "user", "result") or {}
    legacy = result.get("legacy") or {}
    return {
        "username": legacy.get("screen_name", ""),
        "name": legacy.get("name", ""),
        "bio": legacy.get("description", ""),
        "followers_count": int(legacy.get("followers_count") or 0),
        "following_count": int(legacy.get("friends_count") or 0),
        "tweet_count": int(legacy.get("statuses_count") or 0),
        "created_at": legacy.get("created_at", ""),
        "verified": bool(result.get("is_blue_verified", False)),
        "profile_image_url": legacy.get("profile_image_url_https", ""),
        "location": legacy.get("location", ""),
    }
