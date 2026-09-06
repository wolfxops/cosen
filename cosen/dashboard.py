from __future__ import annotations

from html import escape
from typing import Any

from . import store


def _money(value: Any) -> str:
    try:
        return f"${float(value):.4f}"
    except (TypeError, ValueError):
        return "$0.0000"


def _int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def _rows(items: list[dict[str, Any]], columns: list[tuple[str, str, str]]) -> str:
    if not items:
        return "<tr><td colspan='8' class='empty'>No data in this window yet. Send traffic through the gateway.</td></tr>"
    parts = []
    for item in items:
        cells = []
        for key, kind, _label in columns:
            raw = item.get(key)
            if kind == "money":
                cells.append(f"<td>{_money(raw)}</td>")
            elif kind == "int":
                cells.append(f"<td>{_int(raw)}</td>")
            else:
                cells.append(f"<td>{escape(str(raw if raw is not None else '—'))}</td>")
        parts.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(parts)


def render(since_hours: int = 24) -> str:
    data = store.summarize(since_hours)
    totals = data.get("totals") or {}
    models = data.get("by_model") or []
    features = data.get("by_feature") or []
    findings = data.get("findings") or []
    recent = data.get("recent") or []

    model_cols = [("model", "text", "Model"), ("calls", "int", "Calls"), ("cost_usd", "money", "Cost"), ("avg_latency_ms", "int", "Avg ms")]
    feature_cols = [("feature", "text", "Feature"), ("calls", "int", "Calls"), ("cost_usd", "money", "Cost")]
    finding_cols = [("kind", "text", "Scanner"), ("severity", "text", "Severity"), ("n", "int", "Count")]
    recent_cols = [
        ("ts", "text", "When"),
        ("feature", "text", "Feature"),
        ("model", "text", "Model"),
        ("status", "text", "Status"),
        ("cost_usd", "money", "Cost"),
        ("latency_ms", "int", "ms"),
        ("security_verdict", "text", "Security"),
        ("request_preview", "text", "Preview"),
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Cosen — Cost · Observability · Security</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    :root {{
      --bg: #0b1020;
      --card: #141a2e;
      --ink: #e8edf7;
      --mute: #8b95b3;
      --line: #243049;
      --cost: #7dd3a0;
      --obs: #7db3ff;
      --sec: #f0b07a;
      --bad: #f07178;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: ui-sans-serif, system-ui, sans-serif;
      background: radial-gradient(1200px 600px at 10% -10%, #1a2450 0%, var(--bg) 45%);
      color: var(--ink);
    }}
    header {{
      padding: 28px 32px 8px; display: flex; justify-content: space-between; align-items: baseline;
    }}
    h1 {{ font-size: 22px; margin: 0; letter-spacing: 0.08em; }}
    h1 span {{ color: var(--mute); font-weight: 500; letter-spacing: 0; }}
    .sub {{ color: var(--mute); font-size: 13px; }}
    main {{ padding: 16px 32px 48px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
    .card {{
      background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px;
    }}
    .label {{ color: var(--mute); font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em; }}
    .value {{ font-size: 28px; margin-top: 8px; font-variant-numeric: tabular-nums; }}
    .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; }}
    .c {{ background: #163226; color: var(--cost); }}
    .o {{ background: #16243f; color: var(--obs); }}
    .s {{ background: #3a2a18; color: var(--sec); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ text-align: left; color: var(--mute); font-weight: 600; padding: 8px 6px; border-bottom: 1px solid var(--line); }}
    td {{ padding: 8px 6px; border-bottom: 1px solid #1c2438; vertical-align: top; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .empty {{ color: var(--mute); text-align: center; padding: 18px !important; }}
    .cols {{ display: grid; grid-template-columns: 1.2fr 1fr 1fr; gap: 14px; margin-top: 14px; }}
    footer {{ color: var(--mute); font-size: 12px; padding: 8px 32px 28px; }}
    code {{ background: #0d1324; padding: 1px 6px; border-radius: 6px; }}
    @media (max-width: 960px) {{
      .grid, .cols {{ grid-template-columns: 1fr; }}
      header, main, footer {{ padding-left: 16px; padding-right: 16px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Cosen <span>Cost · Observability · Security</span></h1>
      <div class="sub">Last {since_hours}h · local-first · model-agnostic</div>
    </div>
    <div class="sub">GET /health · POST /v1/chat/completions</div>
  </header>
  <main>
    <div class="grid">
      <div class="card">
        <div class="label"><span class="pill c">Cost</span> Spend</div>
        <div class="value">{_money(totals.get("cost_usd"))}</div>
      </div>
      <div class="card">
        <div class="label"><span class="pill o">Obs</span> Calls</div>
        <div class="value">{_int(totals.get("calls"))}</div>
      </div>
      <div class="card">
        <div class="label"><span class="pill o">Obs</span> Avg latency</div>
        <div class="value">{_int(totals.get("avg_latency_ms"))}<span class="sub"> ms</span></div>
      </div>
      <div class="card">
        <div class="label"><span class="pill s">Sec</span> Flagged / blocked</div>
        <div class="value">{_int(totals.get("flagged"))} / {_int(totals.get("blocked"))}</div>
      </div>
    </div>
    <div class="cols">
      <div class="card">
        <div class="label">Spend by model</div>
        <table>
          <thead><tr><th>Model</th><th>Calls</th><th>Cost</th><th>Avg ms</th></tr></thead>
          <tbody>{_rows(models, model_cols)}</tbody>
        </table>
      </div>
      <div class="card">
        <div class="label">Spend by feature</div>
        <table>
          <thead><tr><th>Feature</th><th>Calls</th><th>Cost</th></tr></thead>
          <tbody>{_rows(features, feature_cols)}</tbody>
        </table>
      </div>
      <div class="card">
        <div class="label">Security findings</div>
        <table>
          <thead><tr><th>Scanner</th><th>Severity</th><th>Count</th></tr></thead>
          <tbody>{_rows(findings, finding_cols)}</tbody>
        </table>
      </div>
    </div>
    <div class="card" style="margin-top:14px">
      <div class="label">Recent traces</div>
      <table>
        <thead><tr><th>When</th><th>Feature</th><th>Model</th><th>Status</th><th>Cost</th><th>ms</th><th>Security</th><th>Preview</th></tr></thead>
        <tbody>{_rows(recent, recent_cols)}</tbody>
      </table>
    </div>
  </main>
  <footer>
    Point any OpenAI-compatible SDK at this process. Tag calls with
    <code>X-COS-Feature</code>, <code>X-COS-Project</code>, <code>X-COS-User</code>.
    <code>X-Cosen-*</code> aliases are also accepted.
  </footer>
</body>
</html>
"""
