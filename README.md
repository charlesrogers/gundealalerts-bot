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

## Reddit API & Policy Compliance

This bot is designed from the ground up to comply with Reddit's [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/29979188024852-Reddit-Data-API-Wiki), [Data API Terms](https://www.redditinc.com/policies/data-api-terms), and [Bot Guidelines](https://support.reddithelp.com/hc/en-us/articles/29979188024852-Reddit-Data-API-Wiki#h_01J6Y2YQ29BA5SY07CBYXWCR7R):

### Data access

- **All data is accessed exclusively through Reddit's official Data API via [PRAW](https://praw.readthedocs.io/)** (Python Reddit API Wrapper). No scraping, crawling, or unofficial data collection methods are used.
- **Authenticates via OAuth2** as required by the API terms.
- **Respects rate limits** — the bot self-limits to well under 60 requests/minute and monitors `X-Ratelimit-*` response headers. The bot polls new posts only a few times per day.
- **Uses a descriptive User-Agent** following the required format: `python:com.gundealalerts.bot:v1.0 (by /u/gundealalertsdotcom)`

### Bot behavior

- **Clearly identified as a bot** — the account name, profile, and comment footer all disclose bot status.
- **Single subreddit only** — operates exclusively in r/gundeals, accessing only the data it needs.
- **No spam** — max 6 comments per hour, one comment per post ever, 5-minute delay before commenting, no duplicate/similar content across posts.
- **No manipulation** — the bot never votes, never sends DMs, never circumvents bans or blocks.
- **No private communications** — the bot only posts public comments.

### Data handling

- **No user data is collected or stored** — the bot reads only public post metadata (title, price, URL, score, flair). No usernames, comment text, or private data is accessed or retained.
- **No scraping** — the bot does not bulk-export or scrape Reddit data. It reads individual submissions via the standard API as they appear.
- **No AI/ML training** — Reddit data is not used to train any models. Price history is simple statistical aggregation (averages, percentiles).
- **No commercialization** — the companion website (gundealalerts.com) is free with no ads, no affiliate links, and no paid tiers. Reddit data is not sold, licensed, or shared with third parties.
- **No re-identification** — the bot does not process, store, or infer any information about Reddit users.

### Non-commercial use

- The tool is **free and non-commercial** — no ads, no affiliate links, no paywalls, no paid tiers, no monetization of any kind.
- Reddit data is used solely to provide helpful price context back to the r/gundeals community.

## Rules the bot follows

- **Never comments on dealer posts** — only user-submitted deals
- **Only comments with high-confidence data** — minimum 3 historical deals for the same product
- **One comment per post, ever** — no edits, no duplicates
- **Rate limited** — max 6 comments per hour, well within API rate limits
- **Sanity checked** — skips commenting if the price is wildly different from history (likely a bad product match)
- **Waits before commenting** — 5-minute delay after post creation, never comments on posts older than 6 hours

## Architecture

```
r/gundeals post → Reddit API (PRAW/OAuth2) → Bot checks eligibility
                                             → Queries MongoDB price history
                                             → Generates markdown comment
                                             → Posts reply via Reddit API
```

The bot runs as a scheduled task alongside the [gundealalerts.com](https://www.gundealalerts.com/) application. Price history is built exclusively from data accessed through the official Reddit API.

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
| `REDDIT_BOT_USER_AGENT` | User agent string (default: `python:com.gundealalerts.bot:v1.0 (by /u/gundealalertsdotcom)`) |
| `MONGODB_URI` | MongoDB connection string |

## Tech stack

- Python 3.10
- [PRAW](https://praw.readthedocs.io/) (Reddit API wrapper) — official OAuth2 authentication
- MongoDB (price history database)
- Hosted on Heroku

## Subreddits

This bot operates exclusively in **r/gundeals**.

## Contact

Bot account: [u/gundealalertsdotcom](https://www.reddit.com/user/gundealalertsdotcom)

## License

MIT
