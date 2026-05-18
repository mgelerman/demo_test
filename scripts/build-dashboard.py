"""Build a self-contained HTML evidence dashboard from Allure JSON results.

Reads ``reports/allure-results/*-result.json`` for step hierarchy and
``reports/evidence/`` for video, trace, and log artefacts. Outputs a single
``reports/dashboard.html`` that can be opened by double-clicking (no server).

Usage::

    python scripts/build-dashboard.py            # default paths
    python scripts/build-dashboard.py --out reports/dashboard.html
"""

from __future__ import annotations

import argparse
import base64
import html as html_mod
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "reports" / "allure-results"
EVIDENCE_DIR = REPO_ROOT / "reports" / "evidence"
DEFAULT_OUT = REPO_ROOT / "reports" / "dashboard.html"

LITE_MODE = False

PLACEHOLDER_SVG = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='160'"
    " fill='%23e5e7eb'%3E%3Crect width='240' height='160' rx='8'/%3E"
    "%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle'"
    " fill='%236b7280' font-size='13' font-family='sans-serif'%3E"
    "screenshot%3C/text%3E%3C/svg%3E"
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_allure_results(results_dir: Path) -> list[dict]:
    results = []
    for p in sorted(results_dir.glob("*-result.json")):
        try:
            results.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    results.sort(key=lambda r: r.get("start", 0))
    return results


def find_latest_evidence(evidence_dir: Path, test_name: str) -> Path | None:
    """Find the most recent evidence subfolder for a test."""
    for candidate in evidence_dir.iterdir():
        if not candidate.is_dir() or candidate.name.startswith("_"):
            continue
        clean = candidate.name.lower().replace("-", "_").replace("[", "_").replace("]", "")
        if test_name.lower().replace("[", "_").replace("]", "") in clean:
            subs = sorted(candidate.iterdir(), reverse=True)
            return subs[0] if subs else None
    return None


def find_session_shared(evidence_dir: Path) -> Path | None:
    session_root = evidence_dir / "_session_shared"
    if not session_root.exists():
        return None
    subs = sorted(session_root.iterdir(), reverse=True)
    for d in subs:
        if d.is_dir() and (d / "video.webm").exists():
            return d
    return subs[0] if subs else None


def resolve_attachment(results_dir: Path, source: str) -> Path | None:
    p = results_dir / source
    return p if p.exists() else None


def img_to_b64(path: Path) -> str:
    if LITE_MODE:
        return ""
    return base64.b64encode(path.read_bytes()).decode("ascii")


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def esc(text: str) -> str:
    return html_mod.escape(str(text))


def severity_for(result: dict) -> str:
    for label in result.get("labels", []):
        if label.get("name") == "severity":
            return label["value"]
    return "normal"


def duration_str(result: dict) -> str:
    start = result.get("start", 0)
    stop = result.get("stop", 0)
    if not start or not stop:
        return "?"
    secs = (stop - start) / 1000
    if secs >= 60:
        return f"{secs / 60:.1f}m"
    return f"{secs:.1f}s"


def render_step_screenshots(step: dict, results_dir: Path) -> str:
    imgs = []
    for att in step.get("attachments", []):
        if att.get("type", "").startswith("image/"):
            p = resolve_attachment(results_dir, att["source"])
            if p and p.exists():
                label = esc(att.get("name", "screenshot"))
                if LITE_MODE:
                    src = PLACEHOLDER_SVG
                else:
                    src = f"data:image/png;base64,{img_to_b64(p)}"
                imgs.append(
                    f'<div class="thumb">'
                    f'<a href="{src}" target="_blank">'
                    f'<img src="{src}" alt="{label}" /></a>'
                    f'<span>{label}</span></div>'
                )
    return f'<div class="gallery">{"".join(imgs)}</div>' if imgs else ""


def render_step_text(step: dict, results_dir: Path) -> str:
    texts = []
    for att in step.get("attachments", []):
        if att.get("type", "") == "text/plain":
            p = resolve_attachment(results_dir, att["source"])
            if p and p.exists():
                content = p.read_text(encoding="utf-8", errors="replace").strip()
                if content:
                    name = esc(att.get("name", ""))
                    texts.append(f'<div class="step-text"><b>{name}:</b> {esc(content)}</div>')
    return "".join(texts)


