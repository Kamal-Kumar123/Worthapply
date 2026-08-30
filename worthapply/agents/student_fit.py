"""Student Fit Agent — compares student evidence against job requirements."""

from __future__ import annotations

import re

from worthapply.agents.base import BaseAgent
from worthapply.models.schemas import (
    JobProfile,
    SkillMatch,
    SkillMatchLevel,
    StudentFitResult,
)
from worthapply.providers.base import LLMProvider

_SYSTEM = """You are an expert career counselor who evaluates student-job fit.

PRIMARY evidence (drive the fit_score):
1. Skills (and transferable related skills)
2. Projects
3. Work / internship experience

SECONDARY only:
- Education — note it briefly, but do NOT heavily penalize fit_score for degree mismatch
  if skills/projects/experience are strong. Many strong candidates learn on the job.

Match strength:
- MATCHED (HIGH): clear, direct evidence for the same skill.
- PARTIALLY_MATCHED (MEDIUM): related/transferable skill (AWS↔Azure, ML↔ML pipelines).
- MISSING (LOW): little/no evidence.

Rules:
- Related skills must be PARTIALLY_MATCHED, not MISSING.
- Cite specific resume evidence for HIGH/MEDIUM skills.
- fit_score: weight skills + projects + experience ~90%; education ≤10%.
- Prefer the job's required/preferred skill lists.
- Be generous with transferable skills: AWS↔Azure↔GCP, TensorFlow↔PyTorch, etc.
- Do NOT invent missing skills that are not in Required/Preferred lists.
- Do NOT flag "Missing AWS" unless AWS / Amazon Web Services is explicitly required.
  "Amazon Bedrock Guardrails" as an example is NOT an AWS experience requirement.
- For software / AI / engineering roles: Information Technology, Computer Science,
  CSE, Software Engineering, and similar tech degrees are ALIGNED — do NOT list
  "education in a different field" as a concern. Skills gaps matter; field of study
  for these roles is effectively the same family.
- concerns[] should only include real, grounded gaps (e.g. years of experience,
  hard skill missing from the JD lists). Avoid duplicating the same point twice.
- Years of experience are critical: if the JD clearly requires a minimum of 2+ years
  (e.g. 2-3, 3-5, 7+) and the resume is early-career / ~1 year of internships, say so
  in experience_match and concerns. Entry-level / 0–1 year / fresher roles are fine.
"""

_PROMPT = """Compare this student's profile against the job requirements.

## Student Profile
{student_text}

## Job Requirements
Title: {job_title}
Company: {company}
Required Skills: {required_skills}
Preferred Skills: {preferred_skills}
Experience Required: {experience_req}
Education Required: {education_req}
Responsibilities:
{responsibilities}

Return JSON with fit_score, required_skills and preferred_skills as arrays of objects:
{{"skill": "...", "match_level": "MATCHED|PARTIALLY_MATCHED|MISSING", "evidence": "..."}}
Use ONLY skills from the job lists above when possible.
Transferable skills count as PARTIALLY_MATCHED (e.g. resume AWS + JD Azure;
resume ML + JD ML pipelines; resume PyTorch + JD TensorFlow).
For concerns: only real gaps from the JD. Never invent AWS or "different education field"
for IT/CS students applying to software/AI engineering roles."""


# Concept families — transferable skills within a family = at least MEDIUM match.
_CONCEPTS: dict[str, set[str]] = {
    "python": {"python", "django", "flask", "fastapi", "pytest"},
    "java_jvm": {"java", "kotlin", "spring", "jvm"},
    "javascript": {"javascript", "typescript", "node", "nodejs", "react", "nextjs", "vue", "angular"},
    "ml": {
        "machine learning",
        "ml",
        "mlops",
        "sklearn",
        "scikit",
        "scikit-learn",
        "xgboost",
        "lightgbm",
        "model",
        "pipeline",
        "feature engineering",
    },
    "dl": {
        "deep learning",
        "neural",
        "cnn",
        "rnn",
        "transformer",
        "tensorflow",
        "pytorch",
        "keras",
        "torch",
    },
    "genai": {
        "genai",
        "generative ai",
        "llm",
        "llms",
        "gpt",
        "langchain",
        "agentic",
        "ai agent",
        "rag",
        "prompt",
    },
    "cv": {"computer vision", "opencv", "image", "vision", "yolo"},
    # All major clouds together — AWS experience helps an Azure JD (MEDIUM), etc.
    "cloud": {
        "cloud",
        "azure",
        "microsoft azure",
        "azure ml",
        "databricks",
        "fabric",
        "ai foundry",
        "aws",
        "amazon web services",
        "s3",
        "ec2",
        "lambda",
        "sagemaker",
        "gcp",
        "google cloud",
        "vertex",
        "ibm cloud",
        "oracle cloud",
    },
    "data": {
        "sql",
        "pandas",
        "spark",
        "etl",
        "warehouse",
        "postgres",
        "postgresql",
        "mysql",
        "mongodb",
        "nosql",
        "redis",
        "kafka",
    },
    "devops": {
        "docker",
        "kubernetes",
        "k8s",
        "ci/cd",
        "jenkins",
        "github actions",
        "terraform",
        "ansible",
    },
    "backend": {"api", "rest", "restful", "fastapi", "flask", "django", "express", "graphql"},
    "stats": {"statistics", "probability", "linear algebra", "math"},
}

