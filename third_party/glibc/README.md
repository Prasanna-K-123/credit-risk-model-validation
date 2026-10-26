# Pinned log1p source

Source: GNU C Library `sysdeps/ieee754/dbl-64/s_log1p.c` at commit
`ce65d944e38a20cb70af2a48a4b8aa5d8fabe1cc`, Git blob
`eeb0af859ffce7dacb14bf8fe82ff88ed11af23e`.

https://github.com/bminor/glibc/blob/ce65d944e38a20cb70af2a48a4b8aa5d8fabe1cc/sysdeps/ieee754/dbl-64/s_log1p.c

This exact source is retained as text for provenance; it is never compiled or
loaded. Its Sun Microsystems 1993 permission notice and Naohiko Shimizu 1997
modification credit are preserved here and in the Python translation.

`src/mortgage_risk/portable_log1p.py` version 1.0.0 translates the positive finite
domain using separate binary64 operations, with no fused multiply-add. Zero,
negative, infinite and NaN inputs fail explicitly; C floating-point exception
flags are not emulated. Only `mortgage_risk.cohorts.math` receives the adapter;
the process-wide `math.log1p` is unchanged.

High-precision tests check numerical accuracy; exact historical prepared-table
hashes separately establish the required source-specific serialization.
