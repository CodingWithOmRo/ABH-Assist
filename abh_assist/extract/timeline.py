import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from abh_assist.llm.client import run_llm
from abh_assist.llm.json_guard import validate_and_fix_json
from abh_assist.llm.prompts import EXTRACT_TIMELINE_EVENTS_PROMPT


DEFAULT_SORT_DATE = "9999-12-31"
DATE_CONTEXT_CHARS = 420

RELEVANCE_KEYWORDS = [
    "aufenthalt",
    "aufenthaltserlaubnis",
    "niederlassungserlaubnis",
    "visum",
    "duldung",
    "fiktionsbescheinigung",
    "ausweisung",
    "abschiebung",
    "ausreise",
    "grenzuebertritt",
    "einreise",
    "straftat",
    "urteil",
    "freiheitsstrafe",
    "haft",
    "bewaehrung",
    "geldstrafe",
    "staatsanwaltschaft",
    "gericht",
    "polizei",
    "identitaet",
    "pass",
    "passport",
    "mitwirkung",
    "termin",
    "anhoerung",
    "frist",
    "bescheid",
    "verfuegung",
    "familie",
    "ehe",
    "kind",
    "arbeit",
    "sozialleistung",
    "krankheit",
]


def chunk_text(text: str, max_chars: int = 5000, overlap: int = 500) -> List[str]:
    """Split long file text into overlapping chunks for the local LLM."""
    if not text:
        return [""]

    clean_text = text.strip()
    if len(clean_text) <= max_chars:
        return [clean_text]

    chunks = []
    start = 0
    while start < len(clean_text):
        end = min(start + max_chars, len(clean_text))
        if end < len(clean_text):
            newline = clean_text.rfind("\n", start + int(max_chars * 0.65), end)
            if newline > start:
                end = newline
        chunks.append(clean_text[start:end].strip())
        if end >= len(clean_text):
            break
        start = max(0, end - overlap)
    return [chunk for chunk in chunks if chunk]


def normalize_date(raw_date: Optional[str]) -> Tuple[Optional[str], str, str]:
    """
    Return (display_date, precision, sort_date).
    sort_date is ISO-like and intentionally approximate for month/year dates.
    """
    if raw_date is None:
        return None, "unknown", DEFAULT_SORT_DATE

    date_text = str(raw_date).strip()
    if not date_text or date_text.lower() in {"null", "none", "unbekannt"}:
        return None, "unknown", DEFAULT_SORT_DATE

    iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", date_text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        if _valid_date(year, month, day):
            return f"{day:02d}.{month:02d}.{year:04d}", "day", f"{year:04d}-{month:02d}-{day:02d}"

    day_match = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b", date_text)
    if day_match:
        day, month, year = map(int, day_match.groups())
        year = _expand_year(year)
        if _valid_date(year, month, day):
            return f"{day:02d}.{month:02d}.{year:04d}", "day", f"{year:04d}-{month:02d}-{day:02d}"

    month_match = re.search(r"\b(\d{1,2})[./](\d{4})\b", date_text)
    if month_match:
        month, year = map(int, month_match.groups())
        if 1 <= month <= 12 and 1800 <= year <= 2200:
            return f"{month:02d}.{year:04d}", "month", f"{year:04d}-{month:02d}-01"

    year_match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2}|22\d{2})\b", date_text)
    if year_match:
        year = int(year_match.group(1))
        return f"{year:04d}", "year", f"{year:04d}-01-01"

    return date_text, "unknown", DEFAULT_SORT_DATE


def build_case_timeline(
    documents: Iterable[Dict],
    goal: str,
    progress_callback=None,
) -> Dict:
    all_entries = []
    document_summaries = []
    docs = list(documents)

    for doc_index, doc in enumerate(docs):
        entries = extract_document_timeline_events(doc, goal)
        all_entries.extend(entries)
        document_summaries.append(
            {
                "filename": doc.get("filename"),
                "doc_type": doc.get("doc_type", "unknown"),
                "text_chars": len(doc.get("text") or ""),
                "events_found": len(entries),
            }
        )
        if progress_callback:
            progress_callback(doc_index + 1, len(docs))

    timeline_entries = sort_timeline_entries(all_entries)
    coverage_notes = build_coverage_notes(document_summaries, timeline_entries)

    return {
        "analysis_goal": goal,
        "timeline_entries": timeline_entries,
        "document_summaries": document_summaries,
        "coverage_notes": coverage_notes,
    }