# Nearby families also count as MEDIUM (transferable experience).
_RELATED_FAMILIES: dict[str, set[str]] = {
    "ml": {"dl", "genai", "cv", "stats"},
    "dl": {"ml", "genai", "cv"},
    "genai": {"ml", "dl"},
    "cv": {"ml", "dl"},
    "python": {"backend"},
    "backend": {"python", "javascript"},
    "javascript": {"backend"},
    "data": {"ml"},
    "devops": {"cloud"},
    "cloud": {"devops"},
}


def _family_for_token(token: str) -> str | None:
    t = token.lower().strip()
    for family, members in _CONCEPTS.items():
        if t in members:
            return family
        for m in members:
            if len(t) >= 3 and (t in m or m in t):
                return family
    return None


class StudentFitAgent(BaseAgent):
    name = "student_fit"

    def __init__(self, provider: LLMProvider) -> None:
        super().__init__(provider)

    async def run(
        self, student_text: str, job: JobProfile, job_text: str = ""
    ) -> StudentFitResult | None:
        prompt = _PROMPT.format(
            student_text=student_text[:4500],
            job_title=job.title,
            company=job.company,
            required_skills=", ".join(job.required_skills) or "Not specified",
            preferred_skills=", ".join(job.preferred_skills) or "Not specified",
            experience_req=job.experience_requirement or "Not specified",
            education_req=", ".join(job.education_requirements) or "Not specified",
            responsibilities="\n".join(f"- {r}" for r in job.responsibilities[:12])
            or "Not specified",
        )

        resp = await self.generate_structured(
            prompt, StudentFitResult, system=_SYSTEM, max_tokens=2048
        )

        if resp.ok and resp.structured:
            return self._ground(resp.structured, student_text, job, job_text)

        return self._ground(StudentFitResult(), student_text, job, job_text)

    def _ground(
        self,
        result: StudentFitResult,
        student_text: str,
        job: JobProfile,
        job_text: str = "",
    ) -> StudentFitResult:
        llm_by_skill = {
            self._norm(sm.skill): sm
            for sm in (result.required_skills + result.preferred_skills)
            if sm.skill
        }

        req_names = job.required_skills or [
            sm.skill for sm in result.required_skills if sm.skill
        ]
        pref_names = job.preferred_skills or [
            sm.skill for sm in result.preferred_skills if sm.skill
        ]

        req_atoms = self._expand_skill_list(req_names)
        pref_atoms = self._expand_skill_list(pref_names)
        pref_atoms = [
            s
            for s in pref_atoms
            if self._norm(s) not in {self._norm(x) for x in req_atoms}
        ]

        result.required_skills = [
            self._resolve_skill(name, llm_by_skill, student_text) for name in req_atoms
        ]
        result.preferred_skills = [
            self._resolve_skill(name, llm_by_skill, student_text) for name in pref_atoms
        ]

        matched = sum(
            1
            for sm in result.required_skills
            if sm.match_level == SkillMatchLevel.MATCHED
        )
        partial = sum(
            1
            for sm in result.required_skills
            if sm.match_level == SkillMatchLevel.PARTIALLY_MATCHED
        )
        total = max(len(result.required_skills), 1)
        grounded_score = round(100 * (matched + 0.55 * partial) / total, 1)

        all_low = result.required_skills and all(
            sm.match_level == SkillMatchLevel.MISSING for sm in result.required_skills
        )
        if all_low and result.fit_score >= 60:
            result.fit_score = grounded_score
        elif result.required_skills:
            result.fit_score = round(0.35 * result.fit_score + 0.65 * grounded_score, 1)

        result = apply_experience_gate(result, student_text, job, job_text)
        result = sanitize_fit_narratives(result, student_text, job, job_text)
        return result

    def _resolve_skill(
        self,
        skill: str,
        llm_by_skill: dict[str, SkillMatch],
        student_text: str,
    ) -> SkillMatch:
        key = self._norm(skill)
        llm = llm_by_skill.get(key)
        evidence, level = self._resume_evidence(skill, student_text)

        if llm and llm.match_level == SkillMatchLevel.MATCHED and llm.evidence.strip():
            return SkillMatch(
                skill=skill, match_level=SkillMatchLevel.MATCHED, evidence=llm.evidence
            )

        if evidence:
            # Prefer stronger of LLM partial vs grounded
            if llm and llm.match_level == SkillMatchLevel.MATCHED:
                level = SkillMatchLevel.MATCHED
            return SkillMatch(skill=skill, match_level=level, evidence=evidence)

        if llm and llm.match_level == SkillMatchLevel.PARTIALLY_MATCHED:
            return SkillMatch(
                skill=skill,
                match_level=SkillMatchLevel.PARTIALLY_MATCHED,
                evidence=llm.evidence or "Related experience noted by model.",
            )

        return SkillMatch(skill=skill, match_level=SkillMatchLevel.MISSING, evidence="")

    def _resume_evidence(
        self, skill: str, student_text: str
    ) -> tuple[str, SkillMatchLevel]:
        text = student_text.lower()
        skill_l = skill.lower()
        tokens = self._tokens(skill_l)

        # 1) Direct / high: whole skill phrase or strong token in resume
        for phrase in [skill_l, *tokens]:
            if len(phrase) < 2:
                continue
            if self._contains_term(text, phrase):
                return (
                    self._snippet(student_text, phrase),
                    SkillMatchLevel.MATCHED,
                )

        # 2) Medium: same concept family (ML ↔ ML pipelines, GenAI ↔ LLMs)
        skill_families = {
            f for t in tokens for f in [_family_for_token(t)] if f
        }
        # Also map multi-word skill into families via aliases inside skill string
        for fam, members in _CONCEPTS.items():
            if any(m in skill_l for m in members if len(m) >= 2):
                skill_families.add(fam)

        for fam in skill_families:
            for member in sorted(_CONCEPTS[fam], key=len, reverse=True):
                if self._contains_term(text, member):
                    return (
                        self._snippet(student_text, member)
                        + f" (related to JD skill “{skill}”)",
                        SkillMatchLevel.PARTIALLY_MATCHED,
                    )

        # 2b) Nearby families — e.g. ML experience for GenAI JD, DevOps for Cloud JD
        related = set()
        for fam in skill_families:
            related |= _RELATED_FAMILIES.get(fam, set())
        for fam in related:
            for member in sorted(_CONCEPTS.get(fam, set()), key=len, reverse=True):
                if self._contains_term(text, member):
                    return (
                        self._snippet(student_text, member)
                        + f" (transferable toward “{skill}”)",
                        SkillMatchLevel.PARTIALLY_MATCHED,
                    )

        # 3) Token overlap medium: e.g. "ml pipelines" vs resume "ml"
        for t in tokens:
            if len(t) >= 2 and self._contains_term(text, t):
                return (
                    self._snippet(student_text, t)
                    + f" (partial overlap with “{skill}”)",
                    SkillMatchLevel.PARTIALLY_MATCHED,
                )

        return "", SkillMatchLevel.MISSING

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        term = term.lower().strip()
        if not term:
            return False
        # Word-boundary-ish for short tokens like "ml", "ai"
        if len(term) <= 3:
            return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
        return term in text

    @staticmethod
    def _snippet(student_text: str, term: str) -> str:
        text_l = student_text.lower()
        idx = text_l.find(term.lower())
        if idx < 0:
            # regex short token
            m = re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text_l)
            idx = m.start() if m else 0
        start = max(0, idx - 40)
        end = min(len(student_text), idx + len(term) + 60)
        snippet = " ".join(student_text[start:end].split())
        return f"Found in resume: …{snippet}…"

    def _expand_skill_list(self, skills: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in skills:
            for p in self._split_skill_phrase(raw):
                n = self._norm(p)
                if n and n not in seen:
                    seen.add(n)
                    out.append(p.strip())
        return out[:20]

    @staticmethod
    def _split_skill_phrase(raw: str) -> list[str]:
        raw = raw.strip()
        if not raw:
            return []
        inside = re.findall(r"\(([^)]+)\)", raw)
        if inside:
            bits = re.split(r"[,/;]| and ", inside[0])
            return [b.strip() for b in bits if b.strip()]
        if "," in raw and len(raw) < 100:
            return [b.strip() for b in raw.split(",") if b.strip()]
        return [raw]

    @staticmethod
    def _tokens(skill: str) -> list[str]:
        stop = {"and", "or", "with", "using", "the", "a", "of", "in", "to", "for"}
        parts = re.split(r"[\s,/|&+\-]+", skill.lower())
        return [p for p in parts if p and p not in stop]

    @staticmethod
    def _norm(skill: str) -> str:
        return re.sub(r"\s+", " ", skill.strip().lower())


# ── Experience years gate ──────────────────────────────────────────────

_MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def parse_required_min_years(*texts: str) -> float | None:
    """Return minimum years required by the JD, or None if unspecified."""
    blob = " ".join(t for t in texts if t).lower()
    if not blob.strip():
        return None

    # Explicit early-career / open
    if re.search(
        r"\b(fresher|freshers|entry[- ]level|campus hire|new grad|new graduate|"
        r"no prior experience|0\s*[-–to/]+\s*1\s*(?:years?|yrs?)|"
        r"0\s*\+?\s*(?:years?|yrs?))\b",
        blob,
    ):
        return 0.0

    candidates: list[float] = []

    for m in re.finditer(
        r"(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)\b", blob
    ):
        candidates.append(float(m.group(1)))

    for m in re.finditer(
        r"(\d+(?:\.\d+)?)\s*[-–to/]+\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b",
        blob,
    ):
        candidates.append(float(m.group(1)))

    for m in re.finditer(
        r"(?:at least|minimum|min\.?|not less than|no less than)\s*"
        r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b",
        blob,
    ):
        candidates.append(float(m.group(1)))

    for m in re.finditer(
        r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp\.?)\b",
        blob,
    ):
        candidates.append(float(m.group(1)))

    # "Experience: 7+" without "years" nearby (common on boards)
    for m in re.finditer(
        r"(?:experience|exp\.?)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*\+",
        blob,
    ):
        candidates.append(float(m.group(1)))

    if not candidates:
        return None
    return min(candidates)


