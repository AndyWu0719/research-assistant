from __future__ import annotations

from urllib.parse import urlparse


DISCOVERY_SOURCE_GROUPS: dict[str, list[str]] = {
    "ai_computer_science": ["arXiv", "OpenReview", "ACL Anthology", "CVF Open Access", "PMLR"],
    "general_academic": ["Semantic Scholar", "Crossref", "Google Scholar"],
    "social_science_and_education": ["SSRN", "PubMed", "ERIC"],
    "humanities": ["JSTOR", "Project MUSE", "PhilPapers"],
}

PROTECTED_SITES: dict[str, dict[str, object]] = {
    "jstor": {
        "label": "JSTOR",
        "domains": ["jstor.org"],
        "category": "humanities",
        "login_modes": ["direct", "institution-sso"],
    },
    "project_muse": {
        "label": "Project MUSE",
        "domains": ["muse.jhu.edu"],
        "category": "humanities",
        "login_modes": ["direct", "institution-sso"],
    },
    "proquest": {
        "label": "ProQuest",
        "domains": ["proquest.com"],
        "category": "protected_full_text",
        "login_modes": ["direct", "institution-sso"],
    },
    "ebscohost": {
        "label": "EBSCOhost",
        "domains": ["ebsco.com", "ebscohost.com"],
        "category": "protected_full_text",
        "login_modes": ["direct", "institution-sso"],
    },
    "sciencedirect": {
        "label": "ScienceDirect",
        "domains": ["sciencedirect.com"],
        "category": "protected_full_text",
        "login_modes": ["direct", "institution-sso"],
    },
    "springerlink": {
        "label": "SpringerLink",
        "domains": ["link.springer.com"],
        "category": "protected_full_text",
        "login_modes": ["direct", "institution-sso"],
    },
    "wiley": {
        "label": "Wiley Online Library",
        "domains": ["wiley.com", "onlinelibrary.wiley.com"],
        "category": "protected_full_text",
        "login_modes": ["direct", "institution-sso"],
    },
    "taylor_and_francis": {
        "label": "Taylor & Francis",
        "domains": ["tandfonline.com"],
        "category": "protected_full_text",
        "login_modes": ["direct", "institution-sso"],
    },
    "sage": {
        "label": "Sage Journals",
        "domains": ["sagepub.com"],
        "category": "protected_full_text",
        "login_modes": ["direct", "institution-sso"],
    },
}


def discovery_source_options() -> list[str]:
    ordered: list[str] = []
    for values in DISCOVERY_SOURCE_GROUPS.values():
        for item in values:
            if item not in ordered:
                ordered.append(item)
    return ordered


def protected_site_keys() -> list[str]:
    return list(PROTECTED_SITES.keys())


def detect_protected_site(url: str) -> str | None:
    netloc = urlparse(url).netloc.lower()
    if not netloc:
        return None
    for key, payload in PROTECTED_SITES.items():
        if any(str(domain).lower() in netloc for domain in payload["domains"]):
            return key
    return None


def compact_time_range_to_payload(value: int, unit: str) -> dict[str, object]:
    normalized_unit = str(unit or "day").strip().lower()
    normalized_value = max(1, int(value))
    if normalized_unit == "year":
        return {"mode": "rolling", "days": normalized_value * 365, "label": f"最近 {normalized_value} 年"}
    return {"mode": "rolling", "days": normalized_value, "label": f"最近 {normalized_value} 天"}


def payload_to_compact_time_range(payload: dict[str, object]) -> tuple[int, str]:
    days = max(1, int(payload.get("days") or 7))
    if days >= 365 and days % 365 == 0:
        return days // 365, "year"
    return days, "day"
