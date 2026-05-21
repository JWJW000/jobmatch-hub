from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


SKILL_KEYWORDS: tuple[str, ...] = (
    "Java",
    "Spring Boot",
    "Redis",
    "PostgreSQL",
    "Docker",
    "Nginx",
    "LLM",
    "RAG",
    "Vue",
    "React",
    "MySQL",
    "Kafka",
    "RabbitMQ",
    "Kubernetes",
    "Prometheus",
    "CI/CD",
    "Python",
    "FastAPI",
    "Flask",
    "TypeScript",
    "Go",
    "Elasticsearch",
    "AWS",
    "GCP",
    "Azure",
    "Terraform",
)

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Spring Boot": ("springboot", "spring boot", "spring"),
    "PostgreSQL": ("postgresql", "postgres"),
    "CI/CD": ("ci/cd", "cicd", "github actions", "gitlab ci", "jenkins"),
    "LLM": ("llm", "large language model", "大模型"),
    "RAG": ("rag", "retrieval augmented generation", "检索增强"),
    "Kubernetes": ("kubernetes", "k8s"),
    "RabbitMQ": ("rabbitmq", "rabbit mq"),
}

EXPERIENCE_KEYWORDS = (
    "senior",
    "lead",
    "principal",
    "architect",
    "years",
    "年经验",
    "高并发",
    "distributed",
    "microservice",
    "微服务",
    "scalable",
    "production",
)

DOMAIN_KEYWORDS = (
    "fintech",
    "金融",
    "ecommerce",
    "电商",
    "saas",
    "ai",
    "agent",
    "search",
    "推荐",
    "platform",
    "平台",
    "observability",
    "可观测",
)

BONUS_KEYWORDS = (
    "open source",
    "开源",
    "mentoring",
    "带团队",
    "owner",
    "performance",
    "性能优化",
    "security",
    "安全",
    "cost",
    "成本",
)


@dataclass(frozen=True)
class JobPosting:
    id: str
    title: str
    company: str
    location: str
    description: str


@dataclass(frozen=True)
class JobMatchResult:
    job_id: str
    title: str
    company: str
    location: str
    score: int
    priority: str
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    experience_matches: list[str] = field(default_factory=list)
    domain_matches: list[str] = field(default_factory=list)
    bonus_matches: list[str] = field(default_factory=list)
    pitch: str = ""
    resume_advice: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_jobs(resume_text: str, jobs: list[JobPosting]) -> list[JobMatchResult]:
    if not resume_text.strip():
        raise ValueError("Resume text is empty.")
    if not jobs:
        raise ValueError("No jobs were provided.")

    resume_skills = extract_skills(resume_text)
    resume_experience = extract_terms(resume_text, EXPERIENCE_KEYWORDS)
    resume_domains = extract_terms(resume_text, DOMAIN_KEYWORDS)
    resume_bonus = extract_terms(resume_text, BONUS_KEYWORDS)

    results = []
    for job in jobs:
        jd_text = f"{job.title}\n{job.company}\n{job.location}\n{job.description}"
        jd_skills = extract_skills(jd_text)
        matched_skills = sorted(resume_skills & jd_skills)
        missing_skills = sorted(jd_skills - resume_skills)

        experience_matches = sorted(resume_experience & extract_terms(jd_text, EXPERIENCE_KEYWORDS))
        domain_matches = sorted(resume_domains & extract_terms(jd_text, DOMAIN_KEYWORDS))
        bonus_matches = sorted(resume_bonus & extract_terms(jd_text, BONUS_KEYWORDS))

        skill_score = coverage_score(len(matched_skills), len(jd_skills), weight=62)
        experience_score = coverage_score(len(experience_matches), max(1, len(extract_terms(jd_text, EXPERIENCE_KEYWORDS))), weight=14)
        domain_score = coverage_score(len(domain_matches), max(1, len(extract_terms(jd_text, DOMAIN_KEYWORDS))), weight=12)
        bonus_score = min(12, len(bonus_matches) * 4 + len(set(matched_skills) & {"LLM", "RAG", "Kubernetes", "Prometheus"}) * 2)
        score = min(100, round(skill_score + experience_score + domain_score + bonus_score))

        results.append(
            JobMatchResult(
                job_id=job.id,
                title=job.title,
                company=job.company,
                location=job.location,
                score=score,
                priority=priority_for_score(score),
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                experience_matches=experience_matches,
                domain_matches=domain_matches,
                bonus_matches=bonus_matches,
                pitch=build_pitch(job, matched_skills, domain_matches, missing_skills, score),
                resume_advice=build_resume_advice(job, matched_skills, missing_skills, domain_matches, bonus_matches),
            )
        )

    return sorted(results, key=lambda item: (-item.score, item.company.lower(), item.title.lower()))


def load_jobs(path: str | Path) -> list[JobPosting]:
    source = Path(path).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"Jobs file not found: {source}")
    if source.suffix.lower() == ".csv":
        return load_jobs_csv(source)
    if source.suffix.lower() == ".json":
        return load_jobs_json(source)
    raise ValueError("Jobs file must be CSV or JSON.")