def _experience_section(student_text: str) -> str:
    text = student_text or ""
    # Prefer Experience / Internship / Work section if present
    m = re.search(
        r"(?is)(?:^|\n)\s*(experience|work experience|internship|internships|"
        r"professional experience|employment)\s*\n(.*?)(?=\n\s*[A-Z][A-Za-z /]{2,40}\s*\n|$)",
        text,
    )
    if m:
        return m.group(0)
    return text


def _month_num(token: str) -> int:
    t = token.lower().strip()
    for k, v in _MONTH_MAP.items():
        if t.startswith(k[:3]):
            return v
    return 1


def _months_from_date_ranges(text: str) -> float:
    """Sum approximate months from ranges like 'Jan 2024 – Jun 2024' / '2023-2024'."""
    from datetime import datetime, timezone

    total = 0.0
    now = datetime.now(timezone.utc)
    for m in re.finditer(
        r"(?i)\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\s+(\d{4})\s*[-–to]+\s*"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?|present|current|now)\s*(\d{4})?",
        text,
    ):
        sy = int(m.group(2))
        start_m = _month_num(m.group(1))
        em = m.group(3).lower()
        ey = m.group(4)
        if em in ("present", "current", "now") or not ey:
            end_y, end_m = now.year, now.month
        else:
            end_y, end_m = int(ey), _month_num(em)
        months = (end_y - sy) * 12 + (end_m - start_m) + 1
        if 0 < months <= 60:
            total += months

    for m in re.finditer(r"\b(20\d{2})\s*[-–to]+\s*(20\d{2}|present|current)\b", text, re.I):
        y1 = int(m.group(1))
        y2s = m.group(2).lower()
        y2 = now.year if y2s in ("present", "current") else int(y2s)
        years = y2 - y1
        if 0 < years <= 8:
            total += years * 12

    return total


