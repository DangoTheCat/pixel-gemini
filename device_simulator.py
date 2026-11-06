"""
Android Pixel 10 Pro device simulator.

Generates realistic identifiers (IMEI with valid Luhn checksum, Android ID,
official device fingerprint, and modern Chrome version patch) while keeping
hardware identity consistently aligned with Google Pixel 10 Pro.
"""

import secrets
import string
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any

import config


# ── Helpers ───────────────────────────────────────────────────────────────────

def _luhn_checksum(number: str) -> int:
    """Return the Luhn check digit for a numeric string."""
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10


def _generate_imei() -> str:
    """Generate a syntactically valid IMEI (15 digits, Luhn-valid) with a Google TAC."""
    # Common TAC prefix for Google Pixel hardware
    tac = "35" + "".join(secrets.choice(string.digits) for _ in range(6))
    serial = "".join(secrets.choice(string.digits) for _ in range(6))
    partial = tac + serial
    check_digit = (10 - _luhn_checksum(partial + "0")) % 10
    return partial + str(check_digit)


def _generate_android_id() -> str:
    """Generate a 16-character hex Android ID."""
    return "".join(secrets.choice("0123456789abcdef") for _ in range(16))


def _generate_device_fingerprint(model: str, build_id: str, android: str) -> str:
    """
    Return a realistic Android build fingerprint matching official release builds.
    Format: google/model/model:version/build_id/incremental:user/release-keys
    """
    slug = model.lower().replace(" ", "_")
    incremental = secrets.randbelow(900000) + 12000000  # realistic build incremental
    return f"google/{slug}/{slug}:{android}/{build_id}/{incremental}:user/release-keys"


def _random_chrome_patch() -> str:
    """Return a modern Chrome version patch within legitimate release window."""
    major = config.CHROME_MAJOR_VERSION
    minor = 0
    build = secrets.randbelow(150) + 7200
    patch = secrets.randbelow(100) + 50
    return f"{major}.{minor}.{build}.{patch}"


# ── Device profile dataclass ──────────────────────────────────────────────────

@dataclass
class DeviceProfile:
    imei: str
    android_id: str
    device_fingerprint: str
    user_agent: str
    chrome_version: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Pixel 10 Pro hardware specs
    model: str = config.DEVICE_MODEL
    brand: str = config.DEVICE_BRAND
    manufacturer: str = config.DEVICE_MANUFACTURER
    android_version: str = config.ANDROID_VERSION
    android_sdk: str = config.ANDROID_SDK
    build_id: str = config.BUILD_ID

    def get_client_hints(self) -> Dict[str, Any]:
        """Return Chrome DevTools Protocol (CDP) userAgentMetadata for Client Hints."""
        chrome_major = str(self.chrome_version.split(".")[0])
        return {
            "userAgent": self.user_agent,
            "acceptLanguage": "en-US,en;q=0.9",
            "platform": "Linux aarch64",
            "userAgentMetadata": {
                "brands": [
                    {"brand": "Google Chrome", "version": chrome_major},
                    {"brand": "Chromium", "version": chrome_major},
                    {"brand": "Not=A?Brand", "version": "24"},
                ],
                "fullVersionList": [
                    {"brand": "Google Chrome", "version": self.chrome_version},
                    {"brand": "Chromium", "version": self.chrome_version},
                    {"brand": "Not=A?Brand", "version": "24.0.0.0"},
                ],
                "platform": "Android",
                "platformVersion": self.android_version,
                "architecture": "arm64",
                "model": self.model,
                "mobile": True,
                "bitness": "64",
                "wow64": False,
            },
        }

    def summary(self) -> str:
        """Human-readable summary for Telegram messages."""
        return (
            f"📱 *Device Profile*\n"
            f"Model: {self.model}\n"
            f"Android: {self.android_version} (SDK {self.android_sdk})\n"
            f"Chrome: `{self.chrome_version}`\n"
            f"IMEI (Simulated): `{self.imei}`\n"
            f"Android ID: `{self.android_id}`\n"
            f"Session: `{self.session_id[:8]}…`"
        )


# ── Public factory ────────────────────────────────────────────────────────────

def create_device_profile() -> DeviceProfile:
    """
    Create a fresh Pixel 10 Pro device profile with unique per-session
    identifiers and modern parameters.
    """
    chrome_version = _random_chrome_patch()
    template = secrets.choice(config.USER_AGENT_TEMPLATES)
    user_agent = template.format(
        android=config.ANDROID_VERSION,
        model=config.DEVICE_MODEL,
        build=config.BUILD_ID,
        chrome=chrome_version,
    )
    fingerprint = _generate_device_fingerprint(
        config.DEVICE_MODEL,
        config.BUILD_ID,
        config.ANDROID_VERSION,
    )
    return DeviceProfile(
        imei=_generate_imei(),
        android_id=_generate_android_id(),
        device_fingerprint=fingerprint,
        user_agent=user_agent,
        chrome_version=chrome_version,
    )
