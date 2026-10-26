"""Version 1.0.0: positive-finite binary64 glibc log1p compatibility.

Translation of sysdeps/ieee754/dbl-64/s_log1p.c, commit
ce65d944e38a20cb70af2a48a4b8aa5d8fabe1cc, blob
eeb0af859ffce7dacb14bf8fe82ff88ed11af23e.

Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved.
Developed at SunPro, a Sun Microsystems, Inc. business.
Permission to use, copy, modify, and distribute this
software is freely granted, provided that this notice
is preserved.
Modified by Naohiko Shimizu/Tokai University, Japan 1997/08/25,
for performance improvement on pipelined processors.

Python adaptation, 26 October 2026: restrict to positive finite inputs, retain
separate binary64 arithmetic (no FMA), and omit C floating-point exception flags.
This restores a historical feature serialization, not native-runtime identity.
"""
from __future__ import annotations

from contextlib import contextmanager
import math
import struct
import sys

VERSION = "1.0.0"
UPSTREAM_COMMIT = "ce65d944e38a20cb70af2a48a4b8aa5d8fabe1cc"
UPSTREAM_BLOB = "eeb0af859ffce7dacb14bf8fe82ff88ed11af23e"
LN2_HI = float.fromhex("0x1.62e42fee00000p-1")
LN2_LO = float.fromhex("0x1.a39ef35793c76p-33")
LP = tuple(float.fromhex(x) for x in (
    "0x0p+0", "0x1.5555555555593p-1", "0x1.999999997fa04p-2",
    "0x1.2492494229359p-2", "0x1.c71c51d8e78afp-3",
    "0x1.7466496cb03dep-3", "0x1.39a09d078c69fp-3",
    "0x1.2f112df3e5244p-3"))


def _high(x: float) -> int:
    return struct.unpack(">II", struct.pack(">d", x))[0]


def _set_high(x: float, word: int) -> float:
    low = struct.unpack(">II", struct.pack(">d", x))[1]
    return struct.unpack(">d", struct.pack(">II", word, low))[0]


def positive_log1p(value: float) -> float:
    """Return the pinned grouped-polynomial result for 0 < x < infinity.

    Inputs are converted to binary64. Zero, negative and non-finite values fail
    explicitly. This is deliberately not a general replacement for math.log1p.
    """
    x = float(value)
    if not math.isfinite(x) or x <= 0:
        raise ValueError("Compatibility log1p requires a positive finite balance.")
    hx = _high(x)
    k = 1
    c = 0.0
    if hx < 0x3FDA827A:
        if hx < 0x3E200000:
            if hx < 0x3C900000:
                return x
            return x - x * x * 0.5
        k, f, hu = 0, x, 1
    if k != 0:
        if hx < 0x43400000:
            u = 1.0 + x
            hu = _high(u)
            k = (hu >> 20) - 1023
            c = (1.0 - (u - x) if k > 0 else x - (u - 1.0)) / u
        else:
            u = x
            hu = _high(u)
            k = (hu >> 20) - 1023
        hu &= 0x000FFFFF
        if hu < 0x6A09E:
            u = _set_high(u, hu | 0x3FF00000)
        else:
            k += 1
            u = _set_high(u, hu | 0x3FE00000)
            hu = (0x00100000 - hu) >> 2
        f = u - 1.0
    hfsq = 0.5 * f * f
    if hu == 0:
        if f == 0.0:
            if k == 0:
                return 0.0
            c += k * LN2_LO
            return k * LN2_HI + c
        r = hfsq * (1.0 - 0.66666666666666666 * f)
        if k == 0:
            return f - r
        return k * LN2_HI - ((r - (k * LN2_LO + c)) - f)
    s = f / (2.0 + f)
    z = s * s
    r1 = z * LP[1]
    z2 = z * z
    r2 = LP[2] + z * LP[3]
    z4 = z2 * z2
    r3 = LP[4] + z * LP[5]
    z6 = z4 * z2
    r4 = LP[6] + z * LP[7]
    r = r1 + z2 * r2 + z4 * r3 + z6 * r4
    if k == 0:
        return f - (hfsq - s * (hfsq + r))
    return k * LN2_HI - ((hfsq - (s * (hfsq + r) + (k * LN2_LO + c))) - f)


class BalanceMath:
    """Only the two operations the frozen cohorts module requires."""
    isfinite = staticmethod(math.isfinite)

    def __init__(self):
        self.calls = 0
        self.minimum_input = None
        self.maximum_input = None

    def log1p(self, x):
        result = positive_log1p(x)
        self.calls += 1
        self.minimum_input = x if self.minimum_input is None else min(x, self.minimum_input)
        self.maximum_input = x if self.maximum_input is None else max(x, self.maximum_input)
        return result

    def receipt(self):
        return {"adapter_version": VERSION, "domain": "positive finite binary64",
                "calls": self.calls, "minimum_input": self.minimum_input,
                "maximum_input": self.maximum_input,
                "activation": "mortgage_risk.cohorts.math only"}


@contextmanager
def cohort_math():
    """Use only in an isolated, sequential preparation/evaluation process."""
    from . import cohorts
    if sys.float_info.radix != 2 or sys.float_info.mant_dig != 53:
        raise RuntimeError("The compatibility adapter requires IEEE binary64.")
    original = cohorts.math
    if original is not math:
        raise RuntimeError("Refusing nested or unexpected cohorts math replacement.")
    proxy = BalanceMath()
    cohorts.math = proxy
    try:
        yield proxy
    finally:
        cohorts.math = original
