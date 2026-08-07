"""
Configuration loader for the Pocket Option Signal Bot.
All secrets come from environment variables (set these in Railway,
never hardcode or paste tokens into chat).
"""
import os


class Config:
    # --- Telegram ---
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # channel/group to post signals to
    ADMIN_IDS = [
        int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
    ]

    # --- Pocket Option (read-only market data feed) ---
    PO_SSID = os.getenv("PO_SSID", "")  # session id used to open the websocket feed
    PO_DEMO = os.getenv("PO_DEMO", "true").lower() == "true"

    # --- Signal engine ---
    PAIRS = [p.strip() for p in os.getenv(
        "PAIRS",
        "AUDCAD_otc,EURUSD_otc,GBPJPY_otc,USDJPY_otc,AUDUSD_otc"
    ).split(",") if p.strip()]

    EXPIRATION_MINUTES = int(os.getenv("EXPIRATION_MINUTES", "5"))
    MARTINGALE_LEVELS = int(os.getenv("MARTINGALE_LEVELS", "3"))
    MARTINGALE_STEP_MINUTES = int(os.getenv("MARTINGALE_STEP_MINUTES", "5"))

    # Minimum confidence (0-100) required before a signal is posted.
    # Higher = fewer, more selective signals.
    MIN_CONFIDENCE = int(os.getenv("MIN_CONFIDENCE", "75"))

    # Minutes of lead time between "signal generated" and "entry time"
    ENTRY_LEAD_MINUTES = int(os.getenv("ENTRY_LEAD_MINUTES", "2"))

    # How often (seconds) the engine scans pairs for a new setup
    SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))

    @classmethod
    def validate(cls):
        missing = []
        if not cls.BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.CHAT_ID:
            missing.append("TELEGRAM_CHAT_ID")
        if not cls.PO_SSID:
            missing.append("PO_SSID")
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Set these in Railway's Variables tab, never in chat."
            )
