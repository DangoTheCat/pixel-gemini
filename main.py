"""
Telegram Bot entry point for the Pixel 10 Pro Google One Gemini Bot.

Commands:
  /start         – Show welcome message and available commands
  /login         – Begin credential flow (Email → Password → Optional 2FA Secret)
  /check_offer   – Run Google One automation with CDP stealth and look for offers
  /get_link      – Show the last captured offer link
  /status        – Show current session status and simulated device profile
  /clear_session – Reset credentials and active session
"""

import html
import logging
import os
import shutil
import sys
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
from device_simulator import create_device_profile
from google_automation import GoogleAutomationError, check_gemini_offer

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
AWAIT_EMAIL, AWAIT_PASSWORD, AWAIT_TOTP = range(3)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session(chat_id: int) -> dict:
    """Return (creating if absent) the session dict for *chat_id*."""
    if chat_id not in config.SESSION_STORE:
        config.SESSION_STORE[chat_id] = {}
    return config.SESSION_STORE[chat_id]


# ── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message with command menu and disclaimer."""
    await update.message.reply_text(
        "🤖 *Pixel 10 Pro Google One Bot*\n\n"
        "This bot simulates a Google Pixel 10 Pro (Android 16) device with "
        "CDP Client Hints, attempts Google account login (with 2FA TOTP support), "
        "and checks Google One for Gemini promotional offers.\n\n"
        "📋 *Available Commands:*\n"
        "• /login – Enter your Gmail credentials & optional 2FA key\n"
        "• /check\\_offer – Run automation and search for Gemini offer\n"
        "• /get\\_link – Show the last captured offer link\n"
        "• /status – View current session & device info\n"
        "• /clear\\_session – Reset saved session & device profile\n\n"
        "⚠️ *Technical Notice:* Hardware-bundled Google One promos normally require "
        "physical device attestation (Titan M2 Key Attestation via Play Services). "
        "This tool is provided for educational research into browser emulation & Client Hints.",
        parse_mode="Markdown",
    )


# ── /login conversation ───────────────────────────────────────────────────────

