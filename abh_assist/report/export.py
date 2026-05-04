import json
import os


def save_report(case_id, report_data):
    case_dir = os.path.join("cases", case_id)
    os.makedirs(case_dir, exist_ok=True)

    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(case_dir, f"case_{case_id}_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    json_path_output = os.path.join(output_dir, f"{case_id}_report.json")
    with open(json_path_output, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    txt_path = os.path.join(case_dir, f"case_{case_id}_note.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        _write_text_report(f, case_id, report_data)

    txt_path_output = os.path.join(output_dir, f"{case_id}_note.txt")
    with open(txt_path_output, "w", encoding="utf-8") as f:
        _write_text_report(f, case_id, report_data)

    return json_path, txt_path


def _write_text_report(file_obj, case_id, report_data):
    file_obj.write(f"Fall: {case_id}\n")
    file_obj.write(f"Typ: {report_data.get('case_type')}\n")
    if report_data.get("analysis_goal"):
        file_obj.write(f"Ziel: {report_data.get('analysis_goal')}\n")
    file_obj.write("\n")

    if "timeline_entries" in report_data:
        _write_timeline_report(file_obj, report_data)
        return

    file_obj.write("AKTENNOTIZ:\n")
    note = report_data.get("aktennotiz_de", "")
    if isinstance(note, dict):
        note = json.dumps(note, ensure_ascii=False)
    file_obj.write(str(note))

    file_obj.write("\n\nFRAGEN AN ANTRAGSTELLER:\n")
    for q in report_data.get("questions_for_applicant", []):
        file_obj.write(f"- {q.get('question')} ({q.get('reason')})\n")


def _write_timeline_report(file_obj, report_data):
    file_obj.write("AKTENNOTIZ:\n")
    note = report_data.get("aktennotiz_de", "")
    if isinstance(note, dict):
        note = json.dumps(note, ensure_ascii=False)
    file_obj.write(str(note))

    file_obj.write("\n\nCHRONOLOGIE:\n")
    for entry in report_data.get("timeline_entries", []):
        date = entry.get("date") or "Unbekannt"
        event = entry.get("event") or ""
        source = entry.get("source_document") or ""
        page = entry.get("source_page_or_section") or ""
        relevance = entry.get("relevance") or ""
        file_obj.write(f"- {date}: {event}\n")
        file_obj.write(f"  Dienlichkeit: {relevance}\n")
        file_obj.write(f"  Quelle: {source} {page}\n")

    notes = report_data.get("coverage_notes", [])
    if notes:
        file_obj.write("\nPRUEFHINWEISE:\n")
        for note in notes:
            message = note.get("message") if isinstance(note, dict) else str(note)
            file_obj.write(f"- {message}\n")
