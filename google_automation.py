"""
Google One automation using Selenium with CDP Stealth, Client Hints, and 2FA TOTP support.

Incorporates modern anti-fingerprinting techniques, Sec-CH-UA Client Hints,
persistent session profile support, and Google Authenticator (TOTP) automation.
"""

import logging
import os
import re
import shutil
import time
from typing import Optional
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import pyotp

import config
from device_simulator import DeviceProfile

logger = logging.getLogger(__name__)


# ── Driver factory ────────────────────────────────────────────────────────────

def _build_driver(profile: DeviceProfile, email: str = "") -> webdriver.Chrome:
    """
    Return a Chrome WebDriver configured with:
    - Accurate mobile viewport for Pixel 10 Pro
    - CDP User-Agent Client Hints (Sec-CH-UA-Model, Sec-CH-UA-Platform)
    - Anti-bot stealth overrides (navigator.webdriver, plugins, userAgentData)
    - Optional persistent profile directory to preserve login sessions
    """
    options = Options()

    if config.HEADLESS:
        options.add_argument("--headless=new")

    # Core container & stability flags
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=en-US")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument(f"--window-size={config.VIEWPORT_WIDTH},{config.VIEWPORT_HEIGHT}")
    options.add_argument(f"--user-agent={profile.user_agent}")

    # Eager page loading prevents SPA hanging
    options.page_load_strategy = "eager"

    # Optional proxy routing (mitigates datacenter IP flagging by Google)
    if config.PROXY_URL:
        options.add_argument(f"--proxy-server={config.PROXY_URL}")
        logger.info("Using proxy: %s", config.PROXY_URL)

    # Optional persistent profile mapped to email
    if email and config.SAVE_SESSION_PROFILE:
        clean_email = re.sub(r"[^a-zA-Z0-9]", "_", email)
        profile_path = os.path.abspath(
            os.path.join(config.CHROME_PROFILES_DIR, f"profile_{clean_email}")
        )
        os.makedirs(profile_path, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_path}")
        logger.info("Using persistent Chrome profile: %s", profile_path)

    # Mobile emulation
    mobile_emulation = {
        "deviceMetrics": {
            "width": config.VIEWPORT_WIDTH,
            "height": config.VIEWPORT_HEIGHT,
            "pixelRatio": config.PIXEL_RATIO,
            "touch": True,
        },
        "userAgent": profile.user_agent,
    }
    options.add_experimental_option("mobileEmulation", mobile_emulation)

    # Suppress default automation flags
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Use Chromium binary if available on Linux
    chromium_bin = shutil.which("chromium") or shutil.which("chromium-browser")
    if chromium_bin:
        options.binary_location = chromium_bin

    service = Service()
    driver = webdriver.Chrome(service=service, options=options)

    # ── 1. Emulate real Pixel 10 Pro via CDP User-Agent Client Hints ──────────
    # Google services read Sec-CH-UA-Model & Sec-CH-UA-Platform to verify device
    try:
        driver.execute_cdp_cmd("Emulation.setUserAgentOverride", profile.get_client_hints())
    except Exception as exc:
        logger.warning("Failed to set CDP UserAgentOverride: %s", exc)

    # ── 2. Inject anti-detection & device properties into DOM ─────────────────
    chrome_major = profile.chrome_version.split(".")[0]
    stealth_js = f"""
        // Conceal WebDriver presence
        Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
        Object.defineProperty(navigator, 'plugins', {{ get: () => [] }});
        Object.defineProperty(navigator, 'languages', {{ get: () => ['en-US', 'en'] }});
        Object.defineProperty(navigator, 'platform', {{ get: () => 'Linux armv8l' }});
        Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => 5 }});
        Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => 8 }});
        Object.defineProperty(navigator, 'deviceMemory', {{ get: () => 8 }});
        window.chrome = {{ runtime: {{}} }};

        // UserAgentData high-entropy values matching Pixel 10 Pro
        const _uaData = {{
            brands: [
                {{ brand: 'Google Chrome', version: '{chrome_major}' }},
                {{ brand: 'Chromium', version: '{chrome_major}' }},
                {{ brand: 'Not=A?Brand', version: '24' }}
            ],
            mobile: true,
            platform: 'Android',
            getHighEntropyValues: async function(hints) {{
                const full = {{
                    brands: this.brands,
                    fullVersionList: [
                        {{ brand: 'Google Chrome', version: '{profile.chrome_version}' }},
                        {{ brand: 'Chromium', version: '{profile.chrome_version}' }},
                        {{ brand: 'Not=A?Brand', version: '24.0.0.0' }}
                    ],
                    mobile: true,
                    platform: 'Android',
                    platformVersion: '{config.ANDROID_VERSION}',
                    architecture: 'arm64',
                    model: '{config.DEVICE_MODEL}',
                    uaFullVersion: '{profile.chrome_version}',
                    bitness: '64',
                    wow64: false
                }};
                const result = {{}};
                hints.forEach(h => {{ if (h in full) result[h] = full[h]; }});
                return result;
            }},
            toJSON: function() {{
                return {{ brands: this.brands, mobile: this.mobile, platform: this.platform }};
            }}
        }};
        Object.defineProperty(navigator, 'userAgentData', {{
            get: () => _uaData,
            configurable: true
        }});
    """
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument", {"source": stealth_js}
        )
    except Exception as exc:
        logger.warning("Failed to inject stealth script: %s", exc)

    driver.implicitly_wait(config.IMPLICIT_WAIT)
    driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    return driver


