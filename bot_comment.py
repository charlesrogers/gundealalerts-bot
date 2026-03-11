"""
Bot comment generator — builds informational comments for r/gundeals posts.
Uses product fingerprint data, price history, and medal system.
"""
from datetime import datetime, timedelta


def _deal_rating(pct_vs_median, median_price, deal_count, is_all_time_low=False):
    """Return single-line rating with fires, % vs median, and median price."""
    median_str = f"${median_price:.0f} median across {deal_count} deals"
    pct_abs = abs(pct_vs_median)
    if is_all_time_low or pct_vs_median <= -25:
        return f"🔥🔥🔥🔥🔥/5 — **{pct_abs:.0f}% below** the {median_str}"
    elif pct_vs_median <= -15:
        return f"🔥🔥🔥🔥/5 — **{pct_abs:.0f}% below** the {median_str}"
    elif pct_vs_median <= -5:
        return f"🔥🔥🔥/5 — **{pct_abs:.0f}% below** the {median_str}"
    elif pct_vs_median <= 0:
        return f"🔥🔥/5 — about typical ({median_str})"
    elif pct_vs_median <= 5:
        return f"🔥/5 — about typical ({median_str})"
    elif pct_vs_median <= 10:
        return None
    else:
        return f"⚠️ **{pct_abs:.0f}% above** the {median_str} — this might be a more attractive feature model or have extra add-ons"


def generate_bot_comment(deal, price_context=None, medal_info=None):
    """
    Generate a Reddit comment for a deal.

    Args:
        deal: Alert document from MongoDB
        price_context: Output from generate_price_context() or None
        medal_info: Dict with category_percentile, deal_medal, flair_category

    Returns:
        dict: {
            'comment_text': str (Reddit markdown),
            'has_useful_data': bool,
            'data_points': list of str (what data was included)
        }
    """
    lines = []
    data_points = []
    product = deal.get('product', {})
    title = deal.get('title', '')
    price = deal.get('price') or product.get('price')
    family = product.get('family')
    caliber = product.get('caliber')
    cpr = product.get('cpr')
    is_ammo = product.get('product_type') == 'ammo'

    # Medal line
    if medal_info:
        percentile = medal_info.get('category_percentile')
        medal = medal_info.get('deal_medal')
        category = medal_info.get('flair_category', 'deal')
        if medal and percentile:
            medal_emoji = {'gold': '🥇', 'silver': '🥈', 'bronze': '🥉'}.get(medal, '')
            lines.append(f"{medal_emoji} **Top {100 - int(percentile)}% {category} deal** based on community engagement")
            data_points.append('medal')

    # Price context lines
    if price_context and price:
        deal_count = price_context.get('deal_count', 0)
        avg_price = price_context.get('avg_price')
        min_price = price_context.get('min_price')
        pct_vs_avg = price_context.get('pct_vs_avg')
        is_all_time_low = price_context.get('is_all_time_low', False)

        # Combined rating + price context line
        if pct_vs_avg is not None and deal_count >= 3:
            rating = _deal_rating(pct_vs_avg, avg_price, deal_count, is_all_time_low)
            if rating:
                lines.append(rating)
                if is_all_time_low:
                    lines.append(f"📉 **All-time low** for {family}")
                data_points.append('rating')

        # Recent alternatives table (replaces simple price trend)
        history = price_context.get('price_history', [])
        # Filter out the current deal from history
        current_post_id = deal.get('post_id')
        alternatives = [h for h in history if h.get('post_id') != current_post_id][:10]
        if len(alternatives) >= 2 and family:
            table_lines = [f"**Recent alternatives for {family}:**", "",
                          "| Date | Price | Deal |",
                          "|:-----|------:|:-----|"]
            for h in alternatives:
                d = h.get('date')
                date_str = d.strftime('%b %d, %Y') if isinstance(d, datetime) else '?'
                h_price = h.get('price', 0)
                title_short = h.get('title', '')[:60]
                pid = h.get('post_id', '')
                if pid:
                    link = f"[{title_short}](https://reddit.com/r/gundeals/comments/{pid})"
                else:
                    link = title_short
                table_lines.append(f"| {date_str} | ${h_price:.0f} | {link} |")
            # Join table as single block so \n\n join doesn't break it
            lines.append('\n'.join(table_lines))
            data_points.append('alternatives')

    # Ammo CPR context
    if is_ammo and cpr and caliber:
        cpr_cents = cpr * 100 if cpr < 1 else cpr
        lines.append(f"💰 **{cpr_cents:.1f}¢/rd** for {caliber}")
        data_points.append('cpr')

    # Footer — always present, links to price history
    if family:
        family_slug = product.get('family_slug', '')
        if family_slug:
            lines.append(f"")
            lines.append(f"[Full price history for {family}](https://www.gundealalerts.com/product/{family_slug}) | [Set up alerts](https://www.gundealalerts.com/)")
            data_points.append('link')

    # Only return if we have something useful to say
    has_useful = len(data_points) >= 2  # Need at least medal/price + link
    comment_text = "\n\n".join(lines) if lines else ""

    return {
        'comment_text': comment_text,
        'has_useful_data': has_useful,
        'data_points': data_points,
    }
