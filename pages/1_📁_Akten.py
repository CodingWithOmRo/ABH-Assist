"""
Akten-Übersicht für zielbezogene Chronologie-Auswertungen.
"""
import os
import shutil
from datetime import datetime

import streamlit as st

from abh_assist.case import get_case_documents, list_all_cases


st.set_page_config(page_title="Akten-Übersicht", layout="wide", page_icon="📁")


def normalize_name(name_value):
    if isinstance(name_value, dict):
        surname = name_value.get("surname", "")
        given_names = name_value.get("given_names", "")
        return f"{given_names} {surname}".strip()
    return str(name_value) if name_value else "Unbekannt"


def case_goal(case):
    return case.get("analysis_goal") or case.get("case_details", {}).get("analysis_goal") or case.get("case_type", "Nicht angegeben")


def format_date(value):
    if not value:
        return "Unbekannt"
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value


st.title("📁 Akten-Übersicht")
st.markdown("**Alle gespeicherten Akten und zielbezogenen Chronologien**")

cases = list_all_cases()

if not cases:
    st.info("Noch keine Akten vorhanden. Laden Sie Dokumente auf der Hauptseite hoch, um eine neue Akte zu erstellen.")
    st.stop()

total_cases = len(cases)
new_cases = len([case for case in cases if case.get("status") == "Neu"])
analyzed_cases = len([case for case in cases if case.get("status") == "Analysiert"])
in_review_cases = len([case for case in cases if case.get("status") == "In Prüfung"])
closed_cases = len([case for case in cases if case.get("status") == "Abgeschlossen"])

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Gesamt", total_cases)
with col2:
    st.metric("Neu", new_cases)
with col3:
    st.metric("Analysiert", analyzed_cases)
with col4:
    st.metric("In Prüfung", in_review_cases)
with col5:
    st.metric("Abgeschlossen", closed_cases)

with st.expander("Erweiterte Statistiken"):
    stat_col1, stat_col2 = st.columns(2)
    with stat_col1:
        st.markdown("**Häufigste Analyseziele:**")
        goal_count = {}
        for case in cases:
            goal = case_goal(case)
            if goal and goal != "Nicht angegeben":
                goal_count[goal] = goal_count.get(goal, 0) + 1
        if goal_count:
            for goal, count in sorted(goal_count.items(), key=lambda item: item[1], reverse=True)[:5]:
                st.write(f"- {goal}: {count} Akte(n)")
        else:
            st.write("Noch keine Zielanalysen")

    with stat_col2:
        finished = analyzed_cases + in_review_cases + closed_cases
        completion_rate = finished / total_cases * 100 if total_cases else 0
        avg_docs = sum(case.get("document_count", 0) for case in cases) / total_cases
        avg_entries = sum(case.get("timeline_entry_count", 0) for case in cases) / total_cases
        st.markdown("**Bearbeitungsstand:**")
        st.progress(completion_rate / 100)
        st.write(f"{completion_rate:.1f}% mit Chronologie oder Prüfung")
        st.metric("Durchschn. Dokumente/Akte", f"{avg_docs:.1f}")
        st.metric("Durchschn. Chronologie-Einträge", f"{avg_entries:.1f}")

st.divider()

search_col, filter_col = st.columns([3, 1])
with search_col:
    search_query = st.text_input("Suche nach Name, Akte-ID oder Ziel", "")
with filter_col:
    status_filter = st.selectbox(
        "Status",
        ["Alle", "Neu", "Analysiert", "In Prüfung", "Unvollständig", "Vollständig", "Abgeschlossen", "Unbekannt"],
    )

filtered_cases = cases
if search_query:
    search_lower = search_query.lower()
    filtered_cases = [
        case
        for case in filtered_cases
        if search_lower in normalize_name(case.get("applicant_name", "")).lower()
        or search_lower in case.get("case_id", "").lower()
        or search_lower in case_goal(case).lower()
    ]

if status_filter != "Alle":
    filtered_cases = [case for case in filtered_cases if case.get("status") == status_filter]

st.markdown(f"**{len(filtered_cases)} Akte(n) gefunden**")

if "selected_cases" not in st.session_state:
    st.session_state.selected_cases = []

