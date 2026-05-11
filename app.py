import os
import shutil
from datetime import datetime

import streamlit as st

from abh_assist.case import analyze_case_documents, save_case_metadata
from abh_assist.report.export import save_report
from abh_assist.ui import display_timeline_report


st.set_page_config(page_title="ABH-Assist", page_icon="📂", layout="wide")


GOAL_PRESETS = [
    "Aufenthaltsbeendigung",
    "Identitaetsklaerung",
    "Widerruf oder Ruecknahme eines Aufenthaltstitels",
    "Pruefung Duldung",
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
        "damit fuer die weitere Bearbeitung nichts Dienliches fehlt."
    )
    return goal.strip() or "Aufenthaltsbeendigung"


st.title("ABH-Assist")
st.markdown("**Zielbezogene Aktenauswertung** - datierte dienliche Eintraege chronologisch finden")
st.divider()

analysis_goal = get_analysis_goal()

st.info(
    "Laden Sie die digitale Akte als PDF- oder Bilddateien hoch. Die Analyse sucht alle datierten "
    "Ereignisse, Entscheidungen, Dokumenthinweise und Umstaende, die fuer das gewaehlte Ziel "
    "dienlich sein koennen, und ordnet sie chronologisch."
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
            with open(file_path, "wb") as file_obj:
                file_obj.write(uploaded_file.getbuffer())

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
        timeline_summary = final_report.get("timeline_summary", {})
        date_range = timeline_summary.get("date_range", {})
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
            "documents_with_entries": timeline_summary.get("documents_with_entries", 0),
            "low_confidence_entry_count": timeline_summary.get("low_confidence_count", 0),
            "date_range_start": date_range.get("start"),
            "date_range_end": date_range.get("end"),
            "case_details": {
                "analysis_goal": analysis_goal,
                "timeline_summary": timeline_summary,
            },
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
