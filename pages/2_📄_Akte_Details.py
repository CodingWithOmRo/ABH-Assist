"""
Akte Details: zielbezogene Chronologie einer digitalen Akte.
"""
import json
import os

import streamlit as st

from abh_assist.case import (
    analyze_case_documents,
    get_case_documents,
    load_case_metadata,
    save_case_metadata,
    update_case_status,
)
from abh_assist.report.export import save_report
from abh_assist.ui import display_timeline_report


st.set_page_config(page_title="Akte Details", layout="wide", page_icon="📄")


def normalize_name(name_value):
    if isinstance(name_value, dict):
        surname = name_value.get("surname", "")
        given_names = name_value.get("given_names", "")
        return f"{given_names} {surname}".strip()
    return str(name_value) if name_value else "Unbekannt"


def current_goal(metadata):
    return (
        metadata.get("analysis_goal")
        or metadata.get("case_details", {}).get("analysis_goal")
        or "Aufenthaltsbeendigung"
    )


def normalize_status(value):
    mapping = {
        "In Prüfung": "In Pruefung",
        "In PrÃ¼fung": "In Pruefung",
        "Unvollständig": "Unvollstaendig",
        "UnvollstÃ¤ndig": "Unvollstaendig",
        "Vollständig": "Vollstaendig",
        "VollstÃ¤ndig": "Vollstaendig",
    }
    return mapping.get(value, value or "Unbekannt")


def run_analysis(case_id, metadata, goal):
    docs = get_case_documents(case_id)
    if not docs:
        st.error("Bitte laden Sie zuerst Dokumente hoch.")
        return

    case_dir = os.path.join("cases", case_id)
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(fraction, message):
        progress_bar.progress(fraction)
        status_text.text(message)

    final_report, applicant_name = analyze_case_documents(
        case_dir,
        docs,
        goal,
        existing_applicant_name=normalize_name(metadata.get("applicant_name", "Unbekannt")),
        progress_callback=update_progress,
    )
    save_report(case_id, final_report)

    timeline_summary = final_report.get("timeline_summary", {})
    date_range = timeline_summary.get("date_range", {})
    metadata.update(
        {
            "applicant_name": normalize_name(applicant_name),
            "case_type": f"Zielanalyse: {goal}",
            "case_type_code": "timeline",
            "analysis_goal": goal,
            "status": "Analysiert",
            "missing_documents": [],
            "document_count": len(docs),
            "timeline_entry_count": len(final_report.get("timeline_entries", [])),
            "documents_with_entries": timeline_summary.get("documents_with_entries", 0),
            "low_confidence_entry_count": timeline_summary.get("low_confidence_count", 0),
            "date_range_start": date_range.get("start"),
            "date_range_end": date_range.get("end"),
            "case_details": {
                "analysis_goal": goal,
                "timeline_summary": timeline_summary,
            },
        }
    )
    save_case_metadata(case_id, metadata)
    st.success("Analyse erfolgreich abgeschlossen.")
    st.rerun()


if "selected_case_id" not in st.session_state:
    st.warning("Keine Akte ausgewaehlt. Bitte waehlen Sie eine Akte auf der Akten-Uebersicht aus.")
    if st.button("Zur Akten-Uebersicht"):
        st.switch_page("pages/1_📁_Akten.py")
    st.stop()

case_id = st.session_state["selected_case_id"]
metadata = load_case_metadata(case_id)

if not metadata:
    st.error(f"Akte '{case_id}' konnte nicht geladen werden.")
    if st.button("Zur Akten-Uebersicht"):
        st.switch_page("pages/1_📁_Akten.py")
    st.stop()

applicant_name = normalize_name(metadata.get("applicant_name", "Unbekannt"))
goal = current_goal(metadata)
docs = get_case_documents(case_id)
date_range_start = metadata.get("date_range_start")
date_range_end = metadata.get("date_range_end")
date_span = (
    f"{date_range_start} bis {date_range_end}"
    if date_range_start and date_range_end
    else (date_range_start or date_range_end or "Kein Zeitraum")
)

