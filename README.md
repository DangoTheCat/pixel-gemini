# pixel-gemini

**Pixel 10 Pro Google One Gemini Automation & Telegram Bot**

A Telegram bot and automation framework that simulates a Google Pixel 10 Pro (Android 16) device using Chrome DevTools Protocol (CDP) Client Hints, handles Google Account authentication (including 2FA TOTP), and scans Google One for promotional offers.

---

## What's New & Upgraded (Community Synthesis)

This repository synthesizes the best working techniques and fixes from community forks (`51hcie`, `yhw5231`, `ndnhatvien`):

1. **CDP Client Hints Emulation (`Sec-CH-UA-Model`)**:
   - Injected real high-entropy values matching Google Pixel 10 Pro via Chrome DevTools Protocol.
   - Removed dead code in headers and aligned viewport (`427×952 @ 3.0 DPR`).
2. **Anti-Fingerprint Stealth Script**:
   - Overrides `navigator.webdriver` to `undefined`, sets mobile `maxTouchPoints = 5`, `platform = Linux armv8l`, and realistic hardware concurrency.
   - Removed embedded WebView User-Agent templates that triggered Google's *"Insecure browser"* block.
3. **Two-Factor Authentication (2FA TOTP)**:
   - Added automatic 6-digit OTP code generation via `pyotp` when provided with a Google Authenticator Secret Key.
4. **Proxy & Datacenter IP Mitigation**:
   - Added `PROXY_URL` support to route Selenium traffic through residential/mobile proxies.
5. **Session Profile Persistence**:
   - Optional `--user-data-dir` caching to preserve cookies and avoid repeated login challenges.
6. **Modernized Toolchain**:
   - Updated dependencies (Selenium 4.25+, python-telegram-bot, pyotp; removed obsolete `webdriver-manager`).

---

## Project Structure

```
pixel-gemini/
├── main.py               # Telegram bot entry point & conversation handlers
├── device_simulator.py   # Pixel 10 Pro specs, Luhn IMEI generator, CDP hints
├── google_automation.py  # Selenium CDP stealth driver, 2FA handler & offer scanner
├── config.py             # Configuration, URLs, and device constants
├── requirements.txt      # Python dependencies
└── README.md             # Documentation
```

---

## Features & Commands

| Command | Description |
|---|---|
| `/start` | Show welcome message and overview |
| `/login` | 3-step credential setup (Email → Password → Optional 2FA Secret Key) |
| `/check_offer` | Launch Pixel 10 Pro emulation and scan Google One for offers |
| `/get_link` | Retrieve the last discovered offer link |
| `/status` | View current session state, 2FA status, and simulated device profile |
| `/clear_session` | Delete cached credentials and Chrome profile |

---

## Setup & Running

### 1. Clone & create virtual environment

```bash
git clone https://github.com/DangoTheCat/pixel-gemini.git
cd pixel-gemini
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Set the following variables (or use `.env` / Replit Secrets):

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Token from [@BotFather](https://t.me/BotFather) |
| `PROXY_URL` | Optional | Proxy string (e.g., `http://user:pass@host:port`) |
| `HEADLESS` | Optional | `true` (default) or `false` for visible browser |
| `SAVE_SESSION_PROFILE` | Optional | `true` (default) to persist Chrome cookies |

### 3. Start the Bot

```bash
python main.py
```

---

## Technical Notice & Disclaimer

- **Play Integrity / Hardware Attestation**:
  Google One's official 12-month promotional trials (bundled with Pixel purchases) are gated by Google Play Services and require cryptographic hardware attestation (Titan M2 Key Attestation) tied to legitimate device purchase records. Browser-level emulation (even with CDP hints) cannot forge Titan M2 hardware keys.
- **Account Security**:
  Automating Google account authentication may trigger security challenges or temporary account lockouts. Use test accounts and never share sensitive personal credentials. This project is intended for educational research into browser anti-detection and device emulation.