def render_steps(steps: list[dict], results_dir: Path, depth: int = 0) -> str:
    parts = []
    for i, step in enumerate(steps, 1):
        name = esc(step.get("name", f"Step {i}"))
        status = step.get("status", "unknown")
        badge_cls = "pass" if status == "passed" else "fail" if status in ("failed", "broken") else "skip"
        prefix = f"BF-{i}" if depth == 0 else f"{i}"

        parts.append(f'<div class="step depth-{depth}">')
        parts.append(f'<div class="step-header"><span class="step-badge {badge_cls}">{prefix}</span> {name}</div>')

        screenshots = render_step_screenshots(step, results_dir)
        if screenshots:
            parts.append(screenshots)

        text = render_step_text(step, results_dir)
        if text:
            parts.append(text)

        sub_steps = step.get("steps", [])
        if sub_steps:
            parts.append(render_steps(sub_steps, results_dir, depth + 1))

        parts.append("</div>")
    return "".join(parts)


def render_test_card(result: dict, results_dir: Path, evidence_dir: Path, session_dir: Path | None, index: int) -> str:
    name = esc(result.get("name", "Unknown Test"))
    status = result.get("status", "unknown")
    badge_cls = "pass" if status == "passed" else "fail" if status in ("failed", "broken") else "skip"
    dur = duration_str(result)
    sev = severity_for(result)
    desc = result.get("description", "")
    full_name = result.get("fullName", "")
    test_func = full_name.split("#")[-1] if "#" in full_name else full_name.split(".")[-1]

    ev_dir = find_latest_evidence(evidence_dir, test_func)

    parts = [f'<div class="card" data-status="{status}">']
    parts.append(
        f'<div class="card-header" onclick="toggleCard(this)">'
        f'<span class="badge {badge_cls}">{status}</span>'
        f'<span class="card-title">{name}</span>'
        f'<span class="card-meta">'
        f'<span class="sev sev-{sev}">{sev}</span>'
        f'<span class="dur">{dur}</span>'
        f'</span></div>'
    )

    parts.append('<div class="card-body">')

    if desc:
        parts.append(f'<div class="description">{desc}</div>')

    steps = result.get("steps", [])
    if steps:
        parts.append('<div class="steps-section">')
        parts.append(render_steps(steps, results_dir))
        parts.append("</div>")

    # Footer: final state, video, trace, log
    parts.append('<div class="card-footer">')

    # Final state screenshot
    for att in result.get("attachments", []):
        if att.get("type", "").startswith("image/") and "final_state" in att.get("name", ""):
            p = resolve_attachment(results_dir, att["source"])
            if p and p.exists():
                if LITE_MODE:
                    src = PLACEHOLDER_SVG
                else:
                    src = f"data:image/png;base64,{img_to_b64(p)}"
                parts.append(
                    '<div class="footer-item">'
                    '<div class="footer-label">Final State</div>'
                    f'<a href="{src}" target="_blank">'
                    f'<img src="{src}" class="final-img" /></a></div>'
                )
                break

    # Video — embedded player with play-button overlay
    video_path = None
    if ev_dir and (ev_dir / "video.webm").exists():
        video_path = ev_dir / "video.webm"
    elif session_dir and (session_dir / "video.webm").exists():
        video_path = session_dir / "video.webm"
    if video_path:
        size_mb = video_path.stat().st_size / (1024 * 1024)
        video_uri = video_path.resolve().as_uri()
        vid_id = f"vid-{index}"
        poster_attr = ""
        if not LITE_MODE:
            for att in result.get("attachments", []):
                if att.get("type", "").startswith("image/") and "final_state" in att.get("name", ""):
                    fp = resolve_attachment(results_dir, att["source"])
                    if fp and fp.exists():
                        poster_attr = f' poster="data:image/png;base64,{img_to_b64(fp)}"'
                    break
        parts.append(
            '<div class="footer-item" style="min-width:100%">'
            '<div class="footer-label">Video Recording</div>'
            f'<div class="video-wrap" onclick="playVideo(\'{vid_id}\', this)">'
            f'<video id="{vid_id}" preload="metadata"{poster_attr}>'
            f'<source src="{video_uri}" type="video/webm">'
            '</video>'
            '<div class="play-overlay">'
            '<svg viewBox="0 0 80 80" fill="none"><circle cx="40" cy="40" r="38" '
            'fill="rgba(255,255,255,.9)"/><polygon points="32,24 32,56 58,40" '
            'fill="#2563eb"/></svg></div></div>'
            f'<div class="video-size">{size_mb:.1f} MB &mdash; '
            f'<code>{esc(str(video_path.resolve()))}</code></div></div>'
        )

    # Trace
    trace_path = None
    if ev_dir and (ev_dir / "trace.zip").exists():
        trace_path = ev_dir / "trace.zip"
    elif session_dir and (session_dir / "trace.zip").exists():
        trace_path = session_dir / "trace.zip"
    if trace_path:
        parts.append(
            '<div class="footer-item">'
            '<div class="footer-label">Playwright Trace</div>'
            f'<code>{esc(str(trace_path.resolve()))}</code><br/>'
            '<a href="https://trace.playwright.dev/" target="_blank" class="trace-link">'
            'Open Trace Viewer</a> &mdash; drag trace.zip into the viewer.</div>'
        )

    # Log
    log_path = ev_dir / "log.txt" if ev_dir else None
    if log_path and log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace").strip()
        if log_text:
            parts.append(
                '<details class="log-details">'
                '<summary>Full Test Log</summary>'
                f'<pre class="log-pre">{esc(log_text)}</pre></details>'
            )

    parts.append("</div>")  # card-footer
    parts.append("</div>")  # card-body
    parts.append("</div>")  # card
    return "".join(parts)


