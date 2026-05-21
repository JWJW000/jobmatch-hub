from __future__ import annotations

import json
from pathlib import Path

from .analyzer import JobMatchResult


def write_outputs(results: list[JobMatchResult], out_dir: str | Path) -> tuple[Path, Path]:
    output_dir = Path(out_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "jobmatch-results.json"
    md_path = output_dir / "jobmatch-report.md"
    json_path.write_text(
        json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(render_markdown_report(results), encoding="utf-8")
    return json_path, md_path


def render_markdown_report(results: list[JobMatchResult]) -> str:
    lines = [
        "# JobMatch Hub Report",
        "",
        "| Priority | Score | Company | Role | Location | Matched | Missing |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            "| {priority} | {score} | {company} | {title} | {location} | {matched} | {missing} |".format(
                priority=result.priority,
                score=result.score,
                company=result.company,
                title=result.title,
                location=result.location,
                matched=", ".join(result.matched_skills) or "-",
                missing=", ".join(result.missing_skills) or "-",
            )
        )

    for result in results:
        lines.extend(
            [
                "",
                f"## {result.company} - {result.title}",
                "",
                f"- Score: **{result.score}**",
                f"- Priority: **{result.priority}**",
                f"- Matched skills: {', '.join(result.matched_skills) or '-'}",
                f"- Missing skills: {', '.join(result.missing_skills) or '-'}",
                f"- Domain matches: {', '.join(result.domain_matches) or '-'}",
                "",
                "### Custom Pitch",
                "",
                result.pitch,
                "",
                "### Resume Optimization",
            ]
        )
        lines.extend(f"- {item}" for item in result.resume_advice)
    lines.append("")
    return "\n".join(lines)
