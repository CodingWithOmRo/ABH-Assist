import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from abh_assist.llm.client import run_llm
from abh_assist.llm.json_guard import validate_and_fix_json
from abh_assist.llm.prompts import EXTRACT_TIMELINE_EVENTS_PROMPT


DEFAULT_SORT_DATE = "9999-12-31"
DATE_CONTEXT_CHARS = 420
CHUNK_MAX_CHARS = 1800
CHUNK_OVERLAP = 200
LLM_MAX_TOKENS = 512

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

CASE_SPECIFIC_KEYWORDS = [
    "antragsteller",
    "antrag",
    "bescheid",
    "anerkennung",
    "abschiebungsandrohung",
    "fluechtlingseigenschaft",
    "zuerkannt",
    "abgelehnt",
    "aufgehoben",
    "wohnhaft",
    "vertreten durch",
    "folgende entscheidung",
    "asylfolgeverfahren",
    "asylverfahren",
    "beantragt",
    "geb.",
]

LEGAL_CITATION_KEYWORDS = [
    "bverwg",
    "bverfg",
    "ovg",
    "vg ",
    "vgl.",
    "rechtsprechung",
    "bverwge",
    "bverfge",
    "beschluss vom",
    "urteil vom",
]

EVENT_SCOPE_LABELS = {
    "historical_origin": "Historischer Sachverhalt Herkunftsland",
    "germany_administrative": "Verwaltung Deutschland",
    "germany_judicial": "Straf-/Gerichtsverfahren Deutschland",
    "personal_context": "Persoenliche Lebensumstaende",
    "unclear": "Unklar",
}