def build_html(results: list[dict], results_dir: Path, evidence_dir: Path, session_dir: Path | None) -> str:
    now = datetime.now(timezone.utc).strftime("%d-%b-%Y at %H:%M:%S UTC")
    passed = sum(1 for r in results if r.get("status") == "passed")
    failed = sum(1 for r in results if r.get("status") in ("failed", "broken"))
    skipped = len(results) - passed - failed
    total_ms = sum((r.get("stop", 0) - r.get("start", 0)) for r in results)
    total_dur = f"{total_ms / 1000:.0f}s" if total_ms < 60000 else f"{total_ms / 60000:.1f}m"

    cards = []
    for i, r in enumerate(results):
        cards.append(render_test_card(r, results_dir, evidence_dir, session_dir, i))

    return HTML_TEMPLATE.format(
        timestamp=now,
        total=len(results),
        passed=passed,
        failed=failed,
        skipped=skipped,
        duration=total_dur,
        cards="\n".join(cards),
    )


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>E2E Test Evidence Dashboard</title>
<style>
  :root {{
    --bg: #f8f9fb; --card-bg: #fff; --border: #e2e5ea; --text: #1f2937;
    --muted: #6b7280; --accent: #2563eb; --pass: #16a34a; --fail: #dc2626;
    --skip: #d97706; --code-bg: #1e1e2e; --code-fg: #cdd6f4;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
         background: var(--bg); color: var(--text); line-height: 1.5; }}

  .header {{ background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
             color: #fff; padding: 28px 32px; }}
  .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
  .header .sub {{ color: #94a3b8; font-size: 13px; }}
  .stats {{ display: flex; gap: 20px; margin-top: 16px; flex-wrap: wrap; }}
  .stat {{ background: rgba(255,255,255,.08); border-radius: 8px; padding: 12px 20px;
           text-align: center; min-width: 90px; }}
  .stat .num {{ font-size: 28px; font-weight: 700; }}
  .stat .lbl {{ font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #94a3b8; }}
  .stat.pass .num {{ color: #4ade80; }}
  .stat.fail .num {{ color: #f87171; }}
  .stat.skip .num {{ color: #fbbf24; }}

  .toolbar {{ padding: 12px 32px; display: flex; gap: 8px; background: #fff;
              border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }}
  .filter-btn {{ padding: 6px 16px; border: 1px solid var(--border); border-radius: 6px;
                 background: #fff; cursor: pointer; font-size: 13px; font-weight: 500; }}
  .filter-btn:hover {{ background: #f1f5f9; }}
  .filter-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}

  .container {{ max-width: 1100px; margin: 0 auto; padding: 20px 24px; }}

  .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px;
           margin-bottom: 12px; overflow: hidden; }}
  .card-header {{ display: flex; align-items: center; gap: 10px; padding: 14px 18px;
                  cursor: pointer; user-select: none; }}
  .card-header:hover {{ background: #f8fafc; }}
  .card-title {{ flex: 1; font-size: 14px; font-weight: 600; }}
  .card-meta {{ display: flex; gap: 8px; align-items: center; }}
  .badge {{ padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
            text-transform: uppercase; color: #fff; }}
  .badge.pass {{ background: var(--pass); }}
  .badge.fail {{ background: var(--fail); }}
  .badge.skip {{ background: var(--skip); }}

  .sev {{ font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #f1f5f9;
          color: var(--muted); text-transform: uppercase; }}
  .sev-blocker {{ background: #fef2f2; color: var(--fail); }}
  .sev-critical {{ background: #fff7ed; color: #c2410c; }}
  .dur {{ font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }}

  .card-body {{ display: none; padding: 0 18px 18px; }}
  .card.open .card-body {{ display: block; }}

  .description {{ font-size: 13px; color: var(--muted); padding: 10px 14px; background: #f8fafc;
                  border-radius: 6px; margin-bottom: 14px; white-space: pre-line; }}

  .steps-section {{ border-left: 3px solid var(--accent); padding-left: 16px; margin-bottom: 16px; }}
  .step {{ margin-bottom: 12px; }}
  .step.depth-1 {{ margin-left: 20px; border-left: 2px solid #e5e7eb; padding-left: 12px; }}
  .step-header {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
  .step-badge {{ display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 11px;
                 font-weight: 700; margin-right: 6px; color: #fff; }}
  .step-badge.pass {{ background: var(--pass); }}
  .step-badge.fail {{ background: var(--fail); }}
  .step-badge.skip {{ background: var(--skip); }}
  .step-text {{ font-size: 12px; color: var(--muted); margin: 2px 0; }}

  .gallery {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0; }}
  .thumb {{ text-align: center; }}
  .thumb img {{ max-width: 240px; max-height: 160px; border-radius: 5px; border: 1px solid var(--border);
               cursor: zoom-in; transition: transform .15s; }}
  .thumb img:hover {{ transform: scale(1.03); box-shadow: 0 4px 12px rgba(0,0,0,.12); }}
  .thumb span {{ display: block; font-size: 10px; color: var(--muted); margin-top: 2px;
                 max-width: 240px; word-break: break-word; }}

  .card-footer {{ border-top: 1px solid var(--border); padding-top: 14px; margin-top: 10px;
                  display: flex; flex-wrap: wrap; gap: 16px; }}
  .footer-item {{ flex: 1; min-width: 220px; }}
  .footer-label {{ font-size: 12px; font-weight: 700; color: var(--accent); margin-bottom: 4px;
                   text-transform: uppercase; letter-spacing: .3px; }}
  .footer-item code {{ font-size: 11px; background: #f3f4f6; padding: 2px 6px; border-radius: 3px;
                       word-break: break-all; }}
  .file-size {{ font-size: 11px; color: var(--muted); margin-left: 4px; }}
  .final-img {{ max-width: 320px; border-radius: 6px; border: 1px solid var(--border); }}
  .trace-link {{ color: var(--accent); text-decoration: none; font-size: 13px; }}
  .trace-link:hover {{ text-decoration: underline; }}

  .video-wrap {{ position: relative; display: inline-block; max-width: 480px;
                 border-radius: 8px; overflow: hidden; border: 1px solid var(--border);
                 background: #000; cursor: pointer; }}
  .video-wrap video {{ display: block; width: 100%; border-radius: 8px; }}
  .video-wrap .play-overlay {{ position: absolute; inset: 0; display: flex;
                               align-items: center; justify-content: center;
                               background: rgba(0,0,0,.35); transition: opacity .2s; }}
  .video-wrap:hover .play-overlay {{ background: rgba(0,0,0,.2); }}
  .video-wrap .play-overlay svg {{ width: 56px; height: 56px; filter: drop-shadow(0 2px 6px rgba(0,0,0,.4)); }}
  .video-wrap.playing .play-overlay {{ opacity: 0; pointer-events: none; }}
  .video-size {{ font-size: 11px; color: var(--muted); margin-top: 4px; }}

  .log-details {{ margin-top: 8px; }}
  .log-details summary {{ cursor: pointer; font-size: 13px; font-weight: 600; color: var(--accent); }}
  .log-pre {{ background: var(--code-bg); color: var(--code-fg); padding: 14px; border-radius: 6px;
              font-size: 11px; max-height: 400px; overflow: auto; white-space: pre-wrap;
              margin-top: 6px; }}

  .empty {{ text-align: center; padding: 60px 20px; color: var(--muted); }}
</style>
</head>
<body>

<div class="header">
  <h1>E2E Test Evidence Dashboard</h1>
  <div class="sub">Generated {timestamp}</div>
  <div class="stats">
    <div class="stat"><div class="num">{total}</div><div class="lbl">Tests</div></div>
    <div class="stat pass"><div class="num">{passed}</div><div class="lbl">Passed</div></div>
    <div class="stat fail"><div class="num">{failed}</div><div class="lbl">Failed</div></div>
    <div class="stat skip"><div class="num">{skipped}</div><div class="lbl">Skipped</div></div>
    <div class="stat"><div class="num">{duration}</div><div class="lbl">Duration</div></div>
  </div>
</div>

<div class="toolbar">
  <button class="filter-btn active" onclick="filterTests('all')">All ({total})</button>
  <button class="filter-btn" onclick="filterTests('passed')">Passed ({passed})</button>
  <button class="filter-btn" onclick="filterTests('failed')">Failed ({failed})</button>
</div>

<div class="container">
  {cards}
</div>

<script>
function toggleCard(header) {{
  header.parentElement.classList.toggle('open');
}}
function filterTests(status) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('.card').forEach(card => {{
    if (status === 'all') {{ card.style.display = ''; }}
    else {{ card.style.display = card.dataset.status === status ? '' : 'none'; }}
  }});
}}
function playVideo(id, wrap) {{
  var v = document.getElementById(id);
  if (v.paused) {{
    v.play(); wrap.classList.add('playing');
    v.controls = true;
    v.onpause = function() {{ wrap.classList.remove('playing'); }};
    v.onended = function() {{ wrap.classList.remove('playing'); v.controls = false; }};
  }} else {{
    v.pause(); wrap.classList.remove('playing'); v.controls = false;
  }}
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build E2E evidence dashboard")
    parser.add_argument("--results", default=str(RESULTS_DIR), help="Allure results dir")
    parser.add_argument("--evidence", default=str(EVIDENCE_DIR), help="Evidence dir")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output HTML path")
    parser.add_argument("--lite", action="store_true",
                        help="Omit base64 screenshots (placeholder SVGs) for a smaller file")
    args = parser.parse_args()

    global LITE_MODE  # noqa: PLW0603
    LITE_MODE = args.lite

    results_dir = Path(args.results)
    evidence_dir = Path(args.evidence)
    out_path = Path(args.out)

    if not results_dir.exists():
        print(f"No allure-results at {results_dir}, skipping dashboard.", file=sys.stderr)
        return

    results = load_allure_results(results_dir)
    if not results:
        print("No test results found, skipping dashboard.", file=sys.stderr)
        return

    session_dir = find_session_shared(evidence_dir) if evidence_dir.exists() else None

    html = build_html(results, results_dir, evidence_dir, session_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Dashboard written to {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
