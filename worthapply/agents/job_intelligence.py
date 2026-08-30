"""Job Intelligence Agent — extracts a structured job profile from raw text."""

from __future__ import annotations

import re

from worthapply.agents.base import BaseAgent
from worthapply.models.schemas import JobProfile
from worthapply.providers.base import LLMProvider

_SYSTEM = """You are a job posting analyst. Extract structured fields ONLY from the text.

STRICT RULES:
- Copy company name and job title EXACTLY as written in the posting. Do not rename.
- If a field is missing, leave it empty ("" or []). NEVER invent placeholders
  like "XYZ Technologies", "Acme", "Software Engineer" unless those exact words appear.
- posting_date: ONLY if an explicit date appears in the text. Otherwise leave null/empty.
  Do NOT invent dates. Relative labels like "5d"/"5 days ago" may be copied as-is.
- Do not guess skills that are not mentioned.
- Do NOT invent "AWS" as a required skill just because the text mentions
  "Amazon Bedrock Guardrails" (or similar) as one example platform. Only list AWS
  if the posting clearly asks for AWS / Amazon Web Services experience.
- Prefer short verbatim phrases from the posting for responsibilities."""

_PROMPT = """Extract structured fields from this job posting.

Rules reminder: never invent company, title, posting_date, or cloud skills.

Job posting:
{job_text}

Source URL: {source_url}"""

_PLACEHOLDER_COMPANIES = {
    "xyz technologies",
    "xyz corp",
    "xyz company",
    "acme",
    "acme corp",
    "acme corporation",
    "example company",
    "company name",
    "your company",
    "unknown company",
    "tech company",
}

_PLACEHOLDER_TITLES = {
    "software engineer",
    "software developer",
    "job title",
    "position",
    "role",
}


class JobIntelligenceAgent(BaseAgent):
    name = "job_intelligence"

    def __init__(self, provider: LLMProvider) -> None:
        super().__init__(provider)

    async def run(self, job_text: str, source_url: str = "") -> JobProfile | None:
        """Extract a structured JobProfile from raw job description text."""
        if not (job_text or "").strip():
            return JobProfile(source_url=source_url)

        # Keep enough text for small local models but prefer the start (title/company)
        clipped = job_text.strip()
        if len(clipped) > 6000:
            clipped = clipped[:6000] + "\n...(truncated)"

        prompt = _PROMPT.format(job_text=clipped, source_url=source_url)
        resp = await self.generate_structured(
            prompt, JobProfile, system=_SYSTEM, max_tokens=2048
        )

        if resp.ok and resp.structured:
            profile: JobProfile = resp.structured
            profile = self._sanitize(profile, job_text, source_url)
            return profile
        return None

    def _sanitize(
        self, profile: JobProfile, job_text: str, source_url: str
    ) -> JobProfile:
        text_l = job_text.lower()

        # Always prefer the URL the user provided; never keep an LLM rewrite/truncate.
        if source_url:
            profile.source_url = source_url

        # Drop invented company/title that do not appear in source text
        if profile.company:
            company_l = profile.company.strip().lower()
            if company_l in _PLACEHOLDER_COMPANIES or (
                len(company_l) > 2 and company_l not in text_l
            ):
                # Allow close matches / partial presence
                tokens = [t for t in re.split(r"\W+", company_l) if len(t) > 2]
                if company_l in _PLACEHOLDER_COMPANIES or not any(
                    t in text_l for t in tokens
                ):
                    profile.company = self._guess_company(job_text) or ""

        if profile.title:
            title_l = profile.title.strip().lower()
            if title_l in _PLACEHOLDER_TITLES and title_l not in text_l:
                profile.title = self._guess_title(job_text) or ""
            elif title_l not in text_l:
                # keep if substantial overlap with posting
                words = [w for w in re.split(r"\W+", title_l) if len(w) > 3]
                if words and sum(1 for w in words if w in text_l) < max(1, len(words) // 2):
                    guessed = self._guess_title(job_text)
                    if guessed:
                        profile.title = guessed

        # Never keep a posting_date that isn't grounded in the text
        if profile.posting_date:
            pd = str(profile.posting_date).strip()
            if pd and pd.lower() not in text_l and not self._date_grounded(pd, text_l):
                profile.posting_date = None

        profile.required_skills = self._sanitize_skills(
            profile.required_skills, job_text, required=True
        )
        profile.preferred_skills = self._sanitize_skills(
            profile.preferred_skills, job_text, required=False
        )
        # Don't invent education requirements when posting lists none
        if profile.education_requirements and not self._mentions_education(text_l):
            profile.education_requirements = []

        return profile

    def _sanitize_skills(
        self, skills: list[str], job_text: str, *, required: bool
    ) -> list[str]:
        out: list[str] = []
        for s in skills or []:
            name = (s or "").strip()
            if not name:
                continue
            if self._is_invented_aws(name, job_text):
                continue
            out.append(name)
        return out

    @staticmethod
    def _is_invented_aws(skill: str, job_text: str) -> bool:
        """Drop bare AWS if JD only mentions Amazon Bedrock as an example."""
        sk = skill.lower().strip()
        if sk not in {"aws", "amazon web services", "amazon aws"} and not re.fullmatch(
            r"aws(\s*/\s*azure)?", sk
        ):
            return False
        text = (job_text or "").lower()
        has_aws_token = bool(re.search(r"\baws\b|amazon web services", text))
        has_bedrock_only = (
            "amazon bedrock" in text or "bedrock guardrail" in text
        ) and not has_aws_token
        if has_bedrock_only:
            return True
        if not has_aws_token:
            return True
        # Soft example phrasing without a hard requirement
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
        return soft and not hard

    @staticmethod
    def _mentions_education(text_l: str) -> bool:
        return bool(
            re.search(
                r"\b(b\.?tech|m\.?tech|b\.?e\.?\b|m\.?e\.?\b|bachelor|master|"
                r"degree|graduation|graduate|education|qualification)\b",
                text_l,
            )
        )

    @staticmethod
    def _date_grounded(date_str: str, text_l: str) -> bool:
        # Accept if year+month fragments appear, or relative age labels
        if re.search(r"\b\d+\s*d(ays?)?\b", date_str.lower()) and re.search(
            r"\b\d+\s*d\b", text_l
        ):
            return True
        parts = re.findall(r"\d{4}|\d{1,2}", date_str)
        return bool(parts) and all(p.lower() in text_l for p in parts if len(p) >= 4)

    @staticmethod
    def _guess_title(job_text: str) -> str:
        for line in job_text.splitlines():
            line = line.strip()
            if not line or len(line) > 120:
                continue
            low = line.lower()
            if any(
                k in low
                for k in (
                    "engineer",
                    "developer",
                    "scientist",
                    "analyst",
                    "intern",
                    "manager",
                )
            ):
                return line[:120]
        return ""

    @staticmethod
    def _guess_company(job_text: str) -> str:
        # Common patterns: "Company: X" / "at X" in first lines
        for line in job_text.splitlines()[:40]:
            m = re.match(
                r"(?i)^\s*(company|employer|organization)\s*[:\-]\s*(.+)$", line.strip()
            )
            if m:
                return m.group(2).strip()[:120]
        return ""