st.title(f"Akte: {applicant_name}")
st.caption(f"**Akte-ID:** `{case_id}`")

if st.button("Zurueck zur Uebersicht"):
    st.switch_page("pages/1_📁_Akten.py")

st.divider()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Name", applicant_name)
with col2:
    st.metric("Analyseziel", goal)
with col3:
    st.metric("Status", metadata.get("status", "Unbekannt"))
with col4:
    st.metric("Dokumente", len(docs))
with col5:
    st.metric("Zeitraum", date_span)

st.caption(
    f"Trefferdokumente: {metadata.get('documents_with_entries', 0)} | "
    f"Niedrige Konfidenz: {metadata.get('low_confidence_entry_count', 0)}"
)

st.divider()

with st.expander("Status aktualisieren"):
    statuses = ["Neu", "Analysiert", "In Pruefung", "Unvollstaendig", "Vollstaendig", "Abgeschlossen", "Unbekannt"]
    current_status = normalize_status(metadata.get("status", "Unbekannt"))
    new_status = st.selectbox(
        "Neuer Status",
        statuses,
        index=statuses.index(current_status) if current_status in statuses else 0,
    )
    if st.button("Status speichern"):
        update_case_status(case_id, new_status)
        st.success(f"Status aktualisiert auf: {new_status}")
        st.rerun()

with st.expander("Dokumente hinzufuegen oder Analyse neu erstellen", expanded=False):
    add_files = st.file_uploader(
        "Weitere Dokumente hochladen",
        accept_multiple_files=True,
        type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp"],
        key="add_more_docs",
    )
    if st.button("Dokumente hochladen", disabled=not add_files):
        case_dir = os.path.join("cases", case_id)
        os.makedirs(case_dir, exist_ok=True)
        uploaded_count = 0
        for uploaded_file in add_files:
            file_path = os.path.join(case_dir, uploaded_file.name)
            if not os.path.exists(file_path):
                with open(file_path, "wb") as file_obj:
                    file_obj.write(uploaded_file.getbuffer())
                uploaded_count += 1
        st.success(f"{uploaded_count} Dokument(e) hochgeladen.")
        st.rerun()

    new_goal = st.text_area("Analyseziel", value=goal, height=100)
    if st.button("Analyse neu erstellen", type="primary"):
        run_analysis(case_id, metadata, new_goal.strip() or "Aufenthaltsbeendigung")

st.divider()

report_path = os.path.join("cases", case_id, f"case_{case_id}_report.json")
report_data = None
if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as file_obj:
        report_data = json.load(file_obj)

if report_data and "timeline_entries" in report_data:
    txt_path = os.path.join("cases", case_id, f"case_{case_id}_note.txt")
    json_path = os.path.join("cases", case_id, f"case_{case_id}_report.json")
    display_timeline_report(
        report_data,
        case_id=case_id,
        txt_path=txt_path,
        json_path=json_path,
        show_internal_notes=True,
    )
else:
    if report_data:
        st.warning(
            "Diese Akte enthaelt noch einen alten checklistenbasierten Bericht. "
            "Erstellen Sie die Analyse neu, um die zielbezogene Chronologie zu erhalten."
        )
    else:
        st.info("Fuer diese Akte wurde noch keine zielbezogene Chronologie erstellt.")

    st.subheader("Vorhandene Dokumente")
    if docs:
        for doc in docs:
            st.write(f"- {doc}")
    else:
        st.write("Keine Dokumente vorhanden.")

    st.divider()
    quick_goal = st.text_area("Analyseziel", value=goal, height=100, key="initial_goal")
    if st.button("Chronologie erstellen", type="primary", use_container_width=True):
        run_analysis(case_id, metadata, quick_goal.strip() or "Aufenthaltsbeendigung")
