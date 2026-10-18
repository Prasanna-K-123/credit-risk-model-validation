"""Generate a self-contained aggregate explorer and static report exports."""
import json
from pathlib import Path
from report_html import render

ROOT=Path(__file__).resolve().parents[1]
if __name__=="__main__":
    aggregate=json.loads((ROOT/"reports/demo_aggregates.json").read_text())
    template=(ROOT/"docs/demo.template.html").read_text()
    assert template.count("__DATA__")==1
    html=template.replace("__DATA__",json.dumps(aggregate,ensure_ascii=False,separators=(",",":")))
    (ROOT/"docs/index.html").write_text(html)
    (ROOT/"docs/.nojekyll").write_text("")
    export=ROOT/"docs/exports";export.mkdir(exist_ok=True)
    for source,target in [("reports/TECHNICAL_REPORT.md","technical_report"),("reports/DECISION_MEMO.md","decision_memo"),("docs/PROTOCOL.md","protocol")]:
        body=render((ROOT/source).read_text())
        style="body{font:16px/1.65 system-ui;color:#193342;max-width:1060px;margin:auto;padding:28px}table{border-collapse:collapse;display:block;overflow:auto}td,th{padding:8px;border:1px solid #d6e2e6}a{color:#155e63}h1{line-height:1.2}@media(max-width:600px){body{padding:16px;font-size:15px}}"
        (export/f"{target}.html").write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{target.replace("_"," ").title()} | Prasanna K</title><style>{style}</style><p><a href="../index.html">Research explorer</a></p>'+body+'</html>')
    print(json.dumps({"aggregate_scenarios":len(aggregate["scenarios"]),"exports":3,"individual_rows_published":False}))
