"""Independent numeric/domain/proxy checks for the additive compatibility runtime."""
from contextlib import contextmanager
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mortgage_risk import cohorts
from mortgage_risk.portable_log1p import positive_log1p, cohort_math, UPSTREAM_BLOB


def from_high(word):
    return struct.unpack(">d", struct.pack(">II", word, 0))[0]


def boundary_inputs():
    centers = [from_high(h) for h in (0x3C900000, 0x3E200000, 0x3FDA827A, 0x43400000)]
    centers += [math.ldexp(1.0, e) for e in range(-1074, 1024, 37)]
    # Argument-reduction mantissa branch, exercised at multiple exponents.
    centers += [math.ldexp(from_high(0x3FF6A09E), e) - 1.0 for e in (0, 1, 8, 20, 52, 100, 1022)]
    centers += [1.0, 2.0, 1000.0, 100000.0, 999999.0, sys.float_info.max]
    values = set()
    for x in centers:
        values.update((math.nextafter(x, 0.0), x, math.nextafter(x, math.inf)))
    rng = random.Random(20261026)
    values.update(math.ldexp(rng.uniform(1.0, 2.0), rng.randrange(-1074, 1023)) for _ in range(120))
    return sorted(x for x in values if 0 < x < math.inf)


class PortableRuntimeTests(unittest.TestCase):
    def test_upstream_blob_is_exact(self):
        source = (ROOT / "third_party/glibc/s_log1p.c").read_bytes()
        self.assertEqual(hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest(), UPSTREAM_BLOB)

    def test_boundary_accuracy_against_independent_decimal_logarithm(self):
        # 400 digits preserve 1+x even at the least positive binary64 value.
        # This verifies <=1 ulp accuracy, not glibc bit identity.
        with localcontext() as ctx:
            ctx.prec = 400
            for x in boundary_inputs():
                expected = (Decimal(1) + Decimal.from_float(x)).ln()
                actual = positive_log1p(x)
                error = abs(Decimal.from_float(actual) - expected)
                self.assertLessEqual(error, Decimal.from_float(math.ulp(actual)), x.hex())

    def test_monotonic_positive_results_at_boundaries(self):
        values = [positive_log1p(x) for x in boundary_inputs()]
        self.assertTrue(all(math.isfinite(x) and x > 0 for x in values))
        self.assertTrue(all(a <= b for a, b in zip(values, values[1:])))

    def test_tiny_branch_and_known_log_two(self):
        for x in (math.ulp(0.0), math.ldexp(1.0, -1000), math.ldexp(1.0, -55)):
            self.assertEqual(positive_log1p(x), x)
        self.assertEqual(positive_log1p(1.0).hex(), "0x1.62e42fefa39efp-1")

    def test_domain_rejected_without_fallback(self):
        for x in (0.0, -0.0, -1.0, -0.1, math.inf, -math.inf, math.nan):
            with self.assertRaises(ValueError):
                positive_log1p(x)

    def test_proxy_is_module_local_and_restores_after_error(self):
        original_log = math.log1p
        original_math = cohorts.math
        with self.assertRaisesRegex(RuntimeError, "deliberate"):
            with cohort_math() as proxy:
                self.assertIs(math.log1p, original_log)
                self.assertIs(cohorts.math, proxy)
                self.assertIs(proxy.isfinite, math.isfinite)
                self.assertEqual(cohorts.math.log1p(1.0), positive_log1p(1.0))
                self.assertEqual(proxy.receipt()["calls"], 1)
                with self.assertRaises(RuntimeError):
                    with cohort_math():
                        pass
                raise RuntimeError("deliberate")
        self.assertIs(cohorts.math, original_math)
        self.assertIs(math.log1p, original_log)

    def test_all_original_method_files_unchanged(self):
        methods = json.loads((ROOT / "reports/prefit_manifest.json").read_text())["method_files"]
        self.assertEqual(len(methods), 20)
        for name, digest in methods.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)


if __name__ == "__main__":
    unittest.main()
