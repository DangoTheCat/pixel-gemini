"""
Configuration and constants for the Pixel 10 Pro Google One Gemini Bot.
"""

import os
from pathlib import Path

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# ── Device specs – Google Pixel (Pixel 9 Pro / Pixel 10 Pro) ─────────────────
DEVICE_MODEL = os.environ.get("DEVICE_MODEL", "Pixel 9 Pro")
DEVICE_BRAND = "google"
DEVICE_MANUFACTURER = "Google"

if "10" in DEVICE_MODEL:
    ANDROID_VERSION = os.environ.get("ANDROID_VERSION", "16")
    ANDROID_SDK = os.environ.get("ANDROID_SDK", "36")
    BUILD_ID = os.environ.get("BUILD_ID", "AP3A.250905.001")
    VIEWPORT_WIDTH = 427
    VIEWPORT_HEIGHT = 952
    PIXEL_RATIO = 3.0
else:
    # Pixel 9 Pro specs (official Google hardware with active 1-year Gemini promo)
    ANDROID_VERSION = os.environ.get("ANDROID_VERSION", "15")
    ANDROID_SDK = os.environ.get("ANDROID_SDK", "35")
    BUILD_ID = os.environ.get("BUILD_ID", "AP4A.241205.013")
    VIEWPORT_WIDTH = 412
    VIEWPORT_HEIGHT = 923
    PIXEL_RATIO = 3.0

CHROME_MAJOR_VERSION = 138
CHROME_VERSION = "138.0.7204.100"

# Pool of realistic Pixel mobile Chrome user-agent templates.
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
GOOGLE_ONE_AI_URL = "https://one.google.com/ai"

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
    "partner-eft-onboard",
    "nhận ưu đãi",
    "đổi ưu đãi",
    "ưu đãi",
    "kích hoạt",
    "dùng thử",
    "12 tháng",
    "1 năm",
    "nhận ngay",
]

# Action keywords specifically for clicking offer redemption CTA buttons / cards
OFFER_CTA_KEYWORDS = [
    "claim offer",
    "claim",
    "redeem offer",
    "redeem",
    "get offer",
    "get perk",
    "get benefit",
    "activate offer",
    "claim benefit",
    "nhận ưu đãi",
    "đổi ưu đãi",
    "nhận quà",
    "nhận ngay",
    "kích hoạt ưu đãi",
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
