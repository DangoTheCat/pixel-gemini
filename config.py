"""
Configuration and constants for the Pixel 10 Pro Google One Gemini Bot.
"""

import os
from pathlib import Path

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# ── Device specs – Google Pixel 10 Pro (Android 16) ──────────────────────────
DEVICE_MODEL = "Pixel 10 Pro"
DEVICE_BRAND = "google"
DEVICE_MANUFACTURER = "Google"
ANDROID_VERSION = "16"
ANDROID_SDK = "36"
BUILD_ID = "AP3A.250905.001"  # Production build ID (user/release-keys)
CHROME_MAJOR_VERSION = 138
CHROME_VERSION = "138.0.7204.100"

# Viewport dimensions matching Google Pixel 10 Pro display (427x952 @ 3.0 DPR)
VIEWPORT_WIDTH = 427
VIEWPORT_HEIGHT = 952
PIXEL_RATIO = 3.0

# Pool of realistic Pixel 10 Pro mobile Chrome user-agent templates.
# (Embedded WebView templates with '; wv' removed to prevent Google 'Insecure app' triggers)
USER_AGENT_TEMPLATES = [
    (
        "Mozilla/5.0 (Linux; Android {android}; {model} Build/{build}) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/{chrome} Mobile Safari/537.36"
    ),
]

# ── Google URLs ───────────────────────────────────────────────────────────────
GMAIL_LOGIN_URL = "https://accounts.google.com/"
GOOGLE_ONE_URL = "https://one.google.com/"
GOOGLE_ONE_OFFERS_URL = "https://one.google.com/offers"
GOOGLE_ONE_BENEFITS_URL = "https://one.google.com/benefits"
GOOGLE_ONE_GEMINI_URL = "https://one.google.com/explore-plan/gemini-advanced"

# ── Gemini offer detection keywords ──────────────────────────────────────────
GEMINI_OFFER_KEYWORDS = [
    "gemini pro",
    "gemini advanced",
    "google ai pro",
    "12 month",
    "12-month",
    "1 year",
    "free trial",
    "activate",
    "get started",
    "claim offer",
    "redeem",
]

# ── Selenium / WebDriver ──────────────────────────────────────────────────────
WEBDRIVER_TIMEOUT = 30          # seconds – explicit wait
IMPLICIT_WAIT = 10              # seconds
PAGE_LOAD_TIMEOUT = 60          # seconds
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"

# ── Network & Proxy (Helps mitigate datacenter IP detection) ───────────────────
PROXY_URL = os.environ.get("PROXY_URL", "")

# ── Persistent Profiles / Session storage ─────────────────────────────────────
# Allows caching Chrome cookies to avoid repeated Google login prompts
BASE_DIR = Path(__file__).resolve().parent
CHROME_PROFILES_DIR = os.environ.get(
    "CHROME_PROFILES_DIR", str(BASE_DIR / "chrome_profiles")
)
SAVE_SESSION_PROFILE = os.environ.get("SAVE_SESSION_PROFILE", "true").lower() == "true"

# In-memory dict keyed by Telegram chat_id.
# Values: {"email": ..., "password": ..., "totp_secret": ..., "device": <DeviceProfile>, "offer_link": ...}
SESSION_STORE: dict = {}

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
