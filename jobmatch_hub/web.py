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


CSS = """
:root {
  color-scheme: dark;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #08090a;
  color: #f7f8f8;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at 12% 8%, rgba(94, 106, 210, .24), transparent 34rem),
    linear-gradient(180deg, #111216 0%, #08090a 42%);
}
.shell { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 22px 0 44px; }
.nav { display: flex; justify-content: space-between; align-items: center; min-height: 52px; color: #d7d9df; }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 720; }
.mark { width: 18px; height: 18px; border-radius: 5px; background: #5e6ad2; box-shadow: 0 0 28px rgba(94,106,210,.8); }
.nav-links { display: flex; gap: 18px; font-size: 14px; }
a { color: #aeb4ff; text-decoration: none; }
.hero { display: grid; grid-template-columns: minmax(0, 1fr) 310px; gap: 26px; align-items: end; padding: 62px 0 34px; }
.eyebrow { color: #aeb4ff; margin: 0 0 12px; font-size: 13px; text-transform: uppercase; letter-spacing: .08em; }
h1 { margin: 0; max-width: 850px; font-size: clamp(38px, 7vw, 76px); line-height: .96; letter-spacing: 0; }
.subhead { max-width: 720px; color: #a8acb7; font-size: 18px; line-height: 1.65; margin: 22px 0 0; }
.panel, .hero-panel, .job-card {
  background: rgba(255,255,255,.065);
  border: 1px solid rgba(255,255,255,.11);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.07), 0 24px 70px rgba(0,0,0,.32);
  backdrop-filter: blur(18px);
  border-radius: 8px;
}
.hero-panel { padding: 22px; display: grid; gap: 12px; }
.hero-panel span, .score-card span { color: #8f96a8; font-size: 13px; }
.hero-panel strong { font-size: 18px; line-height: 1.35; }
.hero-panel b { font-size: 54px; color: #fff; }
.grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(360px, .9fr); gap: 18px; }
.panel { padding: 18px; }
form { display: grid; gap: 10px; }
label { color: #dfe1e7; font-weight: 650; font-size: 14px; }
textarea {
  min-height: 180px;
  resize: vertical;
  width: 100%;
  color: #f7f8f8;
  background: rgba(8,9,10,.72);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 7px;
  padding: 13px;
  line-height: 1.5;
}
.actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; color: #8f96a8; font-size: 13px; }
button {
  border: 0;
  border-radius: 7px;
  background: #5e6ad2;
  color: white;
  padding: 11px 16px;
  font-weight: 720;
  cursor: pointer;
}
.score-card { display: flex; justify-content: space-between; align-items: center; gap: 16px; border-bottom: 1px solid rgba(255,255,255,.1); padding-bottom: 18px; }
.score-card strong { display: block; font-size: 66px; line-height: 1; margin-top: 8px; }
.score-card p { color: #dfe1e7; margin: 0; text-align: right; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 18px 0; }
h2, h3 { margin: 0 0 12px; letter-spacing: 0; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; align-content: start; min-height: 36px; }
.chip { border-radius: 999px; padding: 6px 9px; font-size: 12px; border: 1px solid rgba(255,255,255,.12); }
.chip.matched { background: rgba(50, 185, 126, .14); color: #9de7bd; }
.chip.missing { background: rgba(248, 113, 113, .14); color: #ffb4b4; }
.empty { color: #8f96a8; }
.priority ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.priority li { display: flex; justify-content: space-between; gap: 16px; padding: 10px 0; border-top: 1px solid rgba(255,255,255,.08); }
.advice { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; margin-top: 18px; }
.advice p, .advice li { color: #c7cad3; line-height: 1.65; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 18px; }
.job-card { padding: 16px; display: grid; gap: 10px; }
.job-card span { color: #8f96a8; font-size: 13px; }
.job-card strong { display: block; margin-top: 4px; }
.job-card b { color: #aeb4ff; font-size: 28px; }
.job-card p, .path { color: #9da3b2; margin: 0; }
.path { margin-top: 14px; }
.error { border: 1px solid rgba(255, 120, 120, .4); color: #ffd1d1; background: rgba(120, 20, 20, .2); padding: 12px; border-radius: 7px; margin-bottom: 14px; }
code { color: #c9ceff; }
@media (max-width: 880px) {
  .hero, .grid, .advice { grid-template-columns: 1fr; }
  .cards { grid-template-columns: 1fr; }
  .nav { align-items: flex-start; gap: 12px; flex-direction: column; }
}
@media (max-width: 560px) {
  .shell { width: min(100% - 22px, 1180px); }
  .split { grid-template-columns: 1fr; }
  .score-card { align-items: flex-start; flex-direction: column; }
  .score-card p { text-align: left; }
}
"""
