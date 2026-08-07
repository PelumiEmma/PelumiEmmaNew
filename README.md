# Pocket Option Manual Signal Bot

Posts formatted trade signals (like your AUD/CAD example) to a Telegram
chat. You execute the trades manually on Pocket Option - this bot never
places trades itself.

## Files
- `config.py` - loads settings from environment variables
- `indicators.py` - EMA, RSI, MACD (no external TA library needed)
- `signal_engine.py` - 4-factor scoring: EMA trend + MACD momentum + RSI
  positioning on the entry timeframe, plus a 5-minute higher-timeframe
  trend confirmation. Tags each signal with a tier (🔥 High / ✅ Medium /
  ⚠️ Low) based on score
- `pocket_client.py` - market data adapter. Ships with `SimulatedFeed`
  (random walk, for testing) and a `PocketOptionFeed` stub for you to
  wire up your real connection
- `storage.py` - SQLite log of every signal sent and its reported outcome
- `bot.py` - Telegram bot: scans pairs on a timer, formats and posts
  signals, tracks results, auto-restarts on crash
- `.env.example` - variable names to set in Railway (never in chat)

## Message format
```
AUD/CAD 🇨🇦 OTC
🕘 Expiration 5M
⏺️ Entry at 13:30
🟩 BUY
🔼 Martingale levels
1️⃣ level at 13:35
2️⃣ level at 13:40
3️⃣ level at 13:45

✅ Medium (80%)
ID #14 - report with /result win or /result loss
```

## Tracking accuracy
After each trade resolves, report it back:
```
/result win
/result loss
/result loss 14      (target a specific signal ID instead of the latest)
```
Then `/stats` shows real win rate overall, per pair, and per confidence
tier — so you can see whether 🔥 High signals are actually outperforming
✅ Medium ones, and adjust `MIN_CONFIDENCE` based on real data instead of
guessing.

## Running locally (with simulated data)
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id
export PO_SSID=placeholder   # not used yet with SimulatedFeed
python bot.py
```
Commands in Telegram: `/start`, `/status`, `/scan` (force a scan now),
`/pause`, `/resume`, `/result win|loss [id]`, `/stats`.

## Wiring up the real Pocket Option feed
`pocket_client.py` has a `PocketOptionFeed` class with two `TODO` blocks.
Since you already built WebSocket connectivity for MONEYBOT AI, drop that
client's candle-fetch call in there - this bot only needs a list of recent
closing prices per pair, it doesn't care how you get them. Then in `bot.py`,
swap:
```python
feed = SimulatedFeed()
```
for:
```python
feed = PocketOptionFeed(ssid=Config.PO_SSID, demo=Config.PO_DEMO)
```

## Deploying to Railway
1. Push this folder to a GitHub repo (don't commit `.env` - only `.env.example`)
2. In Railway: New Project -> Deploy from GitHub repo
3. Go to Variables tab and paste in your real `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`, `PO_SSID`, etc. - set them there directly, never
   share tokens in chat (that's what revoked your last bot's token)
4. Railway will use the `Procfile` (`worker: python bot.py`) automatically
5. If you push new code and it doesn't take effect, do a manual redeploy
   from the Railway dashboard to clear the build cache
6. Note: `signals.db` lives on Railway's local disk, which resets on
   redeploy. Fine for short-term stats; if you want history to survive
   redeploys long-term, attach a Railway volume mounted at the bot's
   working directory

## Tuning signal frequency
- `MIN_CONFIDENCE` (default 75) - raise for fewer/higher-conviction
  signals, lower for more frequent ones
- `SCAN_INTERVAL_SECONDS` - how often each pair is re-checked
- `PAIRS` - comma-separated list of OTC pairs to watch

## Honest limitation
This engine trades on EMA trend + MACD momentum + RSI positioning
agreement. It's a real, defensible technical setup, but 5-minute OTC
binary pairs are short-timeframe, broker-generated feeds with a built-in
house edge - no indicator combination gives a guaranteed win rate. Treat
`MIN_CONFIDENCE` as a selectivity dial, not an accuracy promise, and size
your martingale steps with that in mind.
