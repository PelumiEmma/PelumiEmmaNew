"""
Pocket Option Manual Signal Bot.

Scans configured OTC pairs on a timer, runs them through the signal engine
(with higher-timeframe confirmation), and posts a formatted signal to your
Telegram chat/channel for you to execute manually on Pocket Option. This
bot never places trades itself.

Report outcomes with /result win or /result loss so /stats can show real
accuracy per pair and per confidence tier.

Run:  python bot.py
Env vars are read via config.py - see .env.example.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import Config
from pocket_client import SimulatedFeed, PocketOptionFeed, BaseFeed
from signal_engine import SignalEngine
import storage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("signalbot")

# --- Currency flag emoji for message formatting ---
FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "AUD": "🇦🇺",
    "CAD": "🇨🇦", "CHF": "🇨🇭", "NZD": "🇳🇿", "CNY": "🇨🇳", "INR": "🇮🇳",
}

HIGHER_TIMEFRAME_SECONDS = 300  # 5-minute trend confirmation


def format_pair(raw_pair: str) -> str:
    """AUDCAD_otc -> ('AUD/CAD', '🇨🇦')"""
    code = raw_pair.replace("_otc", "").upper()
    base, quote = code[:3], code[3:6]
    display = f"{base}/{quote}"
    flag = FLAGS.get(quote, FLAGS.get(base, ""))
    return display, flag


def build_signal_message(signal_id: int, pair_raw: str, direction: str, confidence: int,
                          tier: str, entry_time: datetime, expiration_min: int,
                          martingale_levels: int, martingale_step_min: int) -> str:
    display, flag = format_pair(pair_raw)
    is_otc = "otc" in pair_raw.lower()
    dir_emoji = "🟩 BUY" if direction == "BUY" else "🟥 SELL"

    lines = [
        f"{display} {flag}{' OTC' if is_otc else ''}",
        f"🕘 Expiration {expiration_min}M",
        f"⏺️ Entry at {entry_time.strftime('%H:%M')}",
        dir_emoji,
    ]

    if martingale_levels > 0:
        lines.append("🔼 Martingale levels")
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for i in range(martingale_levels):
            level_time = entry_time + timedelta(minutes=martingale_step_min * (i + 1))
            emoji = number_emojis[i] if i < len(number_emojis) else f"{i+1}."
            lines.append(f"{emoji} level at {level_time.strftime('%H:%M')}")

    lines.append(f"\n{tier} ({confidence}%)")
    lines.append(f"ID #{signal_id} - report with /result win or /result loss")
    return "\n".join(lines)


class SignalBotApp:
    def __init__(self, feed: BaseFeed):
        self.feed = feed
        self.engine = SignalEngine(min_confidence=Config.MIN_CONFIDENCE)
        self.running = False
        self._last_signal_at = {}  # pair -> datetime, avoid spamming same pair

    async def scan_once(self, app: Application, chat_id: str):
        for pair in Config.PAIRS:
            try:
                closes = await self.feed.get_recent_closes(
                    pair, timeframe_seconds=60, count=60
                )
                htf_closes = await self.feed.get_recent_closes(
                    pair, timeframe_seconds=HIGHER_TIMEFRAME_SECONDS, count=30
                )
                signal = self.engine.evaluate(pair, closes, htf_closes)
            except Exception as e:
                log.warning(f"Scan failed for {pair}: {e}")
                continue

            if not signal:
                continue

            # Don't re-fire the same pair within one full signal cycle
            cycle_seconds = 60 * (Config.ENTRY_LEAD_MINUTES +
                                   Config.MARTINGALE_LEVELS * Config.MARTINGALE_STEP_MINUTES)
            last_at = self._last_signal_at.get(pair)
            if last_at and (datetime.now() - last_at).total_seconds() < cycle_seconds:
                continue

            entry_time = datetime.now() + timedelta(minutes=Config.ENTRY_LEAD_MINUTES)
            signal_id = storage.save_signal(
                pair, signal.direction, signal.confidence, signal.tier, entry_time
            )
            msg = build_signal_message(
                signal_id, pair, signal.direction, signal.confidence, signal.tier,
                entry_time, Config.EXPIRATION_MINUTES, Config.MARTINGALE_LEVELS,
                Config.MARTINGALE_STEP_MINUTES,
            )
            await app.bot.send_message(chat_id=chat_id, text=msg)
            self._last_signal_at[pair] = datetime.now()
            log.info(f"Signal #{signal_id} sent: {pair} {signal.direction} ({signal.confidence}%)")

    async def scan_loop(self, app: Application):
        while True:
            try:
                if self.running:
                    await self.scan_once(app, Config.CHAT_ID)
            except Exception as e:
                # Never let one bad scan cycle kill the loop
                log.error(f"scan_loop error (continuing): {e}")
            await asyncio.sleep(Config.SCAN_INTERVAL_SECONDS)


bot_app_state = None  # set in main()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Signal bot online. Commands:\n"
        "/scan - run one scan cycle now\n"
        "/status - show engine status\n"
        "/resume - resume auto-scanning\n"
        "/pause - pause auto-scanning\n"
        "/result win|loss [id] - report a trade outcome\n"
        "/stats - show accuracy by pair and confidence tier"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = bot_app_state
    status = "running" if state.running else "paused"
    await update.message.reply_text(
        f"Status: {status}\n"
        f"Pairs: {', '.join(Config.PAIRS)}\n"
        f"Min confidence: {Config.MIN_CONFIDENCE}%\n"
        f"Scan interval: {Config.SCAN_INTERVAL_SECONDS}s\n"
        f"Higher-timeframe confirmation: {HIGHER_TIMEFRAME_SECONDS // 60}M"
    )


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Scanning now...")
    await bot_app_state.scan_once(context.application, str(update.effective_chat.id))


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_app_state.running = False
    await update.message.reply_text("Auto-scanning paused.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_app_state.running = True
    await update.message.reply_text("Auto-scanning resumed.")


async def cmd_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0].lower() not in ("win", "loss"):
        await update.message.reply_text(
            "Usage: /result win  or  /result loss  (optionally add a signal ID: /result loss 12)"
        )
        return

    outcome = args[0].lower()
    if len(args) > 1 and args[1].isdigit():
        signal_id = int(args[1])
    else:
        signal_id = storage.get_last_unresolved_signal_id()
        if signal_id is None:
            await update.message.reply_text("No pending signals to resolve.")
            return

    ok = storage.resolve_signal(signal_id, outcome)
    if ok:
        emoji = "✅" if outcome == "win" else "❌"
        await update.message.reply_text(f"{emoji} Signal #{signal_id} marked as {outcome}.")
    else:
        await update.message.reply_text(
            f"Signal #{signal_id} not found or already resolved."
        )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = storage.get_stats()
    overall = stats["overall"]
    wins, losses = overall.get("win", 0), overall.get("loss", 0)
    total = wins + losses
    win_rate = f"{(wins / total * 100):.1f}%" if total else "n/a"

    lines = [
        f"📊 Overall: {wins}W / {losses}L ({win_rate}) - {stats['pending']} pending",
        "",
        "By pair:",
    ]

    per_pair = {}
    for pair, outcome, count in stats["per_pair"]:
        per_pair.setdefault(pair, {"win": 0, "loss": 0})[outcome] = count
    for pair, rec in per_pair.items():
        w, l = rec.get("win", 0), rec.get("loss", 0)
        t = w + l
        rate = f"{(w / t * 100):.0f}%" if t else "n/a"
        display, _ = format_pair(pair)
        lines.append(f"  {display}: {w}W/{l}L ({rate})")

    lines.append("")
    lines.append("By confidence tier:")
    per_tier = {}
    for tier, outcome, count in stats["per_tier"]:
        per_tier.setdefault(tier, {"win": 0, "loss": 0})[outcome] = count
    for tier, rec in per_tier.items():
        w, l = rec.get("win", 0), rec.get("loss", 0)
        t = w + l
        rate = f"{(w / t * 100):.0f}%" if t else "n/a"
        lines.append(f"  {tier}: {w}W/{l}L ({rate})")

    await update.message.reply_text("\n".join(lines))


async def post_init(app: Application):
    asyncio.create_task(bot_app_state.scan_loop(app))


def main():
    global bot_app_state
    Config.validate()
    storage.init_db()

    # Swap SimulatedFeed for PocketOptionFeed once you've wired up
    # your real Pocket Option client in pocket_client.py
    feed = SimulatedFeed()
    bot_app_state = SignalBotApp(feed)
    bot_app_state.running = True

    application = Application.builder().token(Config.BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("scan", cmd_scan))
    application.add_handler(CommandHandler("pause", cmd_pause))
    application.add_handler(CommandHandler("resume", cmd_resume))
    application.add_handler(CommandHandler("result", cmd_result))
    application.add_handler(CommandHandler("stats", cmd_stats))

    log.info("Starting signal bot (polling)...")
    application.run_polling()


if __name__ == "__main__":
    # Outer retry loop: if something unexpected crashes the bot (network
    # blip, Telegram hiccup), restart instead of dying and needing a
    # manual Railway restart. Railway's own restart policy is a second
    # layer of defense on top of this.
    import time
    backoff = 5
    while True:
        try:
            main()
            break  # main() only returns on a clean shutdown
        except Exception as e:
            log.error(f"Bot crashed: {e}. Restarting in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)  # cap at 5 min
