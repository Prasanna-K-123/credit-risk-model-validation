"""Apply the monetary-card layout after building the frozen aggregate explorer."""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs/index.html"
CSS = ".metrics.money-metrics{grid-template-columns:minmax(0,1fr)}.metrics.money-metrics strong{font-size:clamp(1.25rem,4vw,2rem);overflow-wrap:anywhere;font-variant-numeric:tabular-nums}"


def polish(text):
    scripts = re.findall(r"<script\b[^>]*>[\s\S]*?</script>", text)
    if 'class="metrics money-metrics"' not in text:
        original = '<div class="metrics"><div><span>Reviewed loans: conditional amount'
        replacement = '<div class="metrics money-metrics"><div><span>Reviewed loans: conditional amount'
        if text.count(original) != 1:
            raise ValueError("Expected one conditional-amount metrics group")
        text = text.replace(original, replacement, 1)
    if CSS not in text:
        if text.count("</style>") != 1:
            raise ValueError("Expected one explorer style block")
        text = text.replace("</style>", CSS + "\n</style>", 1)
    if scripts != re.findall(r"<script\b[^>]*>[\s\S]*?</script>", text):
        raise ValueError("Layout change touched embedded evidence or calculation code")
    return text


if __name__ == "__main__":
    original = PAGE.read_text()
    revised = polish(original)
    PAGE.write_text(revised)
    print("Monetary layout updated; embedded script SHA256: " + hashlib.sha256(
        "".join(re.findall(r"<script\b[^>]*>[\s\S]*?</script>", revised)).encode()).hexdigest())
