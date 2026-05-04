"""
Akte Details: zielbezogene Chronologie einer digitalen Akte.
"""
import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from abh_assist.case import (
    analyze_case_documents,
    get_case_documents,
    load_case_metadata,
    save_case_metadata,
    update_case_status,
)
from abh_assist.extract.timeline import timeline_entries_to_rows
from abh_assist.report.export import save_report


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
            "case_details": {"analysis_goal": goal},
        }
    )
    save_case_metadata(case_id, metadata)
    st.success("Analyse erfolgreich abgeschlossen.")
    st.rerun()


def display_timeline_report(case_id, report_data):
    entries = report_data.get("timeline_entries", [])
    rows = timeline_entries_to_rows(entries)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Chronologie", "Dokumente", "Pruefhinweise", "Aktennotiz", "Interne Notizen"]
    )

    with tab1:
        st.subheader("Chronologische zielrelevante Eintraege")
        st.caption(f"Ziel: {report_data.get('analysis_goal', 'Nicht angegeben')}")
        if rows:
            timeline_df = pd.DataFrame(rows)
            st.dataframe(timeline_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Chronologie als CSV herunterladen",
                data=timeline_df.to_csv(index=False, encoding="utf-8-sig"),
                file_name=f"chronologie_{case_id}.csv",
                mime="text/csv",
            )
        else:
            st.warning("Es wurden keine datierten zielrelevanten Eintraege gefunden.")

        st.divider()
        for entry in entries:
            title = f"{entry.get('date') or 'Unbekannt'} - {entry.get('event') or 'Eintrag'}"
            with st.expander(title):
                st.write(f"**Kategorie:** {entry.get('category', 'Sonstiges')}")
                st.write(f"**Dienlichkeit:** {entry.get('relevance', '-')}")
                st.write(
                    f"**Quelle:** {entry.get('source_document', '-')} "
                    f"{entry.get('source_page_or_section', '')}"
                )
                st.write(f"**Datumsbasis:** {entry.get('date_basis', '-')}")
                st.write(f"**Konfidenz:** {float(entry.get('confidence', 0) or 0):.2f}")
                if entry.get("evidence_snippet"):
                    st.code(entry["evidence_snippet"])

    with tab2:
        st.subheader("Durchsuchte Dokumente")
        summaries = {
            item.get("filename"): item for item in report_data.get("document_summaries", [])
        }
        doc_rows = []
        for doc in report_data.get("documents", []):
            summary = summaries.get(doc.get("filename"), {})
            doc_rows.append(
                {
                    "Dateiname": doc.get("filename"),
                    "Typ": doc.get("doc_type"),
                    "Konfidenz": f"{float(doc.get('confidence', 0) or 0):.2f}",
                    "Textzeichen": summary.get("text_chars", len(doc.get("text", ""))),
                    "Eintraege": summary.get("events_found", 0),
                }
            )

        if doc_rows:
            st.dataframe(pd.DataFrame(doc_rows), use_container_width=True, hide_index=True)

        for doc in report_data.get("documents", []):
            with st.expander(f"{doc.get('filename')} ({doc.get('doc_type')})"):
                st.json({k: v for k, v in doc.items() if k != "text"})
                st.text_area(
                    "Extrahierter Text",
                    value=doc.get("text", ""),
                    height=240,
                    key=f"text_{case_id}_{doc.get('filename')}",
                )

    with tab3:
        st.subheader("Pruefhinweise zur Vollstaendigkeit")
        notes = report_data.get("coverage_notes", [])
        if notes:
            for note in notes:
                severity = note.get("severity", "LOW")
                message = note.get("message", "")
                documents = note.get("documents") or []
                text = message if not documents else f"{message} Dokumente: {', '.join(documents)}"
                if severity == "HIGH":
                    st.error(text)
                elif severity == "MEDIUM":
                    st.warning(text)
                else:
                    st.info(text)
        else:
            st.success("Keine technischen Pruefhinweise.")

        low_confidence = [entry for entry in entries if float(entry.get("confidence", 0) or 0) < 0.5]
        if low_confidence:
            st.markdown("#### Niedrig konfidente vorsorgliche Treffer")
            st.dataframe(
                pd.DataFrame(timeline_entries_to_rows(low_confidence)),
                use_container_width=True,
                hide_index=True,
            )

    with tab4:
        st.subheader("Entwurf Aktennotiz")
        st.text_area(
            "Bearbeitbare Notiz",
            value=report_data.get("aktennotiz_de", ""),
            height=300,
            key="note_edit",
        )

        st.markdown("#### Exporte")
        txt_path = os.path.join("cases", case_id, f"case_{case_id}_note.txt")
        json_path = os.path.join("cases", case_id, f"case_{case_id}_report.json")
        col1, col2 = st.columns(2)
        with col1:
            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding="utf-8") as f:
                    st.download_button("Aktennotiz (.txt)", f.read(), file_name=f"case_{case_id}_note.txt")
        with col2:
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    st.download_button("Bericht (.json)", f.read(), file_name=f"case_{case_id}_report.json")

    with tab5:
        display_internal_notes(case_id)


def display_internal_notes(case_id):
    st.subheader("Interne Notizen")
    st.caption("Notizen sind nur fuer interne Zwecke und werden nicht in Berichten exportiert.")

    notes_file = os.path.join("cases", case_id, "internal_notes.txt")
    existing_notes = ""
    if os.path.exists(notes_file):
        with open(notes_file, "r", encoding="utf-8") as f:
            existing_notes = f.read()

    if existing_notes:
        with st.expander("Bisherige Notizen anzeigen", expanded=False):
            st.text_area("Verlauf", existing_notes, height=200, disabled=True, key="notes_history")

    new_note = st.text_area(
        "Neue Notiz",
        height=150,
        key="new_note_input",
        placeholder="Interne Bemerkungen, Telefonnotizen, Erinnerungen...",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Notiz speichern", type="primary", disabled=not new_note):
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            formatted_note = f"[{timestamp}]\n{new_note}\n{'-' * 50}\n\n"
            with open(notes_file, "a", encoding="utf-8") as f:
                f.write(formatted_note)
            st.success("Notiz gespeichert.")
            st.rerun()

    with col2:
        if existing_notes:
            st.download_button(
                "Notizen herunterladen",
                existing_notes,
                file_name=f"notizen_{case_id}.txt",
            )


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

st.title(f"📄 Akte: {applicant_name}")
st.caption(f"**Akte-ID:** `{case_id}`")

if st.button("← Zurueck zur Uebersicht"):
    st.switch_page("pages/1_📁_Akten.py")

st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Name", applicant_name)
with col2:
    st.metric("Analyseziel", goal)
with col3:
    st.metric("Status", metadata.get("status", "Unbekannt"))
with col4:
    st.metric("Dokumente", len(docs))

st.divider()

with st.expander("Status aktualisieren"):
    statuses = ["Neu", "Analysiert", "In Prüfung", "Unvollständig", "Vollständig", "Abgeschlossen", "Unbekannt"]
    current_status = metadata.get("status", "Unbekannt")
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
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
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
    with open(report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

if report_data and "timeline_entries" in report_data:
    display_timeline_report(case_id, report_data)
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