def estimate_student_years(student_text: str) -> float:
    """Estimate total relevant experience (years) from resume text."""
    section = _experience_section(student_text)
    text = section.lower()

    explicit: list[float] = []
    for m in re.finditer(
        r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp\.?|internship)",
        text,
    ):
        explicit.append(float(m.group(1)))
    for m in re.finditer(
        r"(?:total|overall)\s+(?:experience|exp\.?)\s*[:\-]?\s*(\d+(?:\.\d+)?)",
        text,
    ):
        explicit.append(float(m.group(1)))

    months = 0.0
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*\+?\s*months?", text):
        months += float(m.group(1))
    months += _months_from_date_ranges(section)

    # Count distinct internship/role stints as ~4 months each if no dates
    stints = len(
        re.findall(r"\b(intern(?:ship)?|trainee|apprentice)\b", text)
    )
    if months < 1 and stints:
        months = stints * 4.0

    years_from_months = months / 12.0 if months else 0.0
    years = max(explicit + [years_from_months] if (explicit or years_from_months) else [0.0])

    if years <= 0:
        full = (student_text or "").lower()
        if re.search(r"\bfresher\b|\bno experience\b|\bseeking (first|entry)", full):
            return 0.0
        if re.search(r"\bintern(?:ship)?\b|\btrainee\b", full):
            # User baseline: all internships ~1 year combined when vague
            return 1.0
        return 0.5  # early-career default when unclear

    return round(min(years, 40.0), 2)


