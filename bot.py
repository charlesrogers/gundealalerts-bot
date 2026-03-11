"""
Reddit Bot — Posts useful price/deal data as comments on r/gundeals

Rules:
  - Never comment on dealer posts
  - Only comment when we have high-confidence data
  - One comment per post, ever
  - Rate limit: max N comments per hour
  - Must have a fresh Reddit account with API access

Comment types (in priority order):
  1. Product price check — compare to 90-day history for same product family
  2. Ammo CPR check — compare cost-per-round to 90-day caliber stats
  3. Category highlights — show top deals this week in same category (fallback)
"""

import os
import time
import math
from datetime import datetime, timedelta

# Config
MAX_COMMENTS_PER_HOUR = 6
MIN_DEAL_SCORE = 3            # Don't comment on posts nobody cares about
MIN_DEAL_AGE_MINUTES = 5      # Wait a bit before commenting
MAX_DEAL_AGE_HOURS = 6        # Don't comment on old posts
MIN_HISTORY_DEALS = 3         # Need this many past deals for price comparison
PRICE_SANITY_RATIO = 3.0      # Skip if price is >3x or <0.33x the avg (bad family match)
BOT_COMMENT_FIELD = "bot_commented"  # Flag on alert doc


def run_reddit_bot(db, dry_run=True):
    """
    Main entry point. Finds eligible posts and generates/posts comments.

    Args:
        db: MongoDB connection
        dry_run: If True, print comments but don't post to Reddit

    Returns:
        dict with results
    """
    if db is None:
        return {"success": False, "error": "No database connection"}

    start_time = time.time()
    now = datetime.utcnow()
    result = {
        "success": True,
        "posts_checked": 0,
        "comments_generated": 0,
        "comments_posted": 0,
        "skipped_reasons": {},
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    try:
        # Rate limit check — how many comments in last hour?
        hour_ago = now - timedelta(hours=1)
        recent_comments = db.alerts.count_documents({
            BOT_COMMENT_FIELD: True,
            "bot_commented_at": {"$gte": hour_ago},
        })
        remaining_budget = MAX_COMMENTS_PER_HOUR - recent_comments
        if remaining_budget <= 0:
            print(f"  [bot] Rate limited: {recent_comments} comments in last hour (max {MAX_COMMENTS_PER_HOUR})")
            result["skipped_reasons"]["rate_limited"] = 1
            return result

        # Find eligible posts
        min_age = now - timedelta(hours=MAX_DEAL_AGE_HOURS)
        max_age = now - timedelta(minutes=MIN_DEAL_AGE_MINUTES)

        eligible = list(db.alerts.find({
            "created_utc": {"$gte": min_age, "$lte": max_age},
            "is_dealer": {"$ne": True},
            "score": {"$gte": MIN_DEAL_SCORE},
            BOT_COMMENT_FIELD: {"$ne": True},
        }).sort("score", -1).limit(20))

        result["posts_checked"] = len(eligible)
        print(f"  [bot] Found {len(eligible)} eligible posts (budget: {remaining_budget} comments)")

        comments_made = 0

        for deal in eligible:
            if comments_made >= remaining_budget:
                break

            comment = generate_comment(db, deal, now)

            if comment is None:
                continue

            result["comments_generated"] += 1

            if dry_run:
                print(f"  [bot] DRY RUN comment for: {deal.get('title', '')[:70]}")
                print(f"         {comment[:150]}...")
            else:
                posted = post_comment_to_reddit(db, deal, comment)
                if posted:
                    comments_made += 1
                    result["comments_posted"] += 1

            # Mark as commented regardless of dry_run (in dry_run, skip marking)
            if not dry_run:
                db.alerts.update_one(
                    {"_id": deal["_id"]},
                    {"$set": {
                        BOT_COMMENT_FIELD: True,
                        "bot_commented_at": now,
                        "bot_comment_text": comment,
                    }}
                )

        result["execution_time"] = round(time.time() - start_time, 2)
        return result

    except Exception as e:
        import traceback
        print(f"  [bot] Error: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def generate_comment(db, deal, now):
    """
    Generate a comment for a deal. Returns markdown string or None if nothing useful.
    """
    title = deal.get("title", "")
    price = deal.get("price")
    product = deal.get("product", {})
    family_slug = product.get("family_slug", "")
    caliber = product.get("caliber", "")
    cpr = product.get("cpr")
    cats = deal.get("detected_categories", [])
    ninety_days_ago = now - timedelta(days=90)
    week_ago = now - timedelta(days=7)

    parts = []

    # ── 1. Product price history ──
    if family_slug and price and price > 0:
        price_comment = _build_price_comment(db, deal, family_slug, price, ninety_days_ago)
        if price_comment:
            parts.append(price_comment)

    # ── 2. Ammo CPR comparison ──
    if caliber and cpr and cpr > 0:
        cpr_comment = _build_cpr_comment(db, deal, caliber, cpr, ninety_days_ago)
        if cpr_comment:
            parts.append(cpr_comment)

    # ── 3. Category fallback — top deals this week ──
    if not parts and cats:
        cat_comment = _build_category_comment(db, deal, cats, week_ago)
        if cat_comment:
            parts.append(cat_comment)

    if not parts:
        return None

    # Assemble final comment
    body = "\n\n".join(parts)
    footer = (
        "\n\n---\n"
        "^(Price data from [GunDeals Alert](https://www.gundealalerts.com/) "
        "— tracking r/gundeals prices so you don't have to. | "
        "[Ammo Price Index](https://www.gundealalerts.com/ammo-prices))"
    )

    return body + footer


def _build_price_comment(db, deal, family_slug, price, since):
    """Build price comparison comment for a product family."""
    try:
        stats = list(db.alerts.aggregate([
            {"$match": {
                "product.family_slug": family_slug,
                "price": {"$exists": True, "$gt": 0},
                "created_utc": {"$gte": since},
                "_id": {"$ne": deal["_id"]},
            }},
            {"$group": {
                "_id": None,
                "avg_price": {"$avg": "$price"},
                "min_price": {"$min": "$price"},
                "max_price": {"$max": "$price"},
                "count": {"$sum": 1},
                "prices": {"$push": "$price"},
            }},
        ]))

        if not stats or stats[0]["count"] < MIN_HISTORY_DEALS:
            return None

        s = stats[0]
        avg = s["avg_price"]
        mn = s["min_price"]
        mx = s["max_price"]
        cnt = s["count"]

        # Sanity check — if price is wildly different, the family match is probably wrong
        # (e.g. a bundle matched to a single item family)
        if price > avg * PRICE_SANITY_RATIO or price < avg / PRICE_SANITY_RATIO:
            return None

        pct = ((avg - price) / avg) * 100

        # Calculate SD
        variance = sum((p - avg) ** 2 for p in s["prices"]) / cnt
        sd = variance ** 0.5
        z = (price - avg) / sd if sd > 0 else 0

        # Build comment
        lines = []
        lines.append(f"**📊 Price Check** (90-day, {cnt} deals)")
        lines.append("")
        lines.append(f"| | Price |")
        lines.append(f"|---|---|")
        lines.append(f"| This deal | **${price:,.2f}** |")
        lines.append(f"| 90-day avg | ${avg:,.2f} |")
        lines.append(f"| 90-day low | ${mn:,.2f} |")
        lines.append(f"| 90-day high | ${mx:,.2f} |")

        if pct > 10:
            lines.append(f"\n🔥 **{pct:.0f}% below the 90-day average.**")
            if z <= -1.5:
                lines.append(f"This is **{abs(z):.1f} standard deviations below the mean** — unusually cheap for this product.")
        elif pct > 3:
            lines.append(f"\n✅ {pct:.0f}% below average — decent price.")
        elif pct > -3:
            lines.append(f"\nRight around the 90-day average.")
        else:
            lines.append(f"\n⚠️ {abs(pct):.0f}% above the 90-day average.")

        return "\n".join(lines)

    except Exception as e:
        print(f"  [bot] Price comment error: {e}")
        return None


def _build_cpr_comment(db, deal, caliber, cpr, since):
    """Build ammo CPR comparison comment."""
    try:
        stats = list(db.alerts.aggregate([
            {"$match": {
                "product.caliber": caliber,
                "product.cpr": {"$exists": True, "$gt": 0, "$lt": 5},
                "created_utc": {"$gte": since},
                "_id": {"$ne": deal["_id"]},
            }},
            {"$group": {
                "_id": None,
                "avg_cpr": {"$avg": "$product.cpr"},
                "min_cpr": {"$min": "$product.cpr"},
                "p10": {"$percentile": {"input": "$product.cpr", "p": [0.1], "method": "approximate"}},
                "count": {"$sum": 1},
            }},
        ]))

        if not stats or stats[0]["count"] < MIN_HISTORY_DEALS:
            return None

        s = stats[0]
        avg_cpr = s["avg_cpr"]
        min_cpr = s["min_cpr"]
        cnt = s["count"]
        pct = ((avg_cpr - cpr) / avg_cpr) * 100

        lines = []
        lines.append(f"**🎯 {caliber} CPR Check** (90-day, {cnt} deals)")
        lines.append("")
        lines.append(f"| | CPR |")
        lines.append(f"|---|---|")
        lines.append(f"| This deal | **{cpr*100:.0f}¢/rd** |")
        lines.append(f"| 90-day avg | {avg_cpr*100:.0f}¢/rd |")
        lines.append(f"| 90-day best | {min_cpr*100:.0f}¢/rd |")

        if pct > 10:
            lines.append(f"\n🔥 **{pct:.0f}% below the 90-day average** — buy it.")
        elif pct > 3:
            lines.append(f"\n✅ {pct:.0f}% below average — solid price.")
        elif pct > -3:
            lines.append(f"\nRight around the 90-day average.")
        else:
            lines.append(f"\n⚠️ {abs(pct):.0f}% above the 90-day average.")

        return "\n".join(lines)

    except Exception as e:
        print(f"  [bot] CPR comment error: {e}")
        return None


def _build_category_comment(db, deal, category_ids, since):
    """Build category highlights comment (fallback)."""
    try:
        if not category_ids:
            return None

        cat_id = category_ids[0]
        cat = db.categories.find_one({"_id": cat_id})
        if not cat:
            return None

        cat_name = cat.get("display_name", cat.get("name", ""))

        best = list(db.alerts.find({
            "detected_categories": cat_id,
            "created_utc": {"$gte": since},
            "score": {"$gte": 10},
            "_id": {"$ne": deal["_id"]},
        }).sort("score", -1).limit(3))

        if not best:
            return None

        lines = []
        lines.append(f"**🏷️ Top {cat_name} deals this week:**")
        lines.append("")

        for d in best:
            p = d.get("price")
            score = d.get("score", 0)
            t = d.get("title", "")[:70]
            plink = d.get("permalink", "")
            if plink and not plink.startswith("http"):
                plink = "https://reddit.com" + plink
            price_str = f" — ${p:,.2f}" if p else ""
            lines.append(f"- [{t}]({plink}) ({score} pts{price_str})")

        return "\n".join(lines)

    except Exception as e:
        print(f"  [bot] Category comment error: {e}")
        return None


def post_comment_to_reddit(db, deal, comment_text):
    """
    Post a comment to Reddit via the API.
    Requires REDDIT_BOT_* env vars to be set.
    Returns True if successful.
    """
    try:
        import praw

        client_id = os.environ.get("REDDIT_BOT_CLIENT_ID")
        client_secret = os.environ.get("REDDIT_BOT_CLIENT_SECRET")
        username = os.environ.get("REDDIT_BOT_USERNAME")
        password = os.environ.get("REDDIT_BOT_PASSWORD")
        user_agent = os.environ.get("REDDIT_BOT_USER_AGENT", "GunDealsAlert Bot v1.0")

        if not all([client_id, client_secret, username, password]):
            print("  [bot] Missing REDDIT_BOT_* env vars — cannot post")
            return False

        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=user_agent,
        )

        post_id = deal.get("post_id", "")
        if not post_id:
            print(f"  [bot] No post_id for deal {deal['_id']}")
            return False

        submission = reddit.submission(id=post_id)
        submission.reply(comment_text)
        print(f"  [bot] Posted comment on {post_id}: {deal.get('title', '')[:50]}")
        return True

    except Exception as e:
        print(f"  [bot] Reddit post error: {e}")
        return False
