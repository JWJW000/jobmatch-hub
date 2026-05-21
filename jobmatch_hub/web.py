from __future__ import annotations

import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .analyzer import JobMatchResult, analyze_jobs, parse_jobs_text
from .report import render_markdown_report, write_outputs


EXAMPLE_RESUME = """Senior backend engineer with 6 years of Java, Spring Boot, Redis, PostgreSQL and Docker experience.
Built high-concurrency microservice platforms, CI/CD pipelines, Prometheus dashboards and AI RAG prototypes with LLM integrations.
Led performance optimization and mentoring for ecommerce and SaaS teams."""

EXAMPLE_JOBS = """Title: Senior Java Platform Engineer
Company: Northstar AI
Location: Remote
Description: Build distributed Java Spring Boot services for an AI platform. Requires Redis, PostgreSQL, Docker, Kubernetes, Prometheus, CI/CD, LLM and RAG experience. Senior production ownership preferred.
---
Title: Frontend React Engineer
Company: Canvas Labs
Location: Shanghai
Description: React, TypeScript, Vue migration, design system and SaaS dashboard work. Docker and API collaboration are bonuses."""

LAST_RESULTS: list[JobMatchResult] = []
LAST_REPORT = ""
LAST_PATH = ""


def run_server(host: str = "127.0.0.1", port: int = 8788, out_dir: str = "jobmatch-hub/out") -> None:
    output_dir = Path(out_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    class Handler(JobMatchHandler):
        report_dir = output_dir

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"JobMatch Hub Web UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


class JobMatchHandler(BaseHTTPRequestHandler):
    report_dir: Path

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self._send_html(render_page())
            return
        if self.path == "/api/last":
            self._send_json({"path": LAST_PATH, "results": [item.to_dict() for item in LAST_RESULTS], "markdown": LAST_REPORT})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/score":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = parse_qs(body)
        resume_text = (params.get("resume") or [""])[0]
        jobs_text = (params.get("jobs") or [""])[0]
        try:
            results = analyze_jobs(resume_text, parse_jobs_text(jobs_text))
            _, md_path = write_outputs(results, self.report_dir)
            global LAST_RESULTS, LAST_REPORT, LAST_PATH
            LAST_RESULTS = results
            LAST_REPORT = render_markdown_report(results)
            LAST_PATH = str(md_path)
            self._send_html(render_page(resume_text=resume_text, jobs_text=jobs_text, results=results, report_path=str(md_path)))
        except Exception as exc:  # noqa: BLE001 - local UI should surface validation errors.
            self._send_html(render_page(resume_text=resume_text, jobs_text=jobs_text, error=str(exc)), HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def render_page(
    resume_text: str = EXAMPLE_RESUME,
    jobs_text: str = EXAMPLE_JOBS,
    results: list[JobMatchResult] | None = None,
    report_path: str = "",
    error: str = "",
) -> str:
    shown_results = results if results is not None else LAST_RESULTS
    top = shown_results[0] if shown_results else None
    priority_html = render_priority_list(shown_results)
    cards_html = render_result_cards(shown_results)
    advice_html = render_advice(top)
    missing_html = render_chips(top.missing_skills if top else [], "missing") if top else '<span class="empty">Run a match to see gaps</span>'
    matched_html = render_chips(top.matched_skills if top else [], "matched") if top else '<span class="empty">No matches yet</span>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JobMatch Hub</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="shell">
    <nav class="nav">
      <div class="brand"><span class="mark"></span>JobMatch Hub</div>
      <div class="nav-links"><a href="#score">Score</a><a href="#priority">Priority</a><a href="#advice">Advice</a></div>
    </nav>
    <header class="hero">
      <div>
        <p class="eyebrow">Resume + JD intelligence</p>
        <h1>招聘信息聚合与简历匹配系统</h1>
        <p class="subhead">导入简历和岗位 JD，快速计算匹配度、技能缺口、投递优先级，并生成定制投递话术。</p>
      </div>
      <div class="hero-panel">
        <span>Top match</span>
        <strong>{html.escape(top.company + " / " + top.title) if top else "Awaiting analysis"}</strong>
        <b>{top.score if top else "--"}</b>
      </div>
    </header>

    <main id="score" class="grid">
      <section class="panel input-panel">
        <form method="post" action="/score">
          <label>Resume</label>
          <textarea name="resume" spellcheck="false">{html.escape(resume_text)}</textarea>
          <label>Job descriptions</label>
          <textarea name="jobs" spellcheck="false">{html.escape(jobs_text)}</textarea>
          <div class="actions">
            <button type="submit">Analyze Matches</button>
            <span>Supports manual text, JSON, and separator lines with <code>---</code>.</span>
          </div>
        </form>
      </section>

      <section class="panel result-panel">
        {f'<div class="error">{html.escape(error)}</div>' if error else ''}
        <div class="score-card">
          <div>
            <span>Match score</span>
            <strong>{top.score if top else "--"}</strong>
          </div>
          <p>{html.escape(top.priority) if top else "Paste resume and JD to start."}</p>
        </div>
        <div class="split">
          <div><h3>Matched skills</h3><div class="chips">{matched_html}</div></div>
          <div><h3>Missing skills</h3><div class="chips">{missing_html}</div></div>
        </div>
        <div id="priority" class="priority">
          <h3>投递优先级</h3>
          {priority_html}
        </div>
      </section>
    </main>

    <section id="advice" class="panel advice">
      <div>
        <h2>定制投递话术</h2>
        <p>{html.escape(top.pitch) if top else "分析后会生成可直接改写的投递开场。"}</p>
      </div>
      <div>
        <h2>简历优化建议</h2>
        {advice_html}
      </div>
    </section>

    <section class="cards">{cards_html}</section>
    {f'<p class="path">Report written to <code>{html.escape(report_path)}</code></p>' if report_path else ''}
  </div>
</body>
</html>"""


def render_result_cards(results: list[JobMatchResult]) -> str:
    if not results:
        return ""
    return "\n".join(
        f"""<article class="job-card">
  <div><span>{html.escape(result.company)}</span><strong>{html.escape(result.title)}</strong></div>
  <b>{result.score}</b>
  <p>{html.escape(result.location)} · {html.escape(result.priority)}</p>
</article>"""
        for result in results
    )


def render_priority_list(results: list[JobMatchResult]) -> str:
    if not results:
        return '<p class="empty">No priority list yet.</p>'
    return "<ol>" + "".join(
        f"<li><span>{html.escape(result.company)} · {html.escape(result.title)}</span><b>{result.score}</b></li>" for result in results
    ) + "</ol>"


def render_chips(skills: list[str], kind: str) -> str:
    if not skills:
        return '<span class="empty">None</span>'
    return "".join(f'<span class="chip {kind}">{html.escape(skill)}</span>' for skill in skills)


def render_advice(result: JobMatchResult | None) -> str:
    if not result:
        return "<p>分析后会按岗位生成优化建议。</p>"
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in result.resume_advice) + "</ul>"




def load_open_design_tokens() -> str:
    """Load tokens adapted from nexu-io/open-design/design-systems/x-ai."""
    candidates = [
        Path(__file__).resolve().parents[1] / "open-design" / "x-ai-tokens.css",
        Path.cwd() / "open-design" / "x-ai-tokens.css",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return ""


CSS = load_open_design_tokens() + """
/*
 * UI integration note:
 * - Design tokens are adapted from nexu-io/open-design/design-systems/x-ai/tokens.css.
 * - Components follow Open Design's xAI reference: warm near-black canvas,
 *   monochrome command-like UI, opacity hierarchy, sharp panels, and sparse rhythm.
 */
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at 12% 8%, rgba(255,255,255,.06), transparent 30rem),
    linear-gradient(180deg, color-mix(in oklab, var(--bg), white 4%) 0%, var(--bg) 42%);
  color: var(--fg);
  font-family: var(--font-body);
  line-height: var(--leading-body);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
a { color: var(--fg); text-decoration: none; }
.shell { max-width: var(--container-max); margin: 0 auto; padding: var(--space-6) var(--container-gutter-desktop) var(--space-12); }
.nav { display: flex; justify-content: space-between; align-items: center; min-height: 52px; color: var(--fg-2); }
.brand { display: flex; align-items: center; gap: var(--space-3); font-weight: 700; font-family: var(--font-display); }
.mark { width: 18px; height: 18px; border-radius: var(--radius-sm); background: var(--accent); }
.nav-links { display: flex; gap: var(--space-5); font-size: var(--text-sm); }
.hero { display: grid; grid-template-columns: minmax(0, 1fr) 310px; gap: var(--space-8); align-items: end; padding: var(--section-y-tablet) 0 var(--space-8); }
.eyebrow { color: var(--fg-2); margin: 0 0 var(--space-3); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: .12em; font-family: var(--font-display); }
h1 { margin: 0; max-width: 860px; font-family: var(--font-display); font-size: clamp(38px, 7vw, var(--text-4xl)); line-height: var(--leading-tight); letter-spacing: var(--tracking-display); font-weight: 500; }
.subhead { max-width: 720px; color: var(--fg-2); font-size: var(--text-lg); line-height: 1.65; margin: var(--space-5) 0 0; }
.panel, .hero-panel, .job-card {
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--elev-raised);
  border-radius: var(--radius-md);
}
.hero-panel { padding: var(--space-6); display: grid; gap: var(--space-3); }
.hero-panel span, .score-card span { color: var(--muted); font-size: var(--text-xs); }
.hero-panel strong { font-size: var(--text-base); line-height: 1.35; color: var(--fg-2); font-weight: 500; }
.hero-panel b { font-size: var(--text-4xl); color: var(--fg); font-family: var(--font-display); }
.grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(360px, .9fr); gap: var(--space-5); }
.panel { padding: var(--space-5); }
form { display: grid; gap: var(--space-3); }
label { color: var(--fg); font-weight: 650; font-size: var(--text-sm); }
textarea {
  min-height: 180px;
  resize: vertical;
  width: 100%;
  color: var(--fg);
  background: color-mix(in oklab, var(--bg), black 10%);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-4);
  line-height: 1.5;
  outline: none;
  font-family: var(--font-body);
}
textarea:focus { box-shadow: var(--focus-ring); border-color: transparent; }
.actions { display: flex; align-items: center; gap: var(--space-4); flex-wrap: wrap; color: var(--muted); font-size: var(--text-xs); }
button {
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: var(--accent-on);
  padding: var(--space-3) var(--space-5);
  font-weight: 700;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: .08em;
}
button:hover { background: var(--accent-hover); }
.score-card { display: flex; justify-content: space-between; align-items: center; gap: var(--space-5); border-bottom: 1px solid var(--border-soft); padding-bottom: var(--space-5); }
.score-card strong { display: block; font-size: var(--text-4xl); line-height: 1; margin-top: var(--space-2); font-family: var(--font-display); }
.score-card p { color: var(--fg-2); margin: 0; text-align: right; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin: var(--space-5) 0; }
h2, h3 { margin: 0 0 var(--space-3); letter-spacing: 0; font-family: var(--font-display); font-weight: 500; }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); align-content: start; min-height: 36px; }
.chip { border-radius: var(--radius-pill); padding: 6px 9px; font-size: var(--text-xs); border: 1px solid var(--border); }
.chip.matched { background: rgba(22, 163, 74, .12); color: color-mix(in oklab, var(--success), white 42%); }
.chip.missing { background: rgba(220, 38, 38, .12); color: color-mix(in oklab, var(--danger), white 45%); }
.empty { color: var(--muted); }
.priority ol { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.priority li { display: flex; justify-content: space-between; gap: var(--space-4); padding: var(--space-3) 0; border-top: 1px solid var(--border-soft); }
.advice { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-6); margin-top: var(--space-5); }
.advice p, .advice li { color: var(--fg-2); line-height: 1.65; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); margin-top: var(--space-5); }
.job-card { padding: var(--space-5); display: grid; gap: var(--space-3); }
.job-card span { color: var(--muted); font-size: var(--text-xs); }
.job-card strong { display: block; margin-top: var(--space-1); }
.job-card b { color: var(--fg); font-size: var(--text-2xl); font-family: var(--font-display); }
.job-card p, .path { color: var(--muted); margin: 0; }
.path { margin-top: var(--space-4); }
.error { border: 1px solid color-mix(in oklab, var(--danger), white 35%); color: color-mix(in oklab, var(--danger), white 45%); background: rgba(220, 38, 38, .12); padding: var(--space-4); border-radius: var(--radius-sm); margin-bottom: var(--space-4); }
code { color: var(--fg); font-family: var(--font-mono); }
@media (max-width: 880px) {
  .shell { padding-inline: var(--container-gutter-tablet); }
  .hero, .grid, .advice { grid-template-columns: 1fr; }
  .cards { grid-template-columns: 1fr; }
  .nav { align-items: flex-start; gap: var(--space-3); flex-direction: column; }
}
@media (max-width: 560px) {
  .shell { padding-inline: var(--container-gutter-phone); }
  .split { grid-template-columns: 1fr; }
  .score-card { align-items: flex-start; flex-direction: column; }
  .score-card p { text-align: left; }
}
"""
