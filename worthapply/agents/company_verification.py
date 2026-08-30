"""Company Verification Agent — multi-signal legitimacy check."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from worthapply.agents.base import BaseAgent
from worthapply.models.schemas import CompanyVerification, VerificationStatus
from worthapply.providers.base import LLMProvider
from worthapply.tools.web_search import SearchResult, web_search
from worthapply.tools.webpage_fetcher import fetch_webpage

_JOB_BOARD_HOSTS = {
    "simplyhired.com",
    "simplyhired.co.in",
    "indeed.com",
    "indeed.co.in",
    "linkedin.com",
    "naukri.com",
    "glassdoor.com",
    "glassdoor.co.in",
    "monster.com",
    "monsterindia.com",
    "lever.co",
    "greenhouse.io",
    "boards.greenhouse.io",
    "jobs.lever.co",
    "wellfound.com",
    "angel.co",
    "hirist.tech",
    "instahyre.com",
    "cutshort.io",
    "foundit.in",
    "timesjobs.com",
    "shine.com",
    "internshala.com",
    "getmereferred.com",
    "referralcandy.com",
}

_PLACEHOLDER_COMPANIES = {
    "xyz technologies",
    "xyz corp",
    "xyz company",
    "acme",
    "acme corp",
    "example company",
    "company name",
    "your company",
    "unknown company",
    "tech company",
}

_SYSTEM = """You are a rigorous company verification analyst.

You receive MULTI-SOURCE evidence packs (several searches + fetched pages).
Cross-check them against each other before deciding.

Verification logic:
1. Direct official/job URL (if not an aggregator) = strongest evidence.
2. Known job boards (SimplyHired, Indeed, Naukri, LinkedIn…) are NORMAL listing channels.
3. Confirm company identity via: official website, LinkedIn company page, consistent
   naming across multiple independent results, about/careers pages.
4. Match signals: company name tokens appear on candidate official domains; job title
   appears on careers page or board listing; no contradictory entities with same name.
5. Status:
   - VERIFIED: strong multi-source agreement (official site + consistent identity)
   - PARTIALLY_VERIFIED: company looks real but some gaps (e.g. board-only listing)
   - UNVERIFIED: company identity not established
   - CONFLICTING: sources disagree
   - INSUFFICIENT_EVIDENCE: not enough data gathered
Never call a company a scam. Cite concrete URLs/snippets in evidence[]."""

_PROMPT = """Perform a careful multi-signal verification.

Claimed company: {company}
Job title: {job_title}
Source URL: {source_url}
Source type: {source_type}
Name looks like placeholder: {is_placeholder}

## Evidence pack (multiple queries + pages)
{evidence_pack}

## Heuristic match notes (automatic)
{heuristic_notes}

Cross-check all of the above. Decide verification_status, website_found,
careers_page_found, job_listing_found, confidence (0-1), website_url,
careers_page_url, job_listing_url, evidence[], unresolved_questions[],
and a precise summary.

Rules for flags:
- website_found / website_url: company's own site or LinkedIn company page (not a job board).
- careers_page_found / careers_page_url: a careers/jobs page on that company surface.
- job_listing_found / job_listing_url: THIS ROLE appears on the company careers page.
  A SimplyHired/Indeed/Naukri listing alone must NOT set job_listing_found=true.
