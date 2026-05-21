from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jobmatch_hub import analyze_jobs, load_jobs, render_markdown_report
from jobmatch_hub.report import write_outputs


ROOT = Path(__file__).resolve().parents[1]


def test_core_matching() -> None:
    resume = (ROOT / "examples" / "resume.md").read_text(encoding="utf-8")
    jobs = load_jobs(ROOT / "examples" / "jobs.csv")
    results = analyze_jobs(resume, jobs)
    report = render_markdown_report(results)

    assert len(results) == 3
    assert results[0].score >= 70
    assert "Java" in results[0].matched_skills
    all_missing = {skill for result in results for skill in result.missing_skills}
    assert {"Kubernetes", "React", "TypeScript"} & all_missing
    assert results[0].priority.startswith(("P0", "P1"))
    assert "Custom Pitch" in report

    with tempfile.TemporaryDirectory() as tmp:
        json_path, md_path = write_outputs(results, tmp)
        assert json.loads(json_path.read_text(encoding="utf-8"))[0]["score"] == results[0].score
        assert "# JobMatch Hub Report" in md_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    test_core_matching()
    print("smoke test passed")
