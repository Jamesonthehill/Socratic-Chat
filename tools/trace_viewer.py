#!/usr/bin/env python3
"""Local browser for Socratic Chat LLM request snapshots."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from typing import Any
from urllib.parse import parse_qs, quote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT_DIR = PROJECT_ROOT / "backend" / "storage" / "pipeline_prompts"
PHASE_ORDER = {
    "classifier": 1,
    "answer-evaluation": 2,
    "tutor-generation": 3,
    "learning-completion": 4,
    "conversation-transition": 5,
}


def read_traces(prompt_dir: Path) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not prompt_dir.exists():
        return []

    for path in prompt_dir.glob("*.json"):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        trace_id = str(snapshot.get("trace_id") or "unknown")
        snapshot["_path"] = path.name
        grouped[trace_id].append(snapshot)

    traces: list[dict[str, Any]] = []
    for trace_id, snapshots in grouped.items():
        snapshots.sort(
            key=lambda item: (
                PHASE_ORDER.get(str(item.get("phase")), 99),
                str(item.get("captured_at") or ""),
            )
        )
        timestamps = [str(item.get("updated_at") or item.get("captured_at") or "") for item in snapshots]
        traces.append(
            {
                "trace_id": trace_id,
                "conversation_id": next(
                    (item.get("conversation_id") for item in snapshots if item.get("conversation_id")), None
                ),
                "updated_at": max(timestamps, default=""),
                "snapshots": snapshots,
            }
        )
    traces.sort(key=lambda item: item["updated_at"], reverse=True)
    return traces


def delete_trace(prompt_dir: Path, trace_id: str) -> int:
    """Remove only snapshot files whose stored trace ID matches exactly."""
    deleted = 0
    if not prompt_dir.is_dir():
        return deleted
    for path in prompt_dir.glob("*.json"):
        if path.is_symlink():
            continue
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if snapshot.get("trace_id") == trace_id:
            path.unlink()
            deleted += 1
    return deleted


def pretty_time(value: Any) -> str:
    if not value:
        return "Unknown time"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%b %d, %Y · %I:%M:%S %p")
    except ValueError:
        return str(value)


def json_block(value: Any) -> str:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return f'<pre class="data">{escape(rendered)}</pre>'


def render_messages(messages: Any) -> str:
    if not isinstance(messages, list) or not messages:
        return '<p class="empty">No messages were captured.</p>'
    cards = []
    for index, message in enumerate(messages, start=1):
        role = escape(str(message.get("role", "unknown"))) if isinstance(message, dict) else "unknown"
        content = message.get("content", "") if isinstance(message, dict) else message
        cards.append(
            '<article class="message">'
            f'<div class="message-head"><span class="role {role}">{role}</span>'
            f'<span>Message {index}</span></div>'
            f'<pre>{escape(str(content))}</pre>'
            "</article>"
        )
    return "".join(cards)


def render_phase(snapshot: dict[str, Any]) -> str:
    phase = escape(str(snapshot.get("phase") or "unknown"))
    provider = escape(str(snapshot.get("provider") or "unknown"))
    request = snapshot.get("request") if isinstance(snapshot.get("request"), dict) else {}
    result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
    model = escape(str(request.get("model") or "unknown"))
    latency = result.get("latency_ms")
    latency_text = f"{latency / 1000:.2f}s" if isinstance(latency, (int, float)) else "Waiting"
    settings = {key: value for key, value in request.items() if key != "messages"}
    copy_payload = escape(json.dumps(request, ensure_ascii=False, indent=2, default=str))
    raw = result.get("raw_response")
    final = result.get("final_response")
    parsed = result.get("parsed_output")
    validation = {
        key: value
        for key, value in result.items()
        if key not in {"raw_response", "final_response", "parsed_output", "latency_ms"}
    }

    output_parts = []
    if raw is not None:
        output_parts.append(
            '<section class="output"><h4>Raw Qwen response</h4>'
            f'<pre>{escape(str(raw))}</pre></section>'
        )
    if parsed is not None:
        output_parts.append('<section class="output"><h4>Parsed pipeline result</h4>' + json_block(parsed) + "</section>")
    if final is not None and final != raw:
        output_parts.append(
            '<section class="output"><h4>Final answer shown to the student</h4>'
            f'<pre>{escape(str(final))}</pre></section>'
        )
    if validation:
        output_parts.append('<section class="output"><h4>Validation</h4>' + json_block(validation) + "</section>")
    if not output_parts:
        output_parts.append('<p class="waiting">The request is captured. Waiting for the model result…</p>')

    return (
        '<section class="phase">'
        '<div class="phase-title">'
        f'<div><span class="phase-name">{phase}</span><span class="provider">{provider} · {model}</span></div>'
        '<div class="phase-actions">'
        '<button class="copy-request" type="button" aria-label="Copy complete model request" aria-live="polite">Copy request</button>'
        f'<span class="latency">{latency_text}</span></div>'
        "</div>"
        f'<pre class="copy-payload" hidden>{copy_payload}</pre>'
        '<details><summary>Request settings</summary>' + json_block(settings) + "</details>"
        f'<details><summary>Exact messages sent to Qwen ({len(request.get("messages") or [])})</summary>'
        + render_messages(request.get("messages"))
        + "</details>"
        + "".join(output_parts)
        + "</section>"
    )


def render_page(prompt_dir: Path, selected_trace: str | None, csrf_token: str = "") -> str:
    traces = read_traces(prompt_dir)
    selected = next((trace for trace in traces if trace["trace_id"] == selected_trace), None)
    if selected is None and traces:
        selected = traces[0]

    trace_links = []
    for trace in traces:
        active = " active" if selected and trace["trace_id"] == selected["trace_id"] else ""
        trace_id = escape(trace["trace_id"])
        encoded_id = quote(trace["trace_id"], safe="")
        phases = len(trace["snapshots"])
        trace_links.append(
            f'<a class="trace{active}" href="/?trace={encoded_id}">'
            f'<strong>{trace_id}</strong><span>{phases} phase{"s" if phases != 1 else ""}</span>'
            f'<small>{escape(pretty_time(trace["updated_at"]))}</small></a>'
        )

    if selected:
        delete_button = (
            '<form action="/delete" method="post" '
            'onsubmit="return confirm(\'Delete this trace and its saved prompts? This cannot be undone.\')">'
            f'<input type="hidden" name="trace" value="{escape(selected["trace_id"], quote=True)}">'
            f'<input type="hidden" name="token" value="{escape(csrf_token, quote=True)}">'
            '<button class="delete" type="submit" title="Delete this trace">Delete trace</button>'
            '</form>'
        ) if csrf_token else ""
        content = (
            '<header class="content-head"><div><p class="eyebrow">Selected trace</p>'
            f'<h2>{escape(selected["trace_id"])}</h2>'
            f'<p>Conversation: {escape(str(selected.get("conversation_id") or "not assigned"))}</p></div>'
            '<div class="header-actions"><div class="live"><i></i> Live</div>'
            + delete_button + '</div></header>'
            + "".join(render_phase(snapshot) for snapshot in selected["snapshots"])
        )
    else:
        content = (
            '<div class="blank"><h2>No traces yet</h2>'
            '<p>Send a message in Socratic Chat. Its prompt and result will appear here automatically.</p></div>'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Socratic Chat · LLM Trace Viewer</title>
  <style>
    :root {{ color-scheme: dark; --bg:#08111f; --panel:#101c2f; --line:#263653; --text:#eaf1ff; --muted:#93a4bf; --accent:#62e6c3; --violet:#9a8cff; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif; }}
    .layout {{ min-height:100vh; display:grid; grid-template-columns:310px minmax(0,1fr); }}
    .layout.sidebar-collapsed {{ grid-template-columns:minmax(0,1fr); }} .layout.sidebar-collapsed aside {{ display:none; }}
    aside {{ border-right:1px solid var(--line); padding:24px 18px; position:sticky; top:0; height:100vh; overflow:auto; background:var(--bg); }}
    .aside-head {{ display:flex; align-items:center; justify-content:space-between; gap:8px; }}
    h1 {{ font-size:20px; margin:0; }} aside>p {{ color:var(--muted); margin:6px 0 22px; }}
    .sidebar-close,.sidebar-toggle {{ cursor:pointer; color:var(--text); background:#17243a; border:1px solid var(--line); border-radius:8px; font:inherit; }}
    .sidebar-close {{ width:30px; height:30px; font-size:20px; line-height:1; }}
    .sidebar-toggle {{ display:inline-flex; align-items:center; gap:9px; padding:7px 11px; }}
    .sidebar-toggle:hover,.sidebar-close:hover {{ border-color:var(--violet); }}
    .toolbar {{ margin-bottom:20px; }} .sidebar-backdrop {{ display:none; }}
    .trace {{ display:grid; gap:3px; padding:12px; margin:8px 0; color:var(--text); text-decoration:none; border:1px solid transparent; border-radius:10px; background:#0d1829; }}
    .trace:hover,.trace.active {{ border-color:var(--violet); background:#151f3b; }} .trace strong {{ overflow:hidden; text-overflow:ellipsis; }}
    .trace span,.trace small {{ color:var(--muted); }} main {{ padding:34px; max-width:1200px; width:100%; margin:auto; }}
    .content-head,.phase-title {{ display:flex; align-items:center; justify-content:space-between; gap:20px; }}
    .content-head {{ margin-bottom:22px; }} .content-head h2 {{ margin:0; font-size:24px; }} .content-head p {{ color:var(--muted); margin:4px 0; }}
    .eyebrow {{ text-transform:uppercase; letter-spacing:.12em; font-size:11px; color:var(--accent)!important; font-weight:800; }}
    .live {{ color:var(--muted); white-space:nowrap; }} .live i {{ display:inline-block; width:8px; height:8px; background:var(--accent); border-radius:50%; margin-right:7px; }}
    .header-actions {{ display:flex; align-items:center; gap:16px; }} .delete {{ color:var(--muted); background:transparent; border:0; cursor:pointer; padding:6px 0; font:inherit; text-decoration:underline; text-underline-offset:3px; }}
    .delete:hover,.delete:focus-visible {{ color:#ffb8b8; }}
    .phase {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:20px; margin:16px 0; box-shadow:0 12px 30px #0003; }}
    .phase-actions {{ display:flex; align-items:center; gap:10px; }}
    .copy-request {{ color:var(--muted); background:transparent; border:1px solid var(--line); border-radius:7px; cursor:pointer; padding:5px 9px; font:inherit; white-space:nowrap; }}
    .copy-request:hover,.copy-request:focus-visible {{ color:var(--text); border-color:var(--violet); }}
    .phase-name {{ text-transform:capitalize; font-size:18px; font-weight:800; display:block; }} .provider {{ color:var(--muted); }}
    .latency {{ background:#182743; border:1px solid var(--line); padding:6px 10px; border-radius:999px; font-weight:700; }}
    details {{ border-top:1px solid var(--line); margin-top:18px; padding-top:14px; }} summary {{ cursor:pointer; color:#cbd7ec; font-weight:700; margin-bottom:12px; }}
    .message,.output {{ border:1px solid var(--line); border-radius:10px; margin:10px 0; overflow:hidden; background:#0b1627; }}
    .message-head {{ display:flex; justify-content:space-between; color:var(--muted); padding:8px 12px; border-bottom:1px solid var(--line); font-size:12px; }}
    .role {{ font-weight:800; text-transform:uppercase; }} .role.system {{ color:var(--violet); }} .role.user {{ color:var(--accent); }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; margin:0; padding:14px; font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .data {{ max-height:420px; overflow:auto; background:#07101d; border-radius:8px; }} .output h4 {{ margin:0; padding:10px 14px; border-bottom:1px solid var(--line); color:var(--accent); }}
    .waiting,.empty {{ color:var(--muted); font-style:italic; }} .blank {{ text-align:center; margin-top:30vh; }} .blank p {{ color:var(--muted); }}
    .copy-payload[hidden] {{ display:none; }}
    @media(max-width:800px) {{
      .layout,.layout.sidebar-collapsed {{ display:block; }}
      aside,.layout.sidebar-collapsed aside {{ display:block; position:fixed; z-index:30; left:0; top:0; width:min(310px,85vw); height:100vh; visibility:hidden; transform:translateX(-100%); transition:transform .2s ease,visibility .2s ease; box-shadow:12px 0 28px #0005; }}
      .layout:not(.sidebar-collapsed) aside {{ visibility:visible; transform:translateX(0); }}
      .layout:not(.sidebar-collapsed) .sidebar-backdrop {{ display:block; position:fixed; inset:0; z-index:20; width:100%; border:0; background:#0009; cursor:pointer; }}
      main {{ padding:20px 12px; }} .content-head {{ align-items:flex-start; flex-direction:column; }}
    }}
  </style>
</head>
<body><div class="layout" id="layout"><aside id="trace-sidebar"><div class="aside-head"><h1>LLM Trace Viewer</h1><button class="sidebar-close" id="sidebar-close" type="button" aria-label="Close trace list">×</button></div><p>Exact prompts, outputs, parsing, and timing.</p>{''.join(trace_links)}</aside><button class="sidebar-backdrop" id="sidebar-backdrop" type="button" aria-label="Close trace list"></button><main><div class="toolbar"><button class="sidebar-toggle" id="sidebar-toggle" type="button" aria-controls="trace-sidebar" aria-expanded="true"><span aria-hidden="true">☰</span> Traces</button></div>{content}</main></div>
<script>
  const layout = document.getElementById('layout');
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebarState = sessionStorage.getItem('trace-viewer-sidebar');
  const initiallyClosed = sidebarState === 'closed' || (!sidebarState && matchMedia('(max-width: 800px)').matches);
  layout.classList.toggle('sidebar-collapsed', initiallyClosed);
  sidebarToggle.setAttribute('aria-expanded', String(!initiallyClosed));
  function setSidebarOpen(open) {{
    layout.classList.toggle('sidebar-collapsed', !open);
    sidebarToggle.setAttribute('aria-expanded', String(open));
    sessionStorage.setItem('trace-viewer-sidebar', open ? 'open' : 'closed');
  }}
  sidebarToggle.addEventListener('click', () => setSidebarOpen(layout.classList.contains('sidebar-collapsed')));
  document.getElementById('sidebar-close').addEventListener('click', () => setSidebarOpen(false));
  document.getElementById('sidebar-backdrop').addEventListener('click', () => setSidebarOpen(false));
  document.addEventListener('keydown', event => {{ if (event.key === 'Escape') setSidebarOpen(false); }});
  document.querySelectorAll('.trace').forEach(link => link.addEventListener('click', () => {{
    if (matchMedia('(max-width: 800px)').matches) sessionStorage.setItem('trace-viewer-sidebar', 'closed');
  }}));
  document.querySelectorAll('details').forEach((section, index) => {{
    const key = 'trace-viewer:' + location.search + ':' + index;
    section.open = sessionStorage.getItem(key) === 'open';
    section.addEventListener('toggle', () => sessionStorage.setItem(key, section.open ? 'open' : 'closed'));
  }});
  document.querySelectorAll('.copy-request').forEach(button => button.addEventListener('click', async () => {{
    const requestJson = button.closest('.phase').querySelector('.copy-payload').textContent;
    try {{
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(requestJson);
      }} else {{
        const field = document.createElement('textarea');
        field.value = requestJson;
        document.body.appendChild(field);
        field.select();
        const copied = document.execCommand('copy');
        field.remove();
        if (!copied) throw new Error('Clipboard unavailable');
      }}
      button.textContent = 'Copied';
    }} catch (error) {{
      button.textContent = 'Copy failed';
    }}
    setTimeout(() => {{ button.textContent = 'Copy request'; }}, 1800);
  }}));
  setTimeout(() => window.location.reload(), 3000);
</script>
</body></html>"""


def make_handler(prompt_dir: Path) -> type[BaseHTTPRequestHandler]:
    csrf_token = secrets.token_urlsafe(32)

    class TraceHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in {"/", "/index.html"}:
                self.send_error(404)
                return
            selected_trace = parse_qs(parsed.query).get("trace", [None])[0]
            body = render_page(prompt_dir, selected_trace, csrf_token).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/delete":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400)
                return
            if not 0 < length <= 4096:
                self.send_error(400)
                return
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            submitted_token = form.get("token", [""])[0]
            trace_id = form.get("trace", [""])[0]
            if not secrets.compare_digest(submitted_token, csrf_token):
                self.send_error(403)
                return
            if not trace_id or trace_id not in {trace["trace_id"] for trace in read_traces(prompt_dir)}:
                self.send_error(404)
                return
            delete_trace(prompt_dir, trace_id)
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return

    return TraceHandler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--prompt-dir", type=Path, default=DEFAULT_PROMPT_DIR)
    args = parser.parse_args()

    prompt_dir = args.prompt_dir.expanduser().resolve()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(prompt_dir))
    print(f"LLM Trace Viewer: http://{args.host}:{args.port}")
    print(f"Reading snapshots from: {prompt_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