Write evidence[] as short human sentences with URLs — never raw counters like name_hits=.
Prefer PARTIALLY_VERIFIED over UNVERIFIED when several independent hits agree
on the company even if careers listing is incomplete."""


def _host(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def is_job_board_url(url: str) -> bool:
    host = _host(url)
    if not host:
        return False
    return any(host == b or host.endswith("." + b) for b in _JOB_BOARD_HOSTS)


def _tokens(name: str) -> list[str]:
    stop = {"the", "and", "of", "pvt", "ltd", "limited", "inc", "llc", "private", "technologies", "tech", "solutions"}
    parts = re.split(r"[^a-z0-9]+", name.lower())
    return [p for p in parts if len(p) > 2 and p not in stop]


class CompanyVerificationAgent(BaseAgent):
    name = "company_verification"

    def __init__(self, provider: LLMProvider) -> None:
        super().__init__(provider)

    async def run(
        self,
        company: str,
        job_title: str,
        source_url: str = "",
        job_text: str = "",
    ) -> CompanyVerification:
        # Recover real company from posting text if LLM invented a placeholder
        company = self._resolve_company_name(company, job_text, source_url)
        on_board = is_job_board_url(source_url)
        is_ph = company.strip().lower() in _PLACEHOLDER_COMPANIES or not company.strip()

        source_type = (
            f"Known job board ({_host(source_url)})"
            if on_board
            else (
                "Direct / official URL"
                if source_url
                else "No URL"
            )
        )

        evidence_sections: list[str] = []
        source_urls: list[str] = []
        heuristic: list[str] = []

        website_found = False
        careers_found = False
        listing_found = False  # only True when role found on company careers page
        board_listing_ok = False
        website_url = ""
        careers_page_url = ""
        job_listing_url = ""
        name_hits = 0
        title_hits = 0

        # --- Signal 1: applicant URL ---
        if source_url:
            source_urls.append(source_url)
            page = await fetch_webpage(source_url)
            if page.ok and page.content.strip():
                evidence_sections.append(
                    f"### Source page ({source_url})\nTitle: {page.title}\n{page.content[:3500]}"
                )
                if not on_board:
                    # Direct URL: treat as listing surface; only mark careers/website
                    # if the path/title looks like it (don't stamp the same URL on all 3).
                    listing_found = True
                    job_listing_url = job_listing_url or source_url
                    looks_careers = bool(
                        re.search(
                            r"career|jobs|hiring|work-with|join-us|/job",
                            source_url + " " + page.title,
                            re.I,
                        )
                    )
                    if looks_careers:
                        careers_found = True
                        careers_page_url = careers_page_url or source_url
                    # Homepage-like path → website
                    path = urlparse(source_url).path.strip("/")
                    if not path or path.lower() in {"home", "index.html", "about", "about-us"}:
                        website_found = True
                        website_url = website_url or source_url
                    heuristic.append("Direct non-board URL fetched successfully.")
                else:
                    board_listing_ok = True
                    heuristic.append(
                        f"Job-board listing page fetched ({_host(source_url)}) — "
                        "normal channel, not the same as a company careers page."
                    )
                name_hits += self._count_name_hits(company, page.content + " " + page.title)
                title_hits += self._count_title_hits(job_title, page.content + " " + page.title)

        if is_ph:
            heuristic.append(
                "Claimed company name looks like a placeholder (e.g. XYZ). "
                "Do not treat it as a real entity unless evidence clearly supports it."
            )

        # --- Signals 2–N: multiple targeted searches ---
        queries = self._build_queries(company, job_title, on_board)
        all_results: list[SearchResult] = []
        for q in queries:
            resp = await web_search(q, num_results=5)
            block = [f"### Search: {q}  (provider={resp.provider or 'n/a'})"]
            if not resp.ok:
                block.append(f"Error: {resp.error}")
            elif not resp.results:
                block.append("No results.")
            else:
                for r in resp.results:
                    all_results.append(r)
                    block.append(f"- {r.title}\n  {r.url}\n  {r.snippet}")
                    blob = f"{r.title} {r.snippet} {r.url}"
                    name_hits += self._count_name_hits(company, blob)
                    title_hits += self._count_title_hits(job_title, blob)
            evidence_sections.append("\n".join(block))

        # --- Fetch top non-board candidate pages for deeper match ---
        fetched_official = 0
        for r in all_results:
            if fetched_official >= 3:
                break
            if is_job_board_url(r.url):
                continue
            host = _host(r.url)
            if any(s in host for s in ("facebook.com", "twitter.com", "youtube.com", "reddit.com")):
                continue
            if company and not self._host_or_text_matches_company(company, host, r.title + r.snippet):
                # still allow LinkedIn company pages / clear name in title
                if "linkedin.com/company" not in r.url.lower() and self._count_name_hits(company, r.title) == 0:
                    continue

            page = await fetch_webpage(r.url)
            if not page.ok or not page.content.strip():
                continue

            fetched_official += 1
            source_urls.append(r.url)
            is_careers = bool(re.search(r"career|jobs|hiring|work-with|join-us", r.url + page.title, re.I))
            label = "Careers/jobs page" if is_careers else "Candidate official/about page"
            evidence_sections.append(
                f"### {label}: {r.url}\nTitle: {page.title}\n{page.content[:2800]}"
            )
            website_found = True
            if not website_url:
                website_url = r.url
            page_title_hits = self._count_title_hits(job_title, page.content + " " + page.title)
            name_hits += self._count_name_hits(company, page.content + " " + page.title)
            title_hits += page_title_hits
            if is_careers:
                careers_found = True
                careers_page_url = careers_page_url or r.url
                if page_title_hits > 0 or (job_title and job_title.lower() in page.content.lower()):
                    listing_found = True
                    job_listing_url = job_listing_url or r.url

        heuristic.append(
            f"Gathered signals — company mentions: {name_hits}, "
            f"title matches: {title_hits}, website={website_found}, "
            f"careers_page={careers_found}, role_on_company_site={listing_found}, "
            f"board_listing_ok={board_listing_ok}."
        )

        evidence_pack = "\n\n".join(evidence_sections) or "No evidence collected."
        # Keep prompt size manageable for local models
        if len(evidence_pack) > 12000:
            evidence_pack = evidence_pack[:12000] + "\n...(truncated)"

        prompt = _PROMPT.format(
            company=company or "Unknown",
            job_title=job_title or "Unknown",
            source_url=source_url or "Not provided",
            source_type=source_type,
            is_placeholder=is_ph,
            evidence_pack=evidence_pack,
            heuristic_notes="\n".join(f"- {h}" for h in heuristic),
        )

        resp = await self.generate_structured(
            prompt, CompanyVerification, system=_SYSTEM, max_tokens=2048
        )

        if resp.ok and resp.structured:
            result: CompanyVerification = resp.structured
        else:
            result = CompanyVerification(
                summary="LLM synthesis failed; using heuristic verification only."
            )

        result.company_name = company
        result.source_urls = list(dict.fromkeys(source_urls + list(result.source_urls)))
        # Prefer gathered URLs; keep any LLM-provided ones as fallback
        result.website_url = website_url or result.website_url
        result.careers_page_url = careers_page_url or result.careers_page_url
        result.job_listing_url = job_listing_url or result.job_listing_url
        result = self._apply_heuristics(
            result,
            on_board=on_board,
            is_placeholder=is_ph,
            website_found=website_found,
            careers_found=careers_found,
            listing_found=listing_found,
            board_listing_ok=board_listing_ok,
            source_url=source_url,
            name_hits=name_hits,
            title_hits=title_hits,
        )
        return result

    def _apply_heuristics(
        self,
        result: CompanyVerification,
        *,
        on_board: bool,
        is_placeholder: bool,
        website_found: bool,
        careers_found: bool,
        listing_found: bool,
        board_listing_ok: bool,
        source_url: str,
        name_hits: int,
        title_hits: int,
    ) -> CompanyVerification:
        # Merge boolean flags upward from gathering
        result.website_found = result.website_found or website_found
        result.careers_page_found = result.careers_page_found or careers_found
        # Never treat a job-board page as "listing on company site"
        result.job_listing_found = listing_found or (
            result.job_listing_found and bool(result.job_listing_url)
            and not is_job_board_url(result.job_listing_url)
        )
        if result.job_listing_found and not result.careers_page_found:
            # Role on company site implies a careers/jobs surface existed
            result.careers_page_found = True
            if result.job_listing_url and not result.careers_page_url:
                result.careers_page_url = result.job_listing_url

        evidence = [e for e in result.evidence if not self._is_raw_debug_evidence(e)]

        if on_board:
            host = _host(source_url) or "job board"
            note = (
                f"Posted on a known job board ({host}) — common recruiting channel. "
                "This is not the same as finding the role on the company's own careers page."
            )
            if source_url:
                note += f" Source: {source_url}"
            if note not in evidence:
                evidence.append(note)

        if is_placeholder:
            result.verification_status = VerificationStatus.UNVERIFIED
            result.confidence = min(result.confidence, 0.2)
            result.unresolved_questions = list(result.unresolved_questions) + [
                "Company name appears to be a placeholder; re-extract from the job posting."
            ]
            result.evidence = evidence
            return result

        # Promote status from multi-hit agreement
        if result.website_found and name_hits >= 3:
            if result.careers_page_found or (on_board and board_listing_ok):
                if result.verification_status in (
                    VerificationStatus.UNVERIFIED,
                    VerificationStatus.INSUFFICIENT_EVIDENCE,
                ):
                    result.verification_status = (
                        VerificationStatus.VERIFIED
                        if result.careers_page_found and name_hits >= 4
                        else VerificationStatus.PARTIALLY_VERIFIED
                    )
                result.confidence = max(result.confidence, 0.65 if result.careers_page_found else 0.5)
            elif result.verification_status in (
                VerificationStatus.UNVERIFIED,
                VerificationStatus.INSUFFICIENT_EVIDENCE,
            ):
                result.verification_status = VerificationStatus.PARTIALLY_VERIFIED
                result.confidence = max(result.confidence, 0.45)
        elif on_board and board_listing_ok and name_hits >= 2:
            if result.verification_status in (
                VerificationStatus.UNVERIFIED,
                VerificationStatus.INSUFFICIENT_EVIDENCE,
            ):
                result.verification_status = VerificationStatus.PARTIALLY_VERIFIED
                result.confidence = max(result.confidence, 0.4)

        cross = self._human_cross_check(name_hits, title_hits, result)
        if cross and cross not in evidence:
            evidence.append(cross)
        result.evidence = evidence
        return result

    @staticmethod
    def _is_raw_debug_evidence(text: str) -> bool:
        t = (text or "").lower()
        return "name_hits=" in t or "title_hits=" in t or t.startswith("cross-check:")

    @staticmethod
    def _human_cross_check(
        name_hits: int, title_hits: int, result: CompanyVerification
    ) -> str:
        bits: list[str] = []
        if name_hits > 0:
            bits.append(
                f"company name showed up in about {name_hits} search/page mentions"
            )
        if title_hits > 0:
            bits.append(f"job title matched in about {title_hits} places")
        if result.website_url:
            bits.append(f"website checked: {result.website_url}")
        if result.careers_page_url:
            bits.append(f"careers page: {result.careers_page_url}")
        elif result.website_found and not result.careers_page_found:
            bits.append("no dedicated careers/jobs page URL was confirmed")
        if result.job_listing_url:
            bits.append(f"role also seen on company site: {result.job_listing_url}")
        if not bits:
            return ""
        return "Cross-check: " + "; ".join(bits) + "."

    def _build_queries(self, company: str, job_title: str, on_board: bool) -> list[str]:
        if not company.strip():
            return [f'"{job_title}" official careers'] if job_title else []
        qs = [
            f'"{company}" official website',
            f'"{company}" company about',
            f'"{company}" LinkedIn company',
            f'"{company}" careers OR jobs OR hiring',
        ]
        if job_title:
            qs.append(f'"{company}" "{job_title}"')
            if on_board:
                qs.append(f'"{job_title}" "{company}" site:linkedin.com OR careers')
        # Dedupe while preserving order
        seen = set()
        out = []
        for q in qs:
            if q not in seen:
                seen.add(q)
                out.append(q)
        return out[:6]

    def _resolve_company_name(
        self, company: str, job_text: str, source_url: str
    ) -> str:
        raw = (company or "").strip()
        if raw and raw.lower() not in _PLACEHOLDER_COMPANIES:
            return raw
        text = job_text or ""
        # Common patterns
        for pat in (
            r"(?im)^\s*Company\s*[:\-]\s*(.+)$",
            r"(?im)^\s*Employer\s*[:\-]\s*(.+)$",
            r"(?i)at\s+([A-Z][A-Za-z0-9&.,'\- ]{2,60})\s+(?:is hiring|hiring)",
        ):
            m = re.search(pat, text)
            if m:
                cand = m.group(1).strip().split("\n")[0].strip()
                if cand.lower() not in _PLACEHOLDER_COMPANIES:
                    return cand[:120]
        # From page title lines
        for line in text.splitlines()[:15]:
            if "–" in line or " - " in line:
                # e.g. Role - Company | Location
                parts = re.split(r"\s+[–|-]\s+", line)
                if len(parts) >= 2:
                    cand = parts[1].split("|")[0].strip()
                    if 2 < len(cand) < 80 and cand.lower() not in _PLACEHOLDER_COMPANIES:
                        return cand
        return raw

    def _count_name_hits(self, company: str, blob: str) -> int:
        if not company:
            return 0
        blob_l = blob.lower()
        hits = 0
        full = company.lower().strip()
        if len(full) > 3 and full in blob_l:
            hits += 2
        for t in _tokens(company):
            if re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", blob_l):
                hits += 1
        return hits

    def _count_title_hits(self, title: str, blob: str) -> int:
        if not title:
            return 0
        blob_l = blob.lower()
        hits = 0
        full = title.lower().strip()
        if len(full) > 5 and full in blob_l:
            return 2
        for t in _tokens(title):
            if len(t) > 3 and re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", blob_l):
                hits += 1
        return hits

    def _host_or_text_matches_company(self, company: str, host: str, text: str) -> bool:
        toks = _tokens(company)
        host_l = host.lower()
        text_l = text.lower()
        if any(t in host_l for t in toks if len(t) > 3):
            return True
        return self._count_name_hits(company, text_l) > 0