def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Backward-compatible text chunk helper."""
    return [chunk["text"] for chunk in build_text_chunks(text, max_chars=max_chars, overlap=overlap)]


def build_text_chunks(
    text: str,
    max_chars: int = CHUNK_MAX_CHARS,
    overlap: int = CHUNK_OVERLAP,
) -> List[Dict]:
    """Split long file text into overlapping chunks with page metadata."""
    if not text or not text.strip():
        return [_build_chunk_record("", 0, 0, text or "")]

    source_text = text
    source_len = len(source_text)
    chunks = []
    start = 0

    while start < source_len:
        end = min(start + max_chars, source_len)
        if end < source_len:
            newline = source_text.rfind("\n", start + int(max_chars * 0.65), end)
            if newline > start:
                end = newline

        raw_chunk = source_text[start:end]
        stripped_chunk = raw_chunk.strip()
        if stripped_chunk:
            leading_trim = len(raw_chunk) - len(raw_chunk.lstrip())
            chunk_start = start + leading_trim
            chunk_end = chunk_start + len(stripped_chunk)
            chunks.append(_build_chunk_record(stripped_chunk, chunk_start, chunk_end, source_text))

        if end >= source_len:
            break
        start = max(0, end - overlap)

    return chunks or [_build_chunk_record(source_text.strip(), 0, len(source_text.strip()), source_text)]


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
        entries, doc_summary = extract_document_timeline_events(doc, goal)
        all_entries.extend(entries)
        document_summaries.append(doc_summary)
        if progress_callback:
            progress_callback(doc_index + 1, len(docs))

    timeline_entries = sort_timeline_entries(all_entries)
    timeline_summary = build_timeline_summary(timeline_entries, document_summaries)
    coverage_notes = build_coverage_notes(document_summaries, timeline_entries, timeline_summary)

    return {
        "analysis_goal": goal,
        "timeline_entries": timeline_entries,
        "document_summaries": document_summaries,
        "timeline_summary": timeline_summary,
        "coverage_notes": coverage_notes,
    }


def extract_document_timeline_events(doc: Dict, goal: str) -> Tuple[List[Dict], Dict]:
    text = doc.get("text") or ""
    filename = doc.get("filename") or "Unbekanntes Dokument"
    doc_type = doc.get("doc_type") or "unknown"
    chunks = build_text_chunks(text)
    entries = []
    llm_entry_count = 0
    llm_candidate_count = 0
    regex_entry_count = 0
    inferred_date_count = 0
    llm_failure_count = 0
    rejected_ungrounded_count = 0
    rejected_unsupported_date_count = 0
    rejected_missing_date_count = 0
    page_spans = []

    for index, chunk_meta in enumerate(chunks, start=1):
        if not (chunk_meta.get("text") or "").strip():
            continue
        page_span = chunk_meta.get("page_span")
        if page_span and page_span not in page_spans:
            page_spans.append(page_span)
        prompt = EXTRACT_TIMELINE_EVENTS_PROMPT.format(
            goal=goal,
            filename=filename,
            doc_type=doc_type,
            chunk_number=index,
            total_chunks=len(chunks),
            page_scope=page_span or "Nicht erkennbar",
            text_snippet=chunk_meta.get("text", ""),
        )
        try:
            response = run_llm(prompt, stop=["User:", "</s>"], max_tokens=LLM_MAX_TOKENS)
            parsed = validate_and_fix_json(response) or {}
        except Exception as exc:
            print(f"Timeline extraction warning in {filename} chunk {index}: {exc}")
            parsed = {}
        llm_entries = parsed.get("entries", []) if isinstance(parsed, dict) else []
        if isinstance(parsed, dict) and "entries" in parsed and isinstance(llm_entries, list):
            for entry in llm_entries:
                if not isinstance(entry, dict):
                    continue
                llm_candidate_count += 1
                normalized = normalize_entry(
                    entry,
                    filename=filename,
                    doc_type=doc_type,
                    chunk_number=index,
                    extraction_method="llm",
                    page_hint=page_span,
                )
                validated, rejection_reason = validate_llm_entry_against_chunk(normalized, chunk_meta)
                if not validated:
                    if rejection_reason == "ungrounded_evidence":
                        rejected_ungrounded_count += 1
                    elif rejection_reason == "unsupported_date":
                        rejected_unsupported_date_count += 1
                    elif rejection_reason == "missing_date":
                        rejected_missing_date_count += 1
                    continue
                if validated.get("date_basis", "").startswith("inferred_from_document_date"):
                    inferred_date_count += 1
                llm_entry_count += 1
                entries.append(validated)
        else:
            llm_failure_count += 1

        for candidate in extract_dated_sentence_candidates(chunk_meta, filename, doc_type, index):
            if is_duplicate_candidate(candidate, entries):
                continue
            regex_entry_count += 1
            entries.append(candidate)

    dated_entries = [entry for entry in entries if entry.get("date") or entry.get("sort_date") != DEFAULT_SORT_DATE]
    summary = {
        "filename": filename,
        "doc_type": doc_type,
        "text_chars": len(text),
        "chunk_count": len(chunks),
        "events_found": len(dated_entries),
        "llm_candidates": llm_candidate_count,
        "llm_entries": llm_entry_count,
        "regex_entries": regex_entry_count,
        "inferred_dates": inferred_date_count,
        "llm_failures": llm_failure_count,
        "rejected_ungrounded": rejected_ungrounded_count,
        "rejected_unsupported_date": rejected_unsupported_date_count,
        "rejected_missing_date": rejected_missing_date_count,
        "page_spans": page_spans,
    }
    return dated_entries, summary


def normalize_entry(
    entry: Dict,
    filename: str,
    doc_type: str,
    chunk_number: int,
    extraction_method: str,
    page_hint: Optional[str] = None,
) -> Dict:
    display_date, precision, sort_date = normalize_date(entry.get("date"))
    if entry.get("date_precision") in {"day", "month", "year"}:
        precision = entry["date_precision"]
    event_text = _clean_text(entry.get("event"))
    evidence_text = _clean_text(entry.get("evidence_snippet"))

    return {
        "date": display_date,
        "date_precision": precision,
        "sort_date": sort_date,
        "date_basis": entry.get("date_basis") or "unknown",
        "event": event_text,
        "relevance": _clean_text(entry.get("relevance")),
        "category": entry.get("category") or "Sonstiges",
        "event_scope": normalize_event_scope(
            entry.get("event_scope"),
            evidence_text=evidence_text,
            event_text=event_text,
            doc_type=doc_type,
        ),
        "source_document": entry.get("source_document") or filename,
        "source_page_or_section": entry.get("source_page_or_section") or page_hint or f"Auszug {chunk_number}",
        "evidence_snippet": evidence_text,
        "confidence": _safe_float(entry.get("confidence"), default=0.6),
        "doc_type": doc_type,
        "chunk_number": chunk_number,
        "extraction_method": extraction_method,
    }


def extract_dated_sentence_candidates(
    chunk_meta: Dict,
    filename: str,
    doc_type: str,
    chunk_number: int,
) -> List[Dict]:
    text = chunk_meta.get("text", "")
    candidates = []
    for match in _iter_date_matches(text):
        context = _extract_context(text, match.start(), match.end())
        if not context:
            continue

        date_display, precision, sort_date = normalize_date(match.group(0))
        if precision == "year" and not _has_relevance_keyword(context):
            continue
        if _looks_like_legal_citation_context(context) and not _has_case_specific_keyword(context):
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
                "event_scope": infer_event_scope(context, doc_type),
                "source_document": filename,
                "source_page_or_section": infer_page_marker_for_chunk(chunk_meta, match.start()) or f"Auszug {chunk_number}",
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


def build_timeline_summary(entries: List[Dict], document_summaries: List[Dict]) -> Dict:
    category_counts = {}
    event_scope_counts = {}
    method_counts = {}
    low_confidence_count = 0
    inferred_date_count = 0
    page_reference_count = 0

    for entry in entries:
        category = entry.get("category") or "Sonstiges"
        category_counts[category] = category_counts.get(category, 0) + 1

        event_scope = entry.get("event_scope") or "unclear"
        event_scope_counts[event_scope] = event_scope_counts.get(event_scope, 0) + 1

        method = entry.get("extraction_method") or "unknown"
        method_counts[method] = method_counts.get(method, 0) + 1

        if _safe_float(entry.get("confidence"), 0) < 0.5:
            low_confidence_count += 1
        if str(entry.get("date_basis") or "").startswith("inferred_from_document_date"):
            inferred_date_count += 1
        if _has_real_source_reference(entry.get("source_page_or_section")):
            page_reference_count += 1

    dated_entries = [entry for entry in entries if entry.get("sort_date") and entry.get("sort_date") != DEFAULT_SORT_DATE]
    documents_with_entries = len({entry.get("source_document") for entry in entries if entry.get("source_document")})
    documents_without_entries = len([doc for doc in document_summaries if not doc.get("events_found")])
    rejected_ungrounded = sum(doc.get("rejected_ungrounded", 0) for doc in document_summaries)
    rejected_unsupported_date = sum(doc.get("rejected_unsupported_date", 0) for doc in document_summaries)
    rejected_missing_date = sum(doc.get("rejected_missing_date", 0) for doc in document_summaries)

    start_entry = dated_entries[0] if dated_entries else {}
    end_entry = dated_entries[-1] if dated_entries else {}

    return {
        "entry_count": len(entries),
        "document_count": len(document_summaries),
        "documents_with_entries": documents_with_entries,
        "documents_without_entries": documents_without_entries,
        "low_confidence_count": low_confidence_count,
        "inferred_date_count": inferred_date_count,
        "entries_with_page_reference": page_reference_count,
        "entries_without_page_reference": max(0, len(entries) - page_reference_count),
        "rejected_ungrounded": rejected_ungrounded,
        "rejected_unsupported_date": rejected_unsupported_date,
        "rejected_missing_date": rejected_missing_date,
        "date_range": {
            "start": start_entry.get("date"),
            "start_sort_date": start_entry.get("sort_date"),
            "end": end_entry.get("date"),
            "end_sort_date": end_entry.get("sort_date"),
        },
        "category_counts": [
            {"category": category, "count": count}
            for category, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "event_scope_counts": [
            {"event_scope": EVENT_SCOPE_LABELS.get(scope, scope), "count": count}
            for scope, count in sorted(event_scope_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "method_counts": [
            {"method": method, "count": count}
            for method, count in sorted(method_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "document_hit_counts": [
            {
                "filename": doc.get("filename"),
                "events_found": doc.get("events_found", 0),
                "page_spans": doc.get("page_spans", []),
                "llm_candidates": doc.get("llm_candidates", 0),
                "llm_entries": doc.get("llm_entries", 0),
                "rejected_ungrounded": doc.get("rejected_ungrounded", 0),
                "rejected_unsupported_date": doc.get("rejected_unsupported_date", 0),
            }
            for doc in sorted(
                document_summaries,
                key=lambda item: (-item.get("events_found", 0), item.get("filename") or ""),
            )
        ],
    }


def build_coverage_notes(document_summaries: List[Dict], entries: List[Dict], timeline_summary: Dict) -> List[Dict]:
    notes = []
    empty_docs = [doc["filename"] for doc in document_summaries if not doc.get("text_chars")]
    no_event_docs = [
        doc["filename"]
        for doc in document_summaries
        if doc.get("text_chars") and not doc.get("events_found")
    ]
    llm_failure_docs = [doc["filename"] for doc in document_summaries if doc.get("llm_failures")]
    low_confidence_count = timeline_summary.get("low_confidence_count", 0)
    inferred_date_count = timeline_summary.get("inferred_date_count", 0)
    missing_reference_count = timeline_summary.get("entries_without_page_reference", 0)
    rejected_ungrounded = timeline_summary.get("rejected_ungrounded", 0)
    rejected_unsupported_date = timeline_summary.get("rejected_unsupported_date", 0)
    rejected_missing_date = timeline_summary.get("rejected_missing_date", 0)

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
    if llm_failure_docs:
        notes.append(
            {
                "severity": "MEDIUM",
                "message": "Einige Dokumentauszuege konnten vom LLM nicht sauber als JSON verarbeitet werden. Die Datumssuche lief dennoch weiter.",
                "documents": llm_failure_docs,
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
    if inferred_date_count:
        notes.append(
            {
                "severity": "LOW",
                "message": f"Bei {inferred_date_count} Eintraegen wurde das Datum aus einem eindeutig datierten Dokumentauszug abgeleitet.",
                "documents": [],
            }
        )
    if missing_reference_count:
        notes.append(
            {
                "severity": "LOW",
                "message": f"{missing_reference_count} Eintraege haben noch keine klare Seitenangabe und sollten gegen das Originaldokument geprueft werden.",
                "documents": [],
            }
        )
    if rejected_ungrounded:
        notes.append(
            {
                "severity": "MEDIUM",
                "message": f"{rejected_ungrounded} LLM-Eintraege wurden verworfen, weil die Fundstelle nicht im aktuellen Dokumentauszug nachweisbar war.",
                "documents": [],
            }
        )
    if rejected_unsupported_date:
        notes.append(
            {
                "severity": "MEDIUM",
                "message": f"{rejected_unsupported_date} LLM-Eintraege wurden verworfen, weil das angegebene Datum im aktuellen Dokumentauszug nicht nachweisbar war.",
                "documents": [],
            }
        )
    if rejected_missing_date:
        notes.append(
            {
                "severity": "LOW",
                "message": f"{rejected_missing_date} LLM-Eintraege wurden verworfen, weil kein belastbares Datum aus dem Auszug belegt werden konnte.",
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
                "Datumsbasis": entry.get("date_basis") or "unknown",
                "Kategorie": entry.get("category") or "Sonstiges",
                "Bereich": EVENT_SCOPE_LABELS.get(entry.get("event_scope") or "unclear", entry.get("event_scope") or "unclear"),
                "Ereignis": entry.get("event") or "",
                "Dienlichkeit": entry.get("relevance") or "",
                "Dokument": entry.get("source_document") or "",
                "Fundstelle": entry.get("source_page_or_section") or "",
                "Beleg": entry.get("evidence_snippet") or "",
                "Methode": entry.get("extraction_method") or "",
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
    matches = list(re.finditer(r"--- PAGE (\d+)(?: OCR)? ---", prefix))
    if not matches:
        return None
    return f"Seite {matches[-1].group(1)}"


def infer_page_marker_for_chunk(chunk_meta: Dict, pos: int) -> Optional[str]:
    base_start = chunk_meta.get("start", 0)
    source_text = chunk_meta.get("source_text", chunk_meta.get("text", ""))
    page_marker = infer_page_marker(source_text, base_start + pos)
    return page_marker or chunk_meta.get("page_span")


def infer_page_span(text: str, start: int, end: int) -> Optional[str]:
    page_matches = list(re.finditer(r"--- PAGE (\d+)(?: OCR)? ---", text))
    if not page_matches:
        return None

    pages = [int(match.group(1)) for match in page_matches if start <= match.start() <= end]
    current_page = None
    for match in page_matches:
        if match.start() > start:
            break
        current_page = int(match.group(1))
    if current_page is not None:
        pages.insert(0, current_page)

    unique_pages = sorted(set(pages))
    if not unique_pages:
        return None
    if len(unique_pages) == 1:
        return f"Seite {unique_pages[0]}"
    return f"Seite {unique_pages[0]}-{unique_pages[-1]}"


def infer_category(text: str) -> str:
    lower = _normalize_ascii(text.lower())
    category_keywords = {
        "Asylverfahren": ["asyl", "bamf", "fluechtling", "schutzstatus", "anerkennung", "ablehnung"],
        "Herkunft/Flucht": ["herkunft", "flucht", "verfolgt", "miliz", "heimat", "im irak", "in syrien", "in afghanistan"],
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


def infer_missing_date_from_chunk(entry: Dict, chunk_meta: Dict) -> Dict:
    if entry.get("date") or entry.get("sort_date") != DEFAULT_SORT_DATE:
        return entry

    unique_anchors = []
    seen = set()
    for anchor in chunk_meta.get("date_anchors", []):
        key = (anchor.get("sort_date"), anchor.get("precision"))
        if anchor.get("sort_date") == DEFAULT_SORT_DATE or key in seen:
            continue
        unique_anchors.append(anchor)
        seen.add(key)

    if len(unique_anchors) != 1:
        return entry

    anchor = unique_anchors[0]
    updated_entry = dict(entry)
    updated_entry["date"] = anchor.get("date")
    updated_entry["date_precision"] = anchor.get("precision", "unknown")
    updated_entry["sort_date"] = anchor.get("sort_date", DEFAULT_SORT_DATE)
    updated_entry["date_basis"] = f"inferred_from_document_date ({anchor.get('raw')})"
    current_reference = updated_entry.get("source_page_or_section")
    if not current_reference or _is_generic_chunk_reference(current_reference):
        updated_entry["source_page_or_section"] = (
            anchor.get("source_page_or_section")
            or chunk_meta.get("page_span")
            or current_reference
            or f"Auszug {updated_entry.get('chunk_number', '?')}"
        )
    updated_entry["confidence"] = min(_safe_float(updated_entry.get("confidence"), default=0.6), 0.55)
    if not updated_entry.get("evidence_snippet"):
        updated_entry["evidence_snippet"] = _clean_text(chunk_meta.get("text", "")[:250])
    return updated_entry


def validate_llm_entry_against_chunk(entry: Dict, chunk_meta: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    chunk_text = chunk_meta.get("text", "")
    grounded_evidence = ground_evidence_snippet(entry.get("evidence_snippet"), chunk_text)
    if not grounded_evidence:
        return None, "ungrounded_evidence"

    validated = dict(entry)
    validated["evidence_snippet"] = grounded_evidence

    evidence_anchor = resolve_date_anchor_from_evidence(validated, grounded_evidence, chunk_meta)
    if evidence_anchor:
        validated = apply_date_anchor(validated, evidence_anchor, chunk_meta)
    else:
        validated = infer_missing_date_from_chunk(validated, chunk_meta)
        matched_anchor = match_date_anchor_for_entry(validated, chunk_meta)
        if not matched_anchor:
            if validated.get("sort_date") == DEFAULT_SORT_DATE:
                return None, "missing_date"
            return None, "unsupported_date"
        validated = apply_date_anchor(validated, matched_anchor, chunk_meta)

    validated["category"] = validated.get("category") or infer_category(
        validated.get("evidence_snippet") or validated.get("event")
    )
    validated["event_scope"] = normalize_event_scope(
        validated.get("event_scope"),
        evidence_text=validated.get("evidence_snippet", ""),
        event_text=validated.get("event", ""),
        doc_type=validated.get("doc_type", ""),
    )
    return validated, None


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


def _has_case_specific_keyword(text: str) -> bool:
    lower = _normalize_ascii(text.lower())
    return any(keyword in lower for keyword in CASE_SPECIFIC_KEYWORDS)


def _looks_like_legal_citation_context(text: str) -> bool:
    lower = _normalize_ascii(text.lower())
    return any(keyword in lower for keyword in LEGAL_CITATION_KEYWORDS)


def normalize_event_scope(
    raw_scope: Optional[str],
    evidence_text: str,
    event_text: str,
    doc_type: str,
) -> str:
    normalized_scope = _normalize_ascii((raw_scope or "").strip().lower())
    scope_aliases = {
        "historical_origin": "historical_origin",
        "historischer_sachverhalt_herkunftsland": "historical_origin",
        "herkunftsland": "historical_origin",
        "origin_country_history": "historical_origin",
        "germany_administrative": "germany_administrative",
        "verwaltung_deutschland": "germany_administrative",
        "administrative_germany": "germany_administrative",
        "germany_judicial": "germany_judicial",
        "straf_gerichtsverfahren_deutschland": "germany_judicial",
        "judicial_germany": "germany_judicial",
        "personal_context": "personal_context",
        "persoenliche_lebensumstaende": "personal_context",
        "unclear": "unclear",
        "unklar": "unclear",
    }
    if normalized_scope in scope_aliases:
        return scope_aliases[normalized_scope]
    return infer_event_scope(f"{evidence_text} {event_text}".strip(), doc_type)


def infer_event_scope(text: str, doc_type: str = "") -> str:
    lower = _normalize_ascii(text.lower())
    if any(
        keyword in lower
        for keyword in [
            "bamf",
            "bundesamt",
            "auslaenderbehoerde",
            "aufenthalt",
            "duldung",
            "fiktionsbescheinigung",
            "bescheid",
            "anhorung",
            "anhaerung",
            "frist",
            "mitwirkung",
            "passbeschaffung",
            "abschiebung",
            "ausreiseaufforderung",
        ]
    ):
        return "germany_administrative"
    if any(
        keyword in lower
        for keyword in [
            "gericht",
            "urteil",
            "freiheitsstrafe",
            "geldstrafe",
            "polizei",
            "staatsanwaltschaft",
            "jva",
            "haft",
        ]
    ):
        return "germany_judicial"
    if any(
        keyword in lower
        for keyword in [
            "herkunft",
            "flucht",
            "verfolgt",
            "miliz",
            "heimat",
            "im irak",
            "in syrien",
            "in afghanistan",
            "im iran",
            "im herkunftsland",
        ]
    ):
        return "historical_origin"
    if any(
        keyword in lower
        for keyword in [
            "familie",
            "kind",
            "ehe",
            "krank",
            "gesundheit",
            "arbeit",
            "schule",
            "wohnung",
            "unterkunft",
        ]
    ):
        return "personal_context"
    if doc_type in {"passport", "application_form", "residence_permit_card"}:
        return "germany_administrative"
    return "unclear"


def _build_chunk_record(chunk_text: str, start: int, end: int, source_text: str) -> Dict:
    return {
        "text": chunk_text,
        "start": start,
        "end": end,
        "page_span": infer_page_span(source_text, start, end),
        "date_anchors": _collect_date_anchors(source_text, chunk_text, start),
        "source_text": source_text,
    }


def _collect_date_anchors(source_text: str, chunk_text: str, chunk_start: int) -> List[Dict]:
    anchors = []
    seen = set()
    for match in _iter_date_matches(chunk_text):
        display_date, precision, sort_date = normalize_date(match.group(0))
        if sort_date == DEFAULT_SORT_DATE:
            continue
        page_reference = infer_page_marker(source_text, chunk_start + match.start())
        key = (sort_date, precision, page_reference)
        if key in seen:
            continue
        seen.add(key)
        anchors.append(
            {
                "raw": match.group(0),
                "date": display_date,
                "precision": precision,
                "sort_date": sort_date,
                "source_page_or_section": page_reference,
            }
        )
    return anchors


def ground_evidence_snippet(evidence_snippet: Optional[str], chunk_text: str) -> Optional[str]:
    evidence = _clean_text(evidence_snippet)
    if len(evidence) < 6:
        return None
    if evidence in chunk_text:
        return evidence

    normalized_chunk = _clean_text(chunk_text)
    if evidence in normalized_chunk:
        return evidence

    normalized_evidence = _normalize_for_compare(evidence)
    normalized_chunk_compare = _normalize_for_compare(chunk_text)
    if normalized_evidence and normalized_evidence in normalized_chunk_compare:
        return evidence
    return None


def resolve_date_anchor_from_evidence(entry: Dict, grounded_evidence: str, chunk_meta: Dict) -> Optional[Dict]:
    evidence_anchors = _collect_date_anchors(grounded_evidence, grounded_evidence, 0)
    entry_sort_date = entry.get("sort_date") or DEFAULT_SORT_DATE

    if evidence_anchors:
        for anchor in evidence_anchors:
            if anchor.get("sort_date") == entry_sort_date:
                return anchor
        if len(evidence_anchors) == 1:
            return evidence_anchors[0]

    if entry_sort_date == DEFAULT_SORT_DATE:
        return None
    return match_date_anchor_for_entry(entry, chunk_meta)


def match_date_anchor_for_entry(entry: Dict, chunk_meta: Dict) -> Optional[Dict]:
    entry_sort_date = entry.get("sort_date") or DEFAULT_SORT_DATE
    if entry_sort_date == DEFAULT_SORT_DATE:
        return None

    exact_matches = [
        anchor
        for anchor in chunk_meta.get("date_anchors", [])
        if anchor.get("sort_date") == entry_sort_date
    ]
    if exact_matches:
        return exact_matches[0]
    return None


def apply_date_anchor(entry: Dict, anchor: Dict, chunk_meta: Dict) -> Dict:
    updated_entry = dict(entry)
    updated_entry["date"] = anchor.get("date")
    updated_entry["date_precision"] = anchor.get("precision", updated_entry.get("date_precision", "unknown"))
    updated_entry["sort_date"] = anchor.get("sort_date", DEFAULT_SORT_DATE)
    if not updated_entry.get("date_basis") or updated_entry.get("date_basis") == "unknown":
        updated_entry["date_basis"] = "date_in_text"
    current_reference = updated_entry.get("source_page_or_section")
    if not current_reference or _is_generic_chunk_reference(current_reference):
        updated_entry["source_page_or_section"] = (
            anchor.get("source_page_or_section")
            or chunk_meta.get("page_span")
            or current_reference
            or f"Auszug {updated_entry.get('chunk_number', '?')}"
        )
    return updated_entry


def _has_real_source_reference(reference: Optional[str]) -> bool:
    if not reference:
        return False
    reference_text = str(reference)
    return "Seite " in reference_text or "Abschnitt" in reference_text


def _is_generic_chunk_reference(reference: Optional[str]) -> bool:
    if not reference:
        return False
    return str(reference).startswith("Auszug ")


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