def extract_document_timeline_events(doc: Dict, goal: str) -> List[Dict]:
    text = doc.get("text") or ""
    filename = doc.get("filename") or "Unbekanntes Dokument"
    doc_type = doc.get("doc_type") or "unknown"
    chunks = chunk_text(text)
    entries = []

    for index, chunk in enumerate(chunks, start=1):
        prompt = EXTRACT_TIMELINE_EVENTS_PROMPT.format(
            goal=goal,
            filename=filename,
            doc_type=doc_type,
            chunk_number=index,
            total_chunks=len(chunks),
            text_snippet=chunk,
        )
        response = run_llm(prompt, stop=["User:", "</s>"], max_tokens=2048)
        parsed = validate_and_fix_json(response) or {}
        llm_entries = parsed.get("entries", [])
        if isinstance(llm_entries, list):
            entries.extend(
                normalize_entry(
                    entry,
                    filename=filename,
                    doc_type=doc_type,
                    chunk_number=index,
                    extraction_method="llm",
                )
                for entry in llm_entries
                if isinstance(entry, dict)
            )

        entries.extend(
            candidate
            for candidate in extract_dated_sentence_candidates(chunk, filename, doc_type, index)
            if not is_duplicate_candidate(candidate, entries)
        )

    return [entry for entry in entries if entry.get("date") or entry.get("sort_date") != DEFAULT_SORT_DATE]


def normalize_entry(
    entry: Dict,
    filename: str,
    doc_type: str,
    chunk_number: int,
    extraction_method: str,
) -> Dict:
    display_date, precision, sort_date = normalize_date(entry.get("date"))
    if entry.get("date_precision") in {"day", "month", "year"}:
        precision = entry["date_precision"]

    return {
        "date": display_date,
        "date_precision": precision,
        "sort_date": sort_date,
        "date_basis": entry.get("date_basis") or "unknown",
        "event": _clean_text(entry.get("event")),
        "relevance": _clean_text(entry.get("relevance")),
        "category": entry.get("category") or "Sonstiges",
        "source_document": entry.get("source_document") or filename,
        "source_page_or_section": entry.get("source_page_or_section") or f"Auszug {chunk_number}",
        "evidence_snippet": _clean_text(entry.get("evidence_snippet")),
        "confidence": _safe_float(entry.get("confidence"), default=0.6),
        "doc_type": doc_type,
        "chunk_number": chunk_number,
        "extraction_method": extraction_method,
    }


def extract_dated_sentence_candidates(
    text: str,
    filename: str,
    doc_type: str,
    chunk_number: int,
) -> List[Dict]:
    candidates = []
    for match in _iter_date_matches(text):
        context = _extract_context(text, match.start(), match.end())
        if not context:
            continue

        date_display, precision, sort_date = normalize_date(match.group(0))
        if precision == "year" and not _has_relevance_keyword(context):
            continue

        candidates.append(
            {
                "date": date_display,
                "date_precision": precision,
                "sort_date": sort_date,
                "date_basis": "date_in_text",
                "event": context,
                "relevance": "Automatisch aufgenommen, weil im Dokument ein Datum mit moeglichem Aktenbezug gefunden wurde.",
                "category": infer_category(context),
                "source_document": filename,
                "source_page_or_section": infer_page_marker(text, match.start()) or f"Auszug {chunk_number}",
                "evidence_snippet": context[:500],
                "confidence": 0.35,
                "doc_type": doc_type,
                "chunk_number": chunk_number,
                "extraction_method": "date_regex",
            }
        )
    return candidates


def sort_timeline_entries(entries: Iterable[Dict]) -> List[Dict]:
    normalized_entries = []
    seen = set()

    for entry in entries:
        if not entry:
            continue
        if "sort_date" not in entry:
            display_date, precision, sort_date = normalize_date(entry.get("date"))
            entry["date"] = display_date
            entry["date_precision"] = precision
            entry["sort_date"] = sort_date

        key = _dedupe_key(entry)
        if key in seen:
            continue
        seen.add(key)
        normalized_entries.append(entry)

    return sorted(
        normalized_entries,
        key=lambda item: (
            item.get("sort_date") or DEFAULT_SORT_DATE,
            item.get("source_document") or "",
            item.get("event") or "",
        ),
    )


def build_coverage_notes(document_summaries: List[Dict], entries: List[Dict]) -> List[Dict]:
    notes = []
    empty_docs = [doc["filename"] for doc in document_summaries if not doc.get("text_chars")]
    no_event_docs = [
        doc["filename"]
        for doc in document_summaries
        if doc.get("text_chars") and not doc.get("events_found")
    ]
    low_confidence_count = len([entry for entry in entries if _safe_float(entry.get("confidence"), 0) < 0.5])

    if empty_docs:
        notes.append(
            {
                "severity": "HIGH",
                "message": "Aus einigen Dokumenten konnte kein Text extrahiert werden.",
                "documents": empty_docs,
            }
        )
    if no_event_docs:
        notes.append(
            {
                "severity": "MEDIUM",
                "message": "In einigen Dokumenten wurden keine datierten Eintraege gefunden.",
                "documents": no_event_docs,
            }
        )
    if low_confidence_count:
        notes.append(
            {
                "severity": "LOW",
                "message": f"{low_confidence_count} Eintraege stammen aus der vorsorglichen Datumssuche und sollten geprueft werden.",
                "documents": [],
            }
        )
    if not entries:
        notes.append(
            {
                "severity": "HIGH",
                "message": "Es wurden keine datierten zielrelevanten Eintraege gefunden.",
                "documents": [],
            }
        )
    return notes