# ── Login helper ──────────────────────────────────────────────────────────────

def _wait_for(driver: webdriver.Chrome, by: str, value: str,
              timeout: int = config.WEBDRIVER_TIMEOUT):
    """Return element after waiting for it to be clickable."""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )


def _check_already_logged_in(driver: webdriver.Chrome) -> bool:
    """Check if the browser session already has active Google credentials."""
    current_url = driver.current_url.lower()
    parsed = urlparse(current_url)
    hostname = parsed.hostname or ""
    path = parsed.path or ""

    if (
        ("myaccount.google.com" in hostname or "one.google.com" in hostname)
        and "/signin" not in path
    ):
        return True

    # Check for presence of signed-in avatar/profile element
    try:
        avatar = driver.find_elements(
            By.CSS_SELECTOR,
            'a[href*="SignOutOptions"], a[aria-label*="Google Account"], img[alt*="Google Account"]'
        )
        if avatar:
            return True
    except Exception:
        pass

    return False


def _handle_2fa_totp(driver: webdriver.Chrome, totp_secret: str) -> bool:
    """Attempt to resolve Google Two-Factor Authentication via TOTP code."""
    if not totp_secret:
        return False

    clean_secret = totp_secret.replace(" ", "").upper()
    try:
        otp_code = pyotp.TOTP(clean_secret).now()
        logger.info("Generated TOTP 6-digit code for 2FA prompt")
    except Exception as exc:
        logger.error("Failed to generate OTP from secret: %s", exc)
        return False

    totp_selectors = [
        'input[type="tel"]',
        'input[id*="totp"]',
        'input[id*="code"]',
        'input[autocomplete="one-time-code"]',
        'input[name="Pin"]',
    ]

    for sel in totp_selectors:
        try:
            fields = driver.find_elements(By.CSS_SELECTOR, sel)
            for f in fields:
                if f.is_displayed():
                    f.clear()
                    f.send_keys(otp_code)
                    time.sleep(1)

                    # Look for Next / Submit button
                    for btn_sel in (
                        '#totpNext',
                        'button[type="button"]',
                        'button[type="submit"]',
                        '#idvPreregisteredPhoneNext',
                    ):
                        try:
                            btn = driver.find_element(By.CSS_SELECTOR, btn_sel)
                            if btn.is_displayed():
                                btn.click()
                                time.sleep(3)
                                return True
                        except NoSuchElementException:
                            continue
                    return True
        except Exception:
            continue

    return False


def _gmail_login(driver: webdriver.Chrome, email: str, password: str,
                 totp_secret: str = "") -> bool:
    """
    Perform Gmail / Google account authentication with 2FA TOTP support.
    """
    try:
        driver.get(config.GMAIL_LOGIN_URL)
        time.sleep(3)

        # Check if saved cookies / persistent profile already logged in
        if _check_already_logged_in(driver):
            logger.info("Session already authenticated via cached profile/cookies")
            return True

        # ── Step 1: Email ─────────────────────────────────────────────────────
        try:
            email_field = _wait_for(driver, By.CSS_SELECTOR, 'input[type="email"], #identifierId')
            email_field.clear()
            email_field.send_keys(email)

            next_btn = _wait_for(driver, By.ID, "identifierNext")
            next_btn.click()
            time.sleep(3)
        except TimeoutException:
            # Check if email is already prefilled or if we're on password page
            pass

        # Check for bot challenge or block on identifier step
        body_text = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
        if "couldn't sign you in" in body_text or "browser or app may not be secure" in body_text:
            logger.warning("Google blocked login: 'Browser or app may not be secure' challenge triggered")
            raise GoogleAutomationError(
                "Google flagged this automated login session as insecure. "
                "Consider setting PROXY_URL with a residential IP or logging in with saved session profile."
            )

        # ── Step 2: Password ──────────────────────────────────────────────────
        try:
            password_field = _wait_for(driver, By.CSS_SELECTOR, 'input[type="password"]', timeout=15)
            password_field.clear()
            password_field.send_keys(password)

            pw_next = _wait_for(driver, By.ID, "passwordNext")
            pw_next.click()
            time.sleep(4)
        except TimeoutException:
            if _check_already_logged_in(driver):
                return True
            raise GoogleAutomationError("Timed out waiting for password input field.")

        # ── Step 3: 2FA / Verification Challenge ──────────────────────────────
        current_url = driver.current_url.lower()
        if "challenge" in current_url or "signin/v2/challenge" in current_url:
            logger.info("2FA Challenge detected on account")
            if totp_secret:
                handled = _handle_2fa_totp(driver, totp_secret)
                if handled:
                    time.sleep(4)

            # If still on challenge page
            if "challenge" in driver.current_url.lower():
                raise GoogleAutomationError(
                    "Google 2-Step Verification prompt triggered (Google Authenticator or Phone Prompt). "
                    "Please provide your TOTP Authenticator key via /login or approve the prompt on your phone."
                )

        # ── Step 4: Verify login ──────────────────────────────────────────────
        if _check_already_logged_in(driver):
            logger.info("Login succeeded for %s", email)
            return True

        # Check for wrong password / account error message
        try:
            error_el = driver.find_element(
                By.CSS_SELECTOR, '[jsname="B34EJ"], [aria-live="assertive"]'
            )
            if error_el.text:
                logger.warning("Login error message detected: %s", error_el.text)
                return False
        except NoSuchElementException:
            pass

        parsed = urlparse(driver.current_url)
        if not (parsed.hostname == "accounts.google.com" and parsed.path.startswith("/signin")):
            logger.info("Login appeared successful for %s (URL: %s)", email, driver.current_url)
            return True

        logger.warning("Unexpected URL after login: %s", driver.current_url)
        return False

    except GoogleAutomationError:
        raise
    except TimeoutException as exc:
        logger.error("Timeout during login: %s", exc)
        return False
    except WebDriverException as exc:
        logger.error("WebDriver error during login: %s", exc)
        return False


