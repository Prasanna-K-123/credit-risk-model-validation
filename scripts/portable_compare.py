"""Strict, prespecified aggregate comparison; never changes models or tolerances."""
from __future__ import annotations
import math


def at(value, pointer):
    for key in pointer.strip("/").split("/"):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def compare(old, new, *, excluded=(), atol=1e-10, rtol=1e-10):
    differences, omitted = [], []
    counts = {"leaves": 0, "scientific_numbers": 0, "integer_or_boolean_leaves": 0}
    maximum_absolute_float_difference = 0.0

    def visit(a, b, path):
        nonlocal maximum_absolute_float_difference
        if path in excluded:
            omitted.append({"path": path, "historical": a, "current": b})
            return
        if type(a) is not type(b):
            differences.append({"path": path, "kind": "type", "historical": a, "current": b})
            return
        if isinstance(a, dict):
            if a.keys() != b.keys():
                differences.append({"path": path, "kind": "keys",
                                    "historical": sorted(a), "current": sorted(b)})
            for key in sorted(a.keys() & b.keys()):
                visit(a[key], b[key], path + "/" + key)
        elif isinstance(a, list):
            if len(a) != len(b):
                differences.append({"path": path, "kind": "length",
                                    "historical": len(a), "current": len(b)})
            for i, (aa, bb) in enumerate(zip(a, b)):
                visit(aa, bb, path + "/" + str(i))
        else:
            counts["leaves"] += 1
            if isinstance(a, (int, bool)):
                counts["integer_or_boolean_leaves"] += 1
            if isinstance(a, float):
                counts["scientific_numbers"] += 1
                finite = math.isfinite(a) and math.isfinite(b)
                absolute = abs(a-b)
                tolerance = atol + rtol * abs(a)
                if finite:
                    maximum_absolute_float_difference = max(maximum_absolute_float_difference, absolute)
                if not finite or absolute > tolerance:
                    differences.append({"path": path, "kind": "float", "historical": a, "current": b,
                                        "absolute_difference": absolute, "allowed_difference": tolerance})
            elif a != b:
                differences.append({"path": path, "kind": "exact", "historical": a, "current": b})
    visit(old, new, "")
    return {"passed": not differences, "counts": counts, "differences": differences,
            "excluded_metadata": omitted,
            "maximum_absolute_float_difference": maximum_absolute_float_difference}


def report_precision(old_files, new_files, fields):
    comparisons = []
    for item in fields:
        a = at(old_files[item["file"]], item["path"])
        b = at(new_files[item["file"]], item["path"])
        digits = item["decimal_places"]
        aa, bb = format(a, f".{digits}f"), format(b, f".{digits}f")
        comparisons.append({**item, "historical_formatted": aa, "current_formatted": bb,
                            "passed": aa == bb})
    return {"scope": "Only prespecified fields at the original report's display precision; weaker than strict numerical reproduction.",
            "passed": all(x["passed"] for x in comparisons), "fields": comparisons}