def timeline_entries_to_rows(entries: Iterable[Dict]) -> List[Dict]:
    rows = []
    for entry in entries:
        rows.append(
            {
                "Datum": entry.get("date") or "Unbekannt",
                "Genauigkeit": entry.get("date_precision") or "unknown",
                "Kategorie": entry.get("category") or "Sonstiges",
                "Ereignis": entry.get("event") or "",
                "Dienlichkeit": entry.get("relevance") or "",
                "Dokument": entry.get("source_document") or "",
                "Fundstelle": entry.get("source_page_or_section") or "",
                "Beleg": entry.get("evidence_snippet") or "",
                "Konfidenz": f"{_safe_float(entry.get('confidence'), 0):.2f}",
            }
        )
    return rows


def _iter_date_matches(text: str):
    patterns = [
        r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b",
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        r"\b\d{1,2}[./](?:18|19|20|21|22)\d{2}\b",
        r"\b(?:18|19|20|21|22)\d{2}\b",
    ]
    seen_spans = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            span = match.span()
            if any(_spans_overlap(span, seen) for seen in seen_spans):
                continue
            seen_spans.append(span)
            yield match


def _spans_overlap(left: Tuple[int, int], right: Tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _extract_context(text: str, start: int, end: int) -> str:
    left = max(0, start - DATE_CONTEXT_CHARS // 2)
    right = min(len(text), end + DATE_CONTEXT_CHARS)
    snippet = text[left:right]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:700]


def infer_page_marker(text: str, pos: int) -> Optional[str]:
    prefix = text[:pos]
    matches = list(re.finditer(r"--- PAGE (\d+) ---", prefix))
    if not matches:
        return None
    return f"Seite {matches[-1].group(1)}"


def infer_category(text: str) -> str:
    lower = _normalize_ascii(text.lower())
    category_keywords = {
        "Aufenthalt": ["aufenthalt", "visum", "niederlassung", "titel"],
        "Duldung": ["duldung"],
        "Straftat": ["straftat", "polizei", "anklage", "ermittlung", "bankueberfall"],
        "Urteil": ["urteil", "verurteilt", "freiheitsstrafe", "geldstrafe"],
        "Haft": ["haft", "entlassung", "justizvollzugsanstalt", "jva"],
        "Ausreise": ["ausreise", "ausreisefrist", "ausreiseaufforderung"],
        "Abschiebung": ["abschiebung", "abschiebe"],
        "Identitaet": ["identitaet", "pass", "passport", "staatsangehoerigkeit"],
        "Mitwirkung": ["mitwirkung", "vorladung", "termin"],
        "Familie": ["ehe", "familie", "kind"],
        "Gesundheit": ["krank", "aerzt", "gesundheit"],
        "Arbeit": ["arbeit", "beschaeftigung", "erwerb"],
        "Sozialleistungen": ["sozialleistung", "jobcenter", "buergergeld"],
        "Frist": ["frist"],
        "Kommunikation": ["schreiben", "email", "telefon", "anhoerung"],
    }
    for category, keywords in category_keywords.items():
        if any(keyword in lower for keyword in keywords):
            return category
    return "Sonstiges"


def is_duplicate_candidate(candidate: Dict, existing_entries: List[Dict]) -> bool:
    candidate_date = candidate.get("sort_date")
    candidate_source = candidate.get("source_document")
    candidate_text = _normalize_for_compare(candidate.get("event") or candidate.get("evidence_snippet"))

    for entry in existing_entries:
        if entry.get("sort_date") != candidate_date:
            continue
        if entry.get("source_document") != candidate_source:
            continue
        existing_text = _normalize_for_compare(entry.get("event") or entry.get("evidence_snippet"))
        if candidate_text and existing_text and (candidate_text[:80] in existing_text or existing_text[:80] in candidate_text):
            return True
    return False


def _dedupe_key(entry: Dict) -> Tuple[str, str, str]:
    return (
        str(entry.get("sort_date") or DEFAULT_SORT_DATE),
        str(entry.get("source_document") or "").lower(),
        _normalize_for_compare(entry.get("event") or entry.get("evidence_snippet"))[:160],
    )


def _has_relevance_keyword(text: str) -> bool:
    lower = _normalize_ascii(text.lower())
    return any(keyword in lower for keyword in RELEVANCE_KEYWORDS)


def _normalize_ascii(value: str) -> str:
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def _normalize_for_compare(value: Optional[str]) -> str:
    value = _clean_text(value).lower()
    return re.sub(r"[^a-z0-9äöüß]+", " ", value).strip()


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _expand_year(year: int) -> int:
    if year < 100:
        return 2000 + year if year < 40 else 1900 + year
    return year


def _valid_date(year: int, month: int, day: int) -> bool:
    try:
        datetime(year, month, day)
        return 1800 <= year <= 2200
    except ValueError:
        return False