# ── Offer detection ───────────────────────────────────────────────────────────

def _extract_payment_link(driver: webdriver.Chrome) -> Optional[str]:
    """
    Scan page DOM and raw HTML for a Gemini / Google One offer link.
    """
    # Pattern 1: Direct Google One offer link
    offer_regex = re.compile(
        r'https?://one\.google\.com/offer/([A-Za-z0-9_-]+)',
        re.IGNORECASE,
    )
    matches = offer_regex.findall(driver.page_source)
    for code in matches:
        if (
            code.lower() not in {"freetrial", "free-trial", "trial", "upgrade", "plans", "about", "home", "benefits"}
            and len(code) > 5
        ):
            found = f"https://one.google.com/offer/{code}"
            logger.info("Found unique offer link via regex: %s", found)
            return found

    # Pattern 2: Anchor tags matching promotional keywords
    keywords = config.GEMINI_OFFER_KEYWORDS
    all_links = driver.find_elements(By.TAG_NAME, "a")
    for link in all_links:
        try:
            text = (link.text + " " + (link.get_attribute("aria-label") or "")).lower()
            href = link.get_attribute("href") or ""
            if any(kw in text for kw in keywords) and href and "one.google.com" in href:
                logger.info("Found offer link via text match: %s", href)
                return href
        except Exception:
            continue

    # Pattern 3: Interactive CTA buttons
    buttons = driver.find_elements(By.CSS_SELECTOR, "button, [role='button']")
    for btn in buttons:
        try:
            text = btn.text.lower()
            if any(kw in text for kw in keywords):
                try:
                    parent_link = btn.find_element(By.XPATH, "ancestor::a")
                    href = parent_link.get_attribute("href") or ""
                    if href:
                        return href
                except NoSuchElementException:
                    pass
                if "one.google.com" in driver.current_url:
                    return driver.current_url
        except Exception:
            continue

    return None


def _navigate_google_one(driver: webdriver.Chrome) -> Optional[str]:
    """
    Navigate through Google One plans and benefits pages to find promotional offers.
    """
    urls_to_check = [
        config.GOOGLE_ONE_GEMINI_URL,
        config.GOOGLE_ONE_BENEFITS_URL,
        config.GOOGLE_ONE_OFFERS_URL,
        config.GOOGLE_ONE_URL,
    ]

    for url in urls_to_check:
        try:
            logger.info("Navigating to %s", url)
            driver.get(url)
            time.sleep(3)

            # Dismiss cookie / consent prompts
            for selector in (
                '[aria-label="Accept all"]',
                'button[jsname="higCR"]',
                '[data-action="accept"]',
            ):
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, selector)
                    btn.click()
                    time.sleep(1)
                    break
                except NoSuchElementException:
                    pass

            # Scroll dynamically to trigger SPA lazy loading of cards
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1.5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

            link = _extract_payment_link(driver)
            if link:
                return link

        except (TimeoutException, WebDriverException) as exc:
            logger.warning("Error accessing %s: %s", url, exc)

    return None


# ── Public API ────────────────────────────────────────────────────────────────

class GoogleAutomationError(Exception):
    """Raised when automation encounters an unrecoverable error."""


def check_gemini_offer(email: str, password: str, device: DeviceProfile,
                       totp_secret: str = "") -> Optional[str]:
    """
    Main entry point for Google One Gemini offer check.
    """
    driver: Optional[webdriver.Chrome] = None
    try:
        logger.info("Starting WebDriver for session %s (Model: %s)", device.session_id, device.model)
        driver = _build_driver(device, email=email)

        logged_in = _gmail_login(driver, email, password, totp_secret=totp_secret)
        if not logged_in:
            raise GoogleAutomationError(
                "Login failed – please check your Gmail address and password."
            )

        offer_link = _navigate_google_one(driver)
        return offer_link

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