def apply_experience_gate(
    result: StudentFitResult,
    student_text: str,
    job: JobProfile,
    job_text: str = "",
) -> StudentFitResult:
    """Hard-penalize fit when JD min years clearly exceed resume experience."""
    job_min = parse_required_min_years(
        job.experience_requirement or "",
        job.title or "",
        " ".join(job.responsibilities or []),
        job_text or "",
    )
    student_years = estimate_student_years(student_text)

    if job_min is None:
        result.experience_match = (
            f"Resume experience ≈ {student_years:.1f} year(s). "
            "JD did not state a clear minimum years requirement."
        )
        return result

    if job_min <= 1.0:
        result.experience_match = (
            f"Resume ≈ {student_years:.1f} year(s) vs JD early-career / "
            f"~{job_min:.0f}+ year bar — OK to apply on experience."
        )
        return result

    # Soft OK if student meets or is within 0.25 yr of minimum
    if student_years + 0.25 >= job_min:
        result.experience_match = (
            f"Resume ≈ {student_years:.1f} year(s) meets JD minimum "
            f"of {job_min:.0f}+ years."
        )
        return result

    gap = job_min - student_years
    # Cap fit score hard — low value in applying when underqualified on years
    if gap >= 4:
        cap = 18.0
    elif gap >= 3:
        cap = 22.0
    elif gap >= 2:
        cap = 30.0
    else:
        # e.g. JD 2–3 yrs, resume ~1 yr
        cap = 38.0

    before = result.fit_score
    result.fit_score = round(min(before, cap), 1)
    result.experience_match = (
        f"Experience gap: JD requires about {job_min:.0f}+ years; resume shows "
        f"≈ {student_years:.1f} year(s) (internships/roles combined). "
        f"Fit score reduced ({before:.0f} → {result.fit_score:.0f}) — "
        "low chance of shortlist; prioritize roles closer to your tenure."
    )
    note = (
        f"Years of experience below JD minimum "
        f"(need ~{job_min:.0f}+, have ≈{student_years:.1f})"
    )
    concerns = list(result.concerns or [])
    if not any("experience" in c.lower() and "year" in c.lower() for c in concerns):
        concerns.insert(0, note)
    result.concerns = concerns
    return result


# ── Narrative / gap sanitizers (also used by decision synthesizer) ─────

_TECH_EDU_MARKERS = (
    "information technology",
    "computer science",
    "computer engineering",
    "software engineering",
    "information systems",
    "computer applications",
    "artificial intelligence",
    "data science",
    "electronics",
    "informatics",
    "b.tech",
    "btech",
    "m.tech",
    "mtech",
    "b.e.",
    "m.e.",
    "bca",
    "mca",
    "cse",
    "it engineering",
    "bachelor of technology",
    "master of technology",
)

_SOFTWARE_ROLE_MARKERS = (
    "engineer",
    "developer",
    "software",
    "programmer",
    "sde",
    "ai engineer",
    "ml engineer",
    "machine learning",
    "data scientist",
    "data engineer",
    "devops",
    "full stack",
    "fullstack",
    "backend",
    "frontend",
    "full-stack",
    "analyst",
    "architect",
)


def _job_blob(job: JobProfile, job_text: str = "") -> str:
    parts = [
        job_text or "",
        job.title,
        job.experience_requirement,
        " ".join(job.required_skills or []),
        " ".join(job.preferred_skills or []),
        " ".join(job.responsibilities or []),
        " ".join(job.education_requirements or []),
    ]
    return " ".join(parts).lower()


