import os
import shutil
from datetime import datetime

import pandas as pd
import streamlit as st

from abh_assist.case import analyze_case_documents, save_case_metadata
from abh_assist.extract.timeline import timeline_entries_to_rows
from abh_assist.report.export import save_report


st.set_page_config(page_title="ABH-Assist", page_icon="🏛️", layout="wide")


GOAL_PRESETS = [
    "Aufenthaltsbeendigung",
    "Identitätsklärung",
    "Widerruf oder Rücknahme eines Aufenthaltstitels",
    "Prüfung Duldung",
    "Benutzerdefiniertes Ziel",
]


def normalize_name(name_value):
    if isinstance(name_value, dict):
        surname = name_value.get("surname", "")
        given_names = name_value.get("given_names", "")
        return f"{given_names} {surname}".strip()
    return str(name_value) if name_value else "Unbekannt"


def build_case_id(applicant_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if applicant_name and applicant_name != "Unbekannt":
        safe_name = "".join(c for c in applicant_name if c.isalnum() or c in (" ", "_")).strip()
        safe_name = safe_name.replace(" ", "_") or "Unbekannt"
        base_id = f"Case_{safe_name}"
    else:
        base_id = f"Case_Aktenauswertung_{timestamp}"

    case_id = base_id
    case_dir = os.path.join("cases", case_id)
    if os.path.exists(case_dir):
        case_id = f"{base_id}_{timestamp}"
    return case_id


def get_analysis_goal():
    st.sidebar.header("Ziel der Aktenauswertung")
    selected_goal = st.sidebar.selectbox("Analyseziel", GOAL_PRESETS)
    if selected_goal == "Benutzerdefiniertes Ziel":
        goal = st.sidebar.text_area(
            "Eigenes Ziel",
            value="Aufenthaltsbeendigung",
            height=120,
        )
    else:
        goal = st.sidebar.text_area(
            "Zielbeschreibung verfeinern",
            value=selected_goal,
            height=120,
        )

    st.sidebar.caption(
        "Die Auswertung ist bewusst weit gefasst: Im Zweifel werden Eintraege aufgenommen, "
        "damit nichts Dienliches fehlt."
    )
    return goal.strip() or "Aufenthaltsbeendigung"


def display_timeline_report(final_report, case_id=None, txt_path=None, json_path=None):
    entries = final_report.get("timeline_entries", [])
    rows = timeline_entries_to_rows(entries)

    tab1, tab2, tab3, tab4 = st.tabs(["Chronologie", "Dokumente", "Pruefhinweise", "Aktennotiz"])

    with tab1:
        st.subheader("Chronologische zielrelevante Eintraege")
        st.caption(f"Ziel: {final_report.get('analysis_goal', 'Nicht angegeben')}")
        if rows:
            timeline_df = pd.DataFrame(rows)
            st.dataframe(timeline_df, use_container_width=True, hide_index=True)
            csv_data = timeline_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "Chronologie als CSV herunterladen",
                data=csv_data,
                file_name=f"chronologie_{case_id or 'akte'}.csv",
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
        doc_rows = []
        for doc in final_report.get("documents", []):
            summary = next(
                (
                    item
                    for item in final_report.get("document_summaries", [])
                    if item.get("filename") == doc.get("filename")
                ),
                {},
            )
            doc_rows.append(
                {
                    "Dateiname": doc.get("filename"),
                    "Typ": doc.get("doc_type"),
                    "Konfidenz": f"{doc.get('confidence', 0):.2f}",
                    "Textzeichen": summary.get("text_chars", len(doc.get("text", ""))),
                    "Eintraege": summary.get("events_found", 0),
                }
            )

        if doc_rows:
            st.dataframe(pd.DataFrame(doc_rows), use_container_width=True, hide_index=True)

        for doc in final_report.get("documents", []):
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
        notes = final_report.get("coverage_notes", [])
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
            value=final_report.get("aktennotiz_de", ""),
            height=300,
        )

        col1, col2 = st.columns(2)
        if txt_path and os.path.exists(txt_path):
            with col1:
                with open(txt_path, "r", encoding="utf-8") as f:
                    st.download_button(
                        "Aktennotiz herunterladen (.txt)",
                        f.read(),
                        file_name=f"case_{case_id}_note.txt",
                    )
        if json_path and os.path.exists(json_path):
            with col2:
                with open(json_path, "r", encoding="utf-8") as f:
                    st.download_button(
                        "Bericht herunterladen (.json)",
                        f.read(),
                        file_name=f"case_{case_id}_report.json",
                    )


st.title("🏛️ ABH-Assist")
st.markdown("**Zielbezogene Aktenauswertung** - datierte dienliche Eintraege chronologisch finden")
st.divider()

analysis_goal = get_analysis_goal()

st.info(
    "Laden Sie die digitale Akte als PDF-Dateien hoch. Die KI sucht alle datierten Eintraege "
    "und Dokumentinhalte, die fuer das Ziel dienlich sein koennen, und sortiert sie chronologisch."
)

uploaded_files = st.file_uploader(
    "Akte hochladen",
    accept_multiple_files=True,
    type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp"],
)

if st.button("Akte chronologisch auswerten", type="primary", use_container_width=True):
    if not uploaded_files:
        st.error("Bitte laden Sie zuerst Dokumente hoch.")
    else:
        temp_case_id = "case_temp"
        temp_case_dir = os.path.join("cases", temp_case_id)
        if os.path.exists(temp_case_dir):
            shutil.rmtree(temp_case_dir)
        os.makedirs(temp_case_dir, exist_ok=True)

        for uploaded_file in uploaded_files:
            file_path = os.path.join(temp_case_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(fraction, message):
            progress_bar.progress(fraction)
            status_text.text(message)

        final_report, applicant_name = analyze_case_documents(
            temp_case_dir,
            [uploaded_file.name for uploaded_file in uploaded_files],
            analysis_goal,
            progress_callback=update_progress,
        )

        applicant_name = normalize_name(applicant_name)
        case_id = build_case_id(applicant_name)
        case_dir = os.path.join("cases", case_id)
        os.rename(temp_case_dir, case_dir)

        json_path, txt_path = save_report(case_id, final_report)
        case_metadata = {
            "case_id": case_id,
            "applicant_name": applicant_name,
            "case_type": f"Zielanalyse: {analysis_goal}",
            "case_type_code": "timeline",
            "analysis_goal": analysis_goal,
            "status": "Analysiert",
            "missing_documents": [],
            "document_count": len(uploaded_files),
            "timeline_entry_count": len(final_report.get("timeline_entries", [])),
            "case_details": {"analysis_goal": analysis_goal},
        }
        save_case_metadata(case_id, case_metadata)

        st.session_state["current_case_id"] = case_id
        st.session_state["selected_case_id"] = case_id
        st.success(f"Neue Akte erstellt: {applicant_name} (ID: {case_id})")

        st.divider()
        display_timeline_report(final_report, case_id=case_id, txt_path=txt_path, json_path=json_path)


st.sidebar.divider()
if st.sidebar.button("Wissensdatenbank neu aufbauen"):
    from abh_assist.rag.index import build_index

    build_index()
    st.sidebar.success("Index neu aufgebaut.")
