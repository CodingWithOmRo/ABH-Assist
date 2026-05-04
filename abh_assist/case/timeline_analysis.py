import os
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from abh_assist.classify.doc_classifier import classify_document
from abh_assist.extract.fields import extract_fields_llm
from abh_assist.extract.timeline import build_case_timeline
from abh_assist.ingest.extract_text import extract_text_from_file
from abh_assist.report.build_report import generate_final_report


ProgressCallback = Optional[Callable[[float, str], None]]


IDENTITY_DOC_TYPES = {"passport", "application_form", "residence_permit_card"}


def analyze_case_documents(
    case_dir: str,
    filenames: Iterable[str],
    analysis_goal: str,
    existing_applicant_name: str = "Unbekannt",
    progress_callback: ProgressCallback = None,
) -> Tuple[Dict, str]:
    """
    Run the goal-based timeline analysis for all documents in a case folder.
    Returns (final_report, applicant_name).
    """
    file_list = list(filenames)
    classified_docs = []

    _progress(progress_callback, 0.02, "Dokumente werden eingelesen...")
    for index, filename in enumerate(file_list):
        file_path = os.path.join(case_dir, filename)
        text = extract_text_from_file(file_path)
        cls_result = classify_document(filename, text)
        classified_docs.append(
            {
                "filename": filename,
                "text": text,
                **cls_result,
            }
        )
        _progress(
            progress_callback,
            0.05 + ((index + 1) / max(len(file_list), 1)) * 0.25,
            f"Dokument {index + 1}/{len(file_list)} eingelesen...",
        )

    applicant_name = existing_applicant_name or "Unbekannt"
    _progress(progress_callback, 0.35, "Basisdaten werden fuer die Aktenzuordnung gesucht...")
    for doc in classified_docs:
        if doc.get("doc_type") not in IDENTITY_DOC_TYPES:
            continue
        fields = extract_fields_llm(doc.get("text", ""), doc.get("doc_type"))
        doc.update(fields)
        if applicant_name == "Unbekannt" and fields.get("full_name"):
            applicant_name = normalize_name(fields.get("full_name"))

    _progress(progress_callback, 0.45, "Chronologie wird zielbezogen extrahiert...")

    def timeline_progress(done, total):
        fraction = 0.45 + (done / max(total, 1)) * 0.4
        _progress(progress_callback, fraction, f"Chronologie: Dokument {done}/{total} ausgewertet...")

    timeline_data = build_case_timeline(
        classified_docs,
        analysis_goal,
        progress_callback=timeline_progress,
    )

    report_data = {
        "case_type": f"Zielanalyse: {analysis_goal}",
        "analysis_goal": analysis_goal,
        "documents": classified_docs,
        "missing_documents": [],
        "flags": [],
        **timeline_data,
    }

    _progress(progress_callback, 0.9, "Aktennotiz wird erstellt...")
    final_report = generate_final_report(report_data)
    _progress(progress_callback, 1.0, "Analyse abgeschlossen.")
    return final_report, applicant_name


def normalize_name(name_value):
    if isinstance(name_value, dict):
        surname = name_value.get("surname", "")
        given_names = name_value.get("given_names", "")
        return f"{given_names} {surname}".strip() or "Unbekannt"
    return str(name_value).strip() if name_value else "Unbekannt"


def _progress(callback: ProgressCallback, fraction: float, message: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, fraction)), message)
