# GunDealAlerts Bot

A Reddit bot for [r/gundeals](https://www.reddit.com/r/gundeals/) that provides price context on deal posts. When a deal is posted, the bot checks its price history database and replies with useful data — how the price compares to the 90-day average, whether it's an all-time low, and links to full price history.

**Website:** [gundealalerts.com](https://www.gundealalerts.com/)

## What the bot does

1. **Price Check** — Compares a deal's price against 90-day history for the same product family (e.g., "Glock 19", "Holosun 507C"). Shows average, low, high, and standard deviation.

2. **Ammo CPR Check** — For ammunition deals, compares cost-per-round against 90-day caliber averages.

3. **Category Highlights** — If no price history exists for the specific product, shows the top deals this week in the same category as a fallback.

## Example comment

```
📊 Price Check (90-day, 57 deals)

|  | Price |
|---|---|
| This deal | **$379.00** |
| 90-day avg | $489.00 |
| 90-day low | $399.00 |
| 90-day high | $620.00 |

🔥 **22% below the 90-day average.**
This is **1.8 standard deviations below the mean** — unusually cheap for this product.

---
^(Price data from [GunDeals Alert](https://www.gundealalerts.com/) — tracking r/gundeals prices so you don't have to. | [Ammo Price Index](https://www.gundealalerts.com/ammo-prices))
```

## Rules the bot follows

- **Never comments on dealer posts** — only user-submitted deals
- **Only comments with high-confidence data** — minimum 3 historical deals for the same product
- **One comment per post, ever** — no edits, no duplicates
- **Rate limited** — max 6 comments per hour
- **Sanity checked** — skips commenting if the price is wildly different from history (likely a bad product match)
- **Waits before commenting** — 5-minute delay after post creation, never comments on posts older than 6 hours

## Architecture

```
r/gundeals post → Bot checks eligibility → Queries MongoDB price history
                                          → Generates markdown comment
                                          → Posts via Reddit API (PRAW)
```

The bot runs as a scheduled task alongside the main [gundealalerts.com](https://www.gundealalerts.com/) application. Price history is built from continuous monitoring of r/gundeals submissions.

## Bot code

- [`bot.py`](bot.py) — Main bot logic: finds eligible posts, generates comments, posts to Reddit
- [`bot_comment.py`](bot_comment.py) — Comment text generator with medal system and price context formatting

## Configuration

Environment variables:

| Variable | Description |
|----------|-------------|
| `REDDIT_BOT_CLIENT_ID` | Reddit API client ID |
| `REDDIT_BOT_CLIENT_SECRET` | Reddit API client secret |
| `REDDIT_BOT_USERNAME` | Bot Reddit username |
| `REDDIT_BOT_PASSWORD` | Bot Reddit password |
| `REDDIT_BOT_USER_AGENT` | User agent string (default: "GunDealsAlert Bot v1.0") |
| `MONGODB_URI` | MongoDB connection string |

## Tech stack

- Python 3.10
- [PRAW](https://praw.readthedocs.io/) (Reddit API wrapper)
- MongoDB (price history database)
- Hosted on Heroku

## Subreddits

This bot operates exclusively in **r/gundeals**.

## Contact

Bot account: [u/gundealalertsdotcom](https://www.reddit.com/user/gundealalertsdotcom)

## License

MIT