def parse_jobs_text(text: str) -> list[JobPosting]:
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("[") or stripped.startswith("{"):
        return jobs_from_json(json.loads(stripped))

    blocks = [block.strip() for block in re.split(r"\n\s*---+\s*\n", stripped) if block.strip()]
    jobs = []
    for index, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        title = lines[0] if lines else f"Manual Job {index}"
        company = "Manual Import"
        location = "Remote"
        description = block
        for line in lines[:5]:
            lower = line.lower()
            if lower.startswith("company:"):
                company = line.split(":", 1)[1].strip() or company
            elif lower.startswith("location:"):
                location = line.split(":", 1)[1].strip() or location
            elif lower.startswith("title:"):
                title = line.split(":", 1)[1].strip() or title
        jobs.append(JobPosting(str(index), title, company, location, description))
    return jobs


def extract_skills(text: str) -> set[str]:
    normalized = normalize(text)
    skills = set()
    for skill in SKILL_KEYWORDS:
        aliases = SKILL_ALIASES.get(skill, (skill.lower(),))
        if any(contains_term(normalized, alias) for alias in aliases):
            skills.add(skill)
    return skills


def extract_terms(text: str, terms: tuple[str, ...]) -> set[str]:
    normalized = normalize(text)
    return {term for term in terms if contains_term(normalized, term.lower())}


def load_jobs_csv(source: Path) -> list[JobPosting]:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    jobs = []
    for index, row in enumerate(rows, start=1):
        jobs.append(
            JobPosting(
                id=(row.get("id") or str(index)).strip(),
                title=(row.get("title") or "Untitled role").strip(),
                company=(row.get("company") or "Unknown company").strip(),
                location=(row.get("location") or "Unknown").strip(),
                description=(row.get("description") or row.get("jd") or "").strip(),
            )
        )
    return jobs


def load_jobs_json(source: Path) -> list[JobPosting]:
    return jobs_from_json(json.loads(source.read_text(encoding="utf-8")))


def jobs_from_json(payload: Any) -> list[JobPosting]:
    rows = payload.get("jobs", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("JSON jobs must be a list or an object with a jobs list.")
    jobs = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        jobs.append(
            JobPosting(
                id=str(row.get("id") or index),
                title=str(row.get("title") or "Untitled role"),
                company=str(row.get("company") or "Unknown company"),
                location=str(row.get("location") or "Unknown"),
                description=str(row.get("description") or row.get("jd") or ""),
            )
        )
    return jobs


def coverage_score(matches: int, total: int, weight: int) -> float:
    if total <= 0:
        return 0.0
    return min(weight, (matches / total) * weight)


def priority_for_score(score: int) -> str:
    if score >= 82:
        return "P0 - 今天定制投递"
    if score >= 68:
        return "P1 - 补强后投递"
    if score >= 52:
        return "P2 - 作为备选机会"
    return "P3 - 暂缓"


def build_pitch(job: JobPosting, matched_skills: list[str], domain_matches: list[str], missing_skills: list[str], score: int) -> str:
    skill_phrase = "、".join(matched_skills[:5]) if matched_skills else "后端工程化和快速学习能力"
    domain_phrase = f"，并具备 {'、'.join(domain_matches[:3])} 相关经验" if domain_matches else ""
    gap_phrase = f"我也注意到岗位强调 {'、'.join(missing_skills[:3])}，目前正在用项目方式补齐。" if missing_skills else "岗位关键技能与我的经历高度重合。"
    return (
        f"你好，我对 {job.company} 的 {job.title} 很感兴趣。我的经历覆盖 {skill_phrase}{domain_phrase}，"
        f"与岗位要求的匹配度约为 {score} 分。{gap_phrase}希望有机会进一步沟通我如何在入职后快速交付。"
    )


def build_resume_advice(
    job: JobPosting,
    matched_skills: list[str],
    missing_skills: list[str],
    domain_matches: list[str],
    bonus_matches: list[str],
) -> list[str]:
    advice = []
    if matched_skills:
        advice.append(f"在简历摘要前两屏突出 {', '.join(matched_skills[:6])}，并绑定可量化项目结果。")
    if missing_skills:
        advice.append(f"补一个最小可展示项目覆盖 {', '.join(missing_skills[:4])}，避免只写“了解”。")
    if domain_matches:
        advice.append(f"将 {', '.join(domain_matches[:3])} 场景写成 STAR 案例，贴合 {job.company} 的业务语境。")
    if bonus_matches:
        advice.append(f"把 {', '.join(bonus_matches[:3])} 作为加分项放到项目结尾，强化 senior 信号。")
    if not advice:
        advice.append("先补充岗位相关项目、指标和协作上下文，再考虑投递。")
    return advice


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def contains_term(normalized_text: str, term: str) -> bool:
    escaped = re.escape(term.lower()).replace("\\ ", r"\s+")
    if re.search(rf"(?<![a-z0-9+/#.-]){escaped}(?![a-z0-9+/#.-])", normalized_text):
        return True
    return term.lower() in normalized_text if any(ord(char) > 127 for char in term) else False