def aws_hard_required(job: JobProfile, job_text: str = "") -> bool:
    """True only when the JD clearly asks for AWS / Amazon Web Services."""
    text = _job_blob(job, job_text)
    if not text.strip():
        return False
    has_aws_token = bool(re.search(r"\baws\b|amazon web services", text))
    bedrock_only = (
        "amazon bedrock" in text or "bedrock guardrail" in text
    ) and not has_aws_token
    if bedrock_only:
        return False
    if not has_aws_token:
        # Required list may still name AWS explicitly
        for s in (job.required_skills or []) + (job.preferred_skills or []):
            if re.search(r"\baws\b|amazon web services", (s or "").lower()):
                # Prefer skills list only if JD text unavailable/short
                if len((job_text or "").strip()) < 80:
                    return True
        return False
    soft = bool(
        re.search(
            r"(such as|e\.g\.|for example|including|or through|platforms? such as)"
            r".{0,80}(amazon bedrock|\baws\b)",
            text,
            re.I,
        )
    )
    hard = bool(
        re.search(
            r"(experience (with|in) aws|aws experience|proficien\w* (in |with )?aws|"
            r"required.{0,40}\baws\b|must (have|know).{0,40}\baws\b)",
            text,
            re.I,
        )
    )
    if hard:
        return True
    if soft:
        return False
    # Explicit in required skills list
    for s in job.required_skills or []:
        if re.fullmatch(r"aws|amazon web services", (s or "").strip().lower()):
            return True
    return False


def student_has_tech_education(student_text: str) -> bool:
    blob = (student_text or "").lower()
    if any(m in blob for m in _TECH_EDU_MARKERS):
        return True
    # Standalone IT degree lines: "B.Tech in IT", "IT,"
    return bool(
        re.search(
            r"\b(b\.?\s*tech|bachelor|degree|b\.?e\.?)\b.{0,40}\b(it|i\.t\.)\b",
            blob,
        )
        or re.search(r"\binformation\s+tech", blob)
    )


def is_software_tech_role(title: str) -> bool:
    t = (title or "").lower()
    return any(m in t for m in _SOFTWARE_ROLE_MARKERS)


def _is_false_aws_gap(text: str) -> bool:
    t = (text or "").lower()
    return bool(
        re.search(r"\baws\b|amazon web services|amazon bedrock", t)
        and re.search(r"missing|lack|no |without|gap|need|verify|experience", t)
    )


def _is_edu_field_gap(text: str) -> bool:
    t = (text or "").lower()
    markers = (
        "different field",
        "unrelated field",
        "wrong field",
        "education mismatch",
        "degree mismatch",
        "field of study",
        "educational background",
        "education in a different",
        "degree in a different",
        "not aligned with education",
        "education does not",
    )
    if any(m in t for m in markers):
        return True
    return "education" in t and ("different" in t or "unrelated" in t or "mismatch" in t)


def should_drop_gap_text(
    text: str,
    *,
    student_text: str,
    job: JobProfile,
    job_text: str = "",
) -> bool:
    if not (text or "").strip():
        return True
    if not aws_hard_required(job, job_text) and _is_false_aws_gap(text):
        return True
    if (
        is_software_tech_role(job.title)
        and student_has_tech_education(student_text)
        and _is_edu_field_gap(text)
    ):
        return True
    return False


def sanitize_gap_list(
    items: list[str],
    *,
    student_text: str,
    job: JobProfile,
    job_text: str = "",
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items or []:
        text = (raw or "").strip()
        if not text:
            continue
        if should_drop_gap_text(
            text, student_text=student_text, job=job, job_text=job_text
        ):
            continue
        key = re.sub(r"\s+", " ", text.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def sanitize_fit_narratives(
    result: StudentFitResult,
    student_text: str,
    job: JobProfile,
    job_text: str = "",
) -> StudentFitResult:
    result.concerns = sanitize_gap_list(
        result.concerns, student_text=student_text, job=job, job_text=job_text
    )
    # Soften education_match wording when tech→software
    if (
        is_software_tech_role(job.title)
        and student_has_tech_education(student_text)
        and _is_edu_field_gap(result.education_match)
    ):
        result.education_match = (
            "Tech/IT background — aligned for software and AI engineering roles "
            "(skills matter more than exact degree title)."
        )
    elif (
        is_software_tech_role(job.title)
        and student_has_tech_education(student_text)
        and not (result.education_match or "").strip()
    ):
        result.education_match = (
            "Tech/IT background — suitable for this software/AI role."
        )
    return result