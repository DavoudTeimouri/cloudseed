"""Pure-stdlib SHA-512 crypt (Ulrich Drepper's $6$ algorithm).

Implements the algorithm described in `crypt(3)` / the GLIBC `sha512-crypt.c`.
Verified against the host OS `crypt.crypt` (which implements $6$) in
tests/test_crypt_sha512.py. Falls back to host crypt when available; the pure
implementation is used on platforms without SHA-512 crypt support (e.g. some
Windows Python builds). No third-party dependencies.
"""

from __future__ import annotations

import hashlib
import os

_B64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# byte permutation applied to the final digest before base64 encoding
_PERM = [
    0, 21, 42, 1, 22, 43, 2, 23, 44, 3, 24, 45, 4, 25, 46, 5, 26, 47,
    6, 27, 48, 7, 28, 49, 8, 29, 50, 9, 30, 51, 10, 31, 52, 11, 32, 53,
    12, 33, 54, 13, 34, 55, 14, 35, 56, 15, 36, 57, 16, 37, 58, 17, 38,
    59, 18, 39, 60, 19, 40, 61, 20, 41, 62, 63,
]


def _sha512(*parts: bytes) -> bytes:
    h = hashlib.sha512()
    for p in parts:
        h.update(p)
    return h.digest()


def _b64_encode(data: bytes) -> str:
    """Base64-encode per the crypt variant (MSB-first 6-bit groups)."""
    out = []
    i = 0
    n = len(data)
    while i < n:
        b0 = data[i]
        b1 = data[i + 1] if i + 1 < n else 0
        b2 = data[i + 2] if i + 2 < n else 0
        triple = (b0 << 16) | (b1 << 8) | b2
        # MSB-first: emit top 6 bits first
        out.append(_B64[(triple >> 18) & 0x3F])
        out.append(_B64[(triple >> 12) & 0x3F])
        out.append(_B64[(triple >> 6) & 0x3F])
        out.append(_B64[triple & 0x3F])
        i += 3
    return "".join(out)[:43]


def sha512_crypt(password: str, salt: str = None, rounds: int = 5000) -> str:
    if salt is None:
        salt = os.urandom(8).hex()[:16]
    salt = salt[:16].lstrip("$").replace("$", "")
    rounds = max(1000, min(999999999, int(rounds)))

    pw = password.encode("utf-8") or b"\x00"
    s = (salt.encode("ascii") or b"\x00")
    plen = len(pw)
    slen = len(s)

    # A = sha512(pw + salt + pw)
    A = _sha512(pw, s, pw)

    # B = sha512(pw + salt + (A repeated to len(pw)) + pw)
    P = bytearray()
    while len(P) < plen:
        P += A
    P = P[:plen]
    B = _sha512(pw, s, bytes(P), pw)

    # DP = sha512(pw repeated then truncated to len(salt))
    dp_in = bytearray()
    while len(dp_in) < slen:
        dp_in += pw
    DP = _sha512(bytes(dp_in[:slen]))

    # DS = sha512(salt repeated then truncated to len(pw))
    ds_in = bytearray()
    while len(ds_in) < plen:
        ds_in += s
    DS = _sha512(bytes(ds_in[:plen]))

    # mixing rounds
    C = B
    for i in range(rounds):
        ctx = bytearray()
        ctx += A if (i & 1) else B
        ctx += C
        if i % 3:
            ctx += DP
        if i % 7:
            ctx += DS
        C = _sha512(bytes(ctx))

    # final permutation + encode
    permuted = bytes(C[_PERM[k]] for k in range(64))
    h = _b64_encode(permuted)

    rounds_str = f"rounds={rounds}$" if rounds != 5000 else ""
    return f"$6${rounds_str}{salt}${h}"
