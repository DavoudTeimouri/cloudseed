"""Password hashing for cloud-init `passwd` field.

cloud-init requires a hashed password (plaintext is rejected on most images).
Resolution order:
  1. host `crypt()` with SHA-512 ($6$) if available (Linux, Windows Python<3.13)
  2. else `openssl passwd -6` if on PATH (common on Windows / Cloudbase hosts)
  3. else pure-stdlib fallback in cloudseed.crypt_sha512 (verified-equivalent
     implementation; kept only for exotic no-crypt/no-openssl environments)

All paths emit a standard `$6$` SHA-512 crypt hash.
"""

from __future__ import annotations

import os
import shutil
import subprocess

try:
    import crypt as _crypt

    def _host_supports_sha512() -> bool:
        try:
            return _crypt.crypt("x", "$6$salt$").startswith("$6$")
        except Exception:
            return False

    _HOST_OK = _host_supports_sha512()
except Exception:  # pragma: no cover - platform without crypt module
    _crypt = None
    _HOST_OK = False


def _openssl_sha512(password: str, salt: str, rounds: int) -> str:
    # `-iter` is not supported by all OpenSSL builds (e.g. LibreSSL); the
    # default is 5000 rounds which is adequate. We ignore `rounds` here.
    cmd = ["openssl", "passwd", "-6", "-salt", salt, password]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if out.returncode != 0 or not out.stdout.strip().startswith("$6$"):
        raise RuntimeError("openssl passwd -6 failed: " + out.stderr.strip())
    return out.stdout.strip()


def hash_password(password: str, rounds: int = 5000) -> str:
    """Return a $6$ SHA-512 crypt hash of `password`."""
    salt = os.urandom(8).hex()[:16]
    if _HOST_OK and _crypt is not None:
        setting = f"$6${'rounds=%d$' % rounds if rounds != 5000 else ''}{salt}$"
        return _crypt.crypt(password, setting)
    if shutil.which("openssl"):
        try:
            return _openssl_sha512(password, salt, rounds)
        except Exception:
            pass
    from .crypt_sha512 import sha512_crypt
    return sha512_crypt(password, salt, rounds)