async def login_start(update: Update,
                      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the login conversation – ask for email."""
    await update.message.reply_text(
        "📧 Please enter your Gmail address:\n"
        "_(Send /cancel anytime to abort)_",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return AWAIT_EMAIL


async def login_email(update: Update,
                      context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the email and ask for password."""
    email = update.message.text.strip()
    context.user_data["pending_email"] = email
    await update.message.reply_text(
        f"✅ Email received: `{email}`\n\n🔒 Now enter your password:",
        parse_mode="Markdown",
    )
    return AWAIT_PASSWORD


async def login_password(update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store password, delete user's password message, and ask for optional 2FA secret."""
    password = update.message.text.strip()
    context.user_data["pending_password"] = password

    # Delete the message containing the plaintext password for security
    try:
        await update.message.delete()
    except Exception:
        pass

    # Ask for 2FA TOTP secret key
    reply_keyboard = [["/skip"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "🔑 *Two-Factor Authentication (Optional):*\n\n"
        "If your Google account has 2-Step Verification (Google Authenticator) enabled, "
        "enter your 16/32-character TOTP Secret Key so the bot can generate 2FA codes automatically.\n\n"
        "If your account does not use 2FA or you prefer to approve on your phone, click /skip:",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    return AWAIT_TOTP


async def login_totp(update: Update,
                     context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save credentials, generate new device profile, and conclude login flow."""
    chat_id = update.effective_chat.id
    totp_text = update.message.text.strip()

    totp_secret = ""
    if totp_text != "/skip":
        totp_secret = totp_text

    email = context.user_data.pop("pending_email", "")
    password = context.user_data.pop("pending_password", "")

    # Delete message if it contained a secret key
    if totp_secret:
        try:
            await update.message.delete()
        except Exception:
            pass

    session = _get_session(chat_id)
    session["email"] = email
    session["password"] = password
    session["totp_secret"] = totp_secret
    session["device"] = create_device_profile()
    session["offer_link"] = None

    totp_status = "Configured (Auto-OTP enabled)" if totp_secret else "None (Manual / Prompt)"

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "✅ *Credentials saved* and a new Pixel 10 Pro profile has been generated!\n\n"
            f"• Account: `{email}`\n"
            f"• 2FA Handler: {totp_status}\n\n"
            + session["device"].summary()
            + "\n\nUse /check\\_offer to search for Google One offers."
        ),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def login_cancel(update: Update,
                       context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the login conversation."""
    context.user_data.pop("pending_email", None)
    context.user_data.pop("pending_password", None)
    await update.message.reply_text(
        "❌ Login cancelled.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ── /check_offer ──────────────────────────────────────────────────────────────

async def check_offer(update: Update,
                      context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run Google One automation and report the result."""
    chat_id = update.effective_chat.id
    session = _get_session(chat_id)

    if not session.get("email") or not session.get("password"):
        await update.message.reply_text(
            "⚠️ No credentials found. Please use /login first."
        )
        return

    device = session.get("device")
    if not device:
        device = create_device_profile()
        session["device"] = device

    await update.message.reply_text(
        "⏳ Launching Pixel 10 Pro simulation with CDP Client Hints…\n"
        "Navigating to Google One and checking offers (may take 30–60s)."
    )

    try:
        offer_link = check_gemini_offer(
            session["email"],
            session["password"],
            device,
            totp_secret=session.get("totp_secret", ""),
        )
    except GoogleAutomationError as exc:
        await update.message.reply_text(
            f"❌ <b>Google Automation Block:</b> {html.escape(str(exc))}",
            parse_mode="HTML",
        )
        return
    except Exception as exc:
        logger.exception("Unexpected error in check_offer for chat %s", chat_id)
        await update.message.reply_text(f"❌ An unexpected error occurred: {exc}")
        return

    if offer_link:
        session["offer_link"] = offer_link
        await update.message.reply_text(
            "🎉 <b>Gemini / Google One Offer Found!</b>\n\n"
            f"Link ưu đãi: {html.escape(offer_link)}\n\n"
            "<i>Use /get_link to retrieve this link again.</i>",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "ℹ️ <b>Không tìm thấy link ưu đãi hợp lệ cho tài khoản này.</b>\n\n"
            "Bot chỉ trích xuất các link ưu đãi thực sự có mã kích hoạt "
            "(dạng <code>https://one.google.com/partner-eft-onboard/...</code>).\n\n"
            "<i>Lưu ý:</i> Ưu đãi phần cứng Google One / Gemini 12 tháng yêu cầu "
            "tài khoản và thiết bị thỏa mãn điều kiện khuyến mãi (Pixel Offer / Play Integrity).",
            parse_mode="HTML",
        )


# ── /get_link ─────────────────────────────────────────────────────────────────

async def get_link(update: Update,
                   context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return the last captured offer link for this session."""
    chat_id = update.effective_chat.id
    session = _get_session(chat_id)
    link = session.get("offer_link")

    if link:
        await update.message.reply_text(
            f"🔗 Link ưu đãi: {html.escape(link)}",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            "ℹ️ Chưa có link ưu đãi nào được ghi nhận. "
            "Dùng /check_offer để kiểm tra ưu đãi.",
            parse_mode="HTML",
        )


# ── /status ───────────────────────────────────────────────────────────────────

async def status(update: Update,
                 context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current session and device profile summary."""
    chat_id = update.effective_chat.id
    session = _get_session(chat_id)

    if not session:
        await update.message.reply_text(
            "ℹ️ No active session. Use /login to get started."
        )
        return

    email = session.get("email", "—")
    has_creds = bool(session.get("email") and session.get("password"))
    has_totp = bool(session.get("totp_secret"))
    offer_link = session.get("offer_link")
    device = session.get("device")

    lines = [
        "📊 *Session Status*\n",
        f"Account: `{email}`",
        f"Credentials loaded: {'✅' if has_creds else '❌'}",
        f"2FA Secret set: {'✅' if has_totp else '❌ (Phone Prompt)'}",
        f"Offer link captured: {'✅' if offer_link else '❌'}",
    ]

    if device:
        lines.append("\n" + device.summary())

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


# ── /clear_session ────────────────────────────────────────────────────────────

async def clear_session(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear session data and cached Chrome profile for this chat."""
    chat_id = update.effective_chat.id
    session = config.SESSION_STORE.pop(chat_id, {})
    email = session.get("email")

    if email and config.SAVE_SESSION_PROFILE:
        import re
        clean_email = re.sub(r"[^a-zA-Z0-9]", "_", email)
        profile_path = os.path.join(config.CHROME_PROFILES_DIR, f"profile_{clean_email}")
        if os.path.exists(profile_path):
            try:
                shutil.rmtree(profile_path)
            except Exception as exc:
                logger.warning("Could not delete profile %s: %s", profile_path, exc)

    await update.message.reply_text("🧹 Session cleared. All stored credentials and profiles were removed.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and inform the user if possible."""
    logger.error("Exception while handling an update: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred while processing your request. Please try again."
            )
        except Exception:
            pass


# ── Application setup ─────────────────────────────────────────────────────────

def main() -> None:
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Set it in your environment or secrets and restart."
        )
        sys.exit(1)

    app = Application.builder().token(token).build()
    app.add_error_handler(error_handler)

    # /login conversation handler with 2FA TOTP support
    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", login_start)],
        states={
            AWAIT_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_email)
            ],
            AWAIT_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)
            ],
            AWAIT_TOTP: [
                CommandHandler("skip", login_totp),
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_totp),
            ],
        },
        fallbacks=[CommandHandler("cancel", login_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(login_conv)
    app.add_handler(CommandHandler("check_offer", check_offer))
    app.add_handler(CommandHandler("get_link", get_link))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("clear_session", clear_session))

    logger.info("Bot is running. Press Ctrl-C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