if filtered_cases:
    with st.expander("Massenaktionen"):
        bulk_col1, bulk_col2, bulk_col3 = st.columns([2, 1, 1])
        with bulk_col1:
            select_all = st.checkbox("Alle gefilterten Akten auswählen", key="select_all_cases")
        if select_all:
            st.session_state.selected_cases = [case["case_id"] for case in filtered_cases]
        with bulk_col2:
            if st.button("Ausgewählte löschen", disabled=not st.session_state.selected_cases):
                st.session_state.bulk_delete_confirm = True
        with bulk_col3:
            st.write(f"{len(st.session_state.selected_cases)} ausgewählt")

        if st.session_state.get("bulk_delete_confirm", False):
            st.warning(f"{len(st.session_state.selected_cases)} Akte(n) wirklich löschen?")
            yes_col, no_col = st.columns(2)
            with yes_col:
                if st.button("Ja, löschen", type="primary"):
                    for selected_case_id in st.session_state.selected_cases:
                        case_dir = os.path.join("cases", selected_case_id)
                        if os.path.exists(case_dir):
                            shutil.rmtree(case_dir)
                    st.session_state.selected_cases = []
                    st.session_state.bulk_delete_confirm = False
                    st.rerun()
            with no_col:
                if st.button("Abbrechen"):
                    st.session_state.bulk_delete_confirm = False
                    st.rerun()

st.divider()

status_icons = {
    "Neu": "🆕",
    "Analysiert": "✅",
    "In Prüfung": "🔎",
    "Unvollständig": "⚠️",
    "Vollständig": "✅",
    "Abgeschlossen": "✔️",
    "Unbekannt": "❓",
}

for case in filtered_cases:
    case_id = case["case_id"]
    applicant_name = normalize_name(case.get("applicant_name", "Unbekannt"))
    docs = get_case_documents(case_id)

    with st.container():
        check_col, name_col, goal_col, date_col, status_col, delete_col = st.columns([0.3, 2.4, 2.4, 1.4, 1.2, 0.5])

        with check_col:
            checked = case_id in st.session_state.selected_cases
            if st.checkbox(
                f"Akte {applicant_name} auswählen",
                value=checked,
                key=f"check_{case_id}",
                label_visibility="collapsed",
            ):
                if case_id not in st.session_state.selected_cases:
                    st.session_state.selected_cases.append(case_id)
            elif case_id in st.session_state.selected_cases:
                st.session_state.selected_cases.remove(case_id)

        with name_col:
            label = f"{applicant_name} (ID: {case_id[:18]}...)"
            if st.button(label, key=f"case_{case_id}", use_container_width=True):
                st.session_state["selected_case_id"] = case_id
                st.switch_page("pages/2_📄_Akte_Details.py")

        with goal_col:
            st.write(f"**Ziel:** {case_goal(case)}")
            st.caption(f"{case.get('timeline_entry_count', 0)} Chronologie-Einträge")

        with date_col:
            st.write(f"**Erstellt:** {format_date(case.get('created_date'))}")

        with status_col:
            status = case.get("status", "Unbekannt")
            st.write(f"{status_icons.get(status, '❓')} {status}")

        with delete_col:
            if st.button("🗑️", key=f"delete_{case_id}", help="Akte löschen"):
                st.session_state[f"confirm_delete_{case_id}"] = True

        if st.session_state.get(f"confirm_delete_{case_id}", False):
            st.warning(f"Akte '{applicant_name}' (ID: {case_id}) wirklich löschen?")
            yes_col, no_col = st.columns(2)
            with yes_col:
                if st.button("Ja, löschen", key=f"confirm_yes_{case_id}"):
                    case_path = os.path.join("cases", case_id)
                    if os.path.exists(case_path):
                        shutil.rmtree(case_path)
                    del st.session_state[f"confirm_delete_{case_id}"]
                    st.rerun()
            with no_col:
                if st.button("Abbrechen", key=f"confirm_no_{case_id}"):
                    del st.session_state[f"confirm_delete_{case_id}"]
                    st.rerun()

        with st.expander("Details anzeigen"):
            st.write(f"**Analyseziel:** {case_goal(case)}")
            st.write(f"**Anzahl Dokumente:** {len(docs)}")
            st.write(f"**Chronologie-Einträge:** {case.get('timeline_entry_count', 0)}")
            if docs:
                st.write("**Hochgeladene Dokumente:**")
                for doc in docs:
                    st.write(f"- {doc}")

    st.divider()

st.sidebar.header("Aktionen")
if st.sidebar.button("Aktualisieren"):
    st.rerun()

st.sidebar.divider()
st.sidebar.info("Tipp: Klicken Sie auf einen Namen, um die vollständige Akte anzuzeigen.")
