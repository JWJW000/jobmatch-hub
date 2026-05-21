from __future__ import annotations

import argparse
from pathlib import Path

from .analyzer import analyze_jobs, load_jobs
from .report import write_outputs
from .web import run_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m jobmatch_hub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser("score", help="Score a resume against CSV or JSON job descriptions")
    score_parser.add_argument("--resume", required=True, help="Path to resume Markdown/text file")
    score_parser.add_argument("--jobs", required=True, help="Path to jobs CSV or JSON file")
    score_parser.add_argument("--out", required=True, help="Output directory for JSON and Markdown reports")

    web_parser = subparsers.add_parser("web", help="Start local Web UI")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8788)
    web_parser.add_argument("--out", default="jobmatch-hub/out", help="Directory where Web UI writes reports")

    args = parser.parse_args(argv)
    if args.command == "score":
        return score_command(args.resume, args.jobs, args.out)
    if args.command == "web":
        run_server(host=args.host, port=args.port, out_dir=args.out)
        return 0
    parser.error("unknown command")
    return 2


def score_command(resume_path: str, jobs_path: str, out_dir: str) -> int:
    resume_file = Path(resume_path).expanduser()
    resume_text = resume_file.read_text(encoding="utf-8")
    results = analyze_jobs(resume_text, load_jobs(jobs_path))
    json_path, md_path = write_outputs(results, out_dir)
    print(f"JSON written to {json_path}")
    print(f"Markdown report written to {md_path}")
    print(f"Top match: {results[0].company} / {results[0].title} / {results[0].score}")
    return 0
