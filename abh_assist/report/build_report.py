import json
from abh_assist.llm.client import run_llm
from abh_assist.llm.prompts import (
    CASE_NOTE_PROMPT,
    GENERATE_QUESTIONS_PROMPT,
    TIMELINE_CASE_NOTE_PROMPT,
)
from abh_assist.llm.json_guard import validate_and_fix_json

def generate_final_report(case_data):
    """
    Aggregates all analysis and asks LLM for final questions and note.
    """
    if "timeline_entries" in case_data:
        return generate_timeline_report(case_data)
    
    # 1. Generate Questions
    q_prompt = GENERATE_QUESTIONS_PROMPT.format(
        missing_docs=json.dumps(case_data.get('missing_documents', [])),
        flags=json.dumps(case_data.get('flags', []))
    )
    q_resp = run_llm(q_prompt)
    q_json = validate_and_fix_json(q_resp)
    if q_json:
        case_data['questions_for_applicant'] = q_json.get('questions', [])
        
    # 2. Generate Case Note
    # Minimize context to fit in context window
    mini_context = {
        "case_type": case_data.get("case_type"),
        "present_docs": [d['doc_type'] for d in case_data.get('documents', [])],
        "missing_docs": [d['doc_type'] for d in case_data.get('missing_documents', [])],
        "flags": [f['code'] for f in case_data.get('flags', [])]
    }
    
    n_prompt = CASE_NOTE_PROMPT.format(context_json=json.dumps(mini_context))
    n_resp = run_llm(n_prompt)
    n_json = validate_and_fix_json(n_resp)
    if n_json:
        case_data['aktennotiz_de'] = n_json.get('aktennotiz', "")
        
    return case_data


def generate_timeline_report(case_data):
    """
    Generate the final note for a goal-based chronological file review.
    """
    entries = case_data.get("timeline_entries", [])
    compact_entries = [
        {
            "date": entry.get("date"),
            "event": entry.get("event"),
            "relevance": entry.get("relevance"),
            "category": entry.get("category"),
            "event_scope": entry.get("event_scope"),
            "source_document": entry.get("source_document"),
            "source_page_or_section": entry.get("source_page_or_section"),
            "confidence": entry.get("confidence"),
        }
        for entry in entries[:25]
    ]
    try:
        prompt = TIMELINE_CASE_NOTE_PROMPT.format(
            goal=case_data.get("analysis_goal", ""),
            timeline_json=json.dumps(compact_entries, ensure_ascii=False),
            timeline_summary_json=json.dumps(case_data.get("timeline_summary", {}), ensure_ascii=False),
            coverage_notes_json=json.dumps(case_data.get("coverage_notes", []), ensure_ascii=False),
        )
        response = run_llm(prompt, stop=["User:", "</s>"], max_tokens=512)
        note_json = validate_and_fix_json(response)
    except Exception as exc:
        print(f"Timeline note generation warning: {exc}")
        note_json = None

    if note_json:
        case_data["aktennotiz_de"] = note_json.get("aktennotiz", "")
    else:
        case_data["aktennotiz_de"] = build_fallback_timeline_note(case_data)

    case_data.setdefault("questions_for_applicant", [])
    case_data.setdefault("missing_documents", [])
    case_data.setdefault("flags", [])
    return case_data


def build_fallback_timeline_note(case_data):
    goal = case_data.get("analysis_goal", "Nicht angegeben")
    count = len(case_data.get("timeline_entries", []))
    summary = case_data.get("timeline_summary", {})
    documents = summary.get("documents_with_entries", 0)
    total_documents = summary.get("document_count", 0)
    date_range = summary.get("date_range", {})
    date_span = ""
    if date_range.get("start") and date_range.get("end"):
        date_span = f" Der abgedeckte Zeitraum reicht von {date_range['start']} bis {date_range['end']}."
    return (
        f"Zielbezogene Aktenauswertung zum Ziel '{goal}'. "
        f"Es wurden {count} datierte Eintraege identifiziert und chronologisch geordnet. "
        f"Dabei wurden {documents} von {total_documents} Dokumenten mit mindestens einem Treffer abgedeckt."
        f"{date_span}"
        "Die Liste ist bewusst weit gefasst; niedrig konfidente Eintraege sind anhand der Fundstellen zu pruefen."
    )
