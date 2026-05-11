import os
from datetime import datetime
from typing import Dict, Iterable, List

import pandas as pd
import streamlit as st

from abh_assist.extract.timeline import EVENT_SCOPE_LABELS, build_timeline_summary, timeline_entries_to_rows


def display_timeline_report(
    report_data: Dict,
    case_id: str | None = None,
    txt_path: str | None = None,
    json_path: str | None = None,
    show_internal_notes: bool = False,
) -> None:
    entries = report_data.get("timeline_entries", [])
    document_summaries = report_data.get("document_summaries", [])
    summary = report_data.get("timeline_summary") or build_timeline_summary(entries, document_summaries)
    key_prefix = case_id or "timeline_review"

    tab_labels = ["Uebersicht", "Chronologie", "Dokumente", "Pruefhinweise", "Aktennotiz"]
    if show_internal_notes:
        tab_labels.append("Interne Notizen")

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _display_overview(report_data, summary)

    with tabs[1]:
        _display_chronology_tab(entries, summary, key_prefix)

    with tabs[2]:
        _display_documents_tab(report_data, key_prefix)

    with tabs[3]:
        _display_review_tab(report_data)

    with tabs[4]:
        _display_note_tab(report_data, case_id=case_id, txt_path=txt_path, json_path=json_path)

    if show_internal_notes:
        with tabs[5]:
            display_internal_notes(case_id or "ad_hoc_case")


def display_internal_notes(case_id: str) -> None:
    st.subheader("Interne Notizen")
    st.caption("Notizen sind nur fuer interne Zwecke und werden nicht exportiert.")

    notes_file = os.path.join("cases", case_id, "internal_notes.txt")
    existing_notes = ""
    if os.path.exists(notes_file):
        with open(notes_file, "r", encoding="utf-8") as file_obj:
            existing_notes = file_obj.read()

    if existing_notes:
        with st.expander("Bisherige Notizen anzeigen", expanded=False):
            st.text_area("Verlauf", existing_notes, height=220, disabled=True, key=f"notes_history_{case_id}")

    new_note = st.text_area(
        "Neue Notiz",
        height=150,
        key=f"new_note_input_{case_id}",
        placeholder="Interne Bemerkungen, Telefonnotizen, Erinnerungen...",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Notiz speichern", type="primary", disabled=not new_note, key=f"save_note_{case_id}"):
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            formatted_note = f"[{timestamp}]\n{new_note}\n{'-' * 50}\n\n"
            with open(notes_file, "a", encoding="utf-8") as file_obj:
                file_obj.write(formatted_note)
            st.success("Notiz gespeichert.")
            st.rerun()

    with col2:
        if existing_notes:
            st.download_button(
                "Notizen herunterladen",
                existing_notes,
                file_name=f"notizen_{case_id}.txt",
                key=f"download_notes_{case_id}",
            )


def _display_overview(report_data: Dict, summary: Dict) -> None:
    st.subheader("Auswertungsuebersicht")
    st.caption(f"Ziel: {report_data.get('analysis_goal', 'Nicht angegeben')}")

    date_range = summary.get("date_range", {})
    date_span = _format_date_span(date_range)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Eintraege", summary.get("entry_count", 0))
    with col2:
        st.metric("Dokumente", summary.get("document_count", 0))
    with col3:
        st.metric("Dokumente mit Treffern", summary.get("documents_with_entries", 0))
    with col4:
        st.metric("Niedrige Konfidenz", summary.get("low_confidence_count", 0))
    with col5:
        st.metric("Zeitraum", date_span)

    rejection_col1, rejection_col2, rejection_col3 = st.columns(3)
    with rejection_col1:
        st.metric("Verworfene Fundstellen", summary.get("rejected_ungrounded", 0))
    with rejection_col2:
        st.metric("Verworfene Datumsangaben", summary.get("rejected_unsupported_date", 0))
    with rejection_col3:
        st.metric("Verworfene Eintraege ohne Datum", summary.get("rejected_missing_date", 0))

    category_rows = summary.get("category_counts", [])
    if category_rows:
        st.markdown("#### Kategorien")
        st.dataframe(pd.DataFrame(category_rows), use_container_width=True, hide_index=True)

    scope_rows = summary.get("event_scope_counts", [])
    if scope_rows:
        st.markdown("#### Bereiche")
        st.dataframe(pd.DataFrame(scope_rows), use_container_width=True, hide_index=True)

    document_rows = summary.get("document_hit_counts", [])
    if document_rows:
        st.markdown("#### Dokumentabdeckung")
        top_rows = []
        for row in document_rows[:10]:
            page_spans = ", ".join(row.get("page_spans") or [])
            top_rows.append(
                {
                    "Datei": row.get("filename"),
                    "Eintraege": row.get("events_found", 0),
                    "LLM akzeptiert": row.get("llm_entries", 0),
                    "Fundstellen verworfen": row.get("rejected_ungrounded", 0),
                    "Daten verworfen": row.get("rejected_unsupported_date", 0),
                    "Seiten": page_spans or "-",
                }
            )
        st.dataframe(pd.DataFrame(top_rows), use_container_width=True, hide_index=True)


def _display_chronology_tab(entries: List[Dict], summary: Dict, key_prefix: str) -> None:
    st.subheader("Chronologische zielrelevante Eintraege")
    st.caption(
        "Die Liste ist recall-orientiert: Im Zweifel wird ein datierter Eintrag aufgenommen, "
        "damit fuer die weitere Sachbearbeitung nichts verlorengeht."
    )

    categories = sorted({entry.get("category") or "Sonstiges" for entry in entries})
    scopes = sorted({EVENT_SCOPE_LABELS.get(entry.get("event_scope") or "unclear", entry.get("event_scope") or "unclear") for entry in entries})
    filter_col1, filter_col2 = st.columns([2, 2])
    with filter_col1:
        search_text = st.text_input(
            "Suche",
            value="",
            key=f"{key_prefix}_timeline_search",
            placeholder="Ereignis, Dokument oder Fundstelle durchsuchen",
        )
    with filter_col2:
        selected_categories = st.multiselect(
            "Kategorien",
            categories,
            default=categories,
            key=f"{key_prefix}_timeline_categories",
        )

    filter_col3, filter_col4 = st.columns(2)
    with filter_col3:
        selected_scopes = st.multiselect(
            "Bereiche",
            scopes,
            default=scopes,
            key=f"{key_prefix}_timeline_scopes",
        )
    with filter_col4:
        only_low_confidence = st.checkbox(
            "Nur niedrige Konfidenz",
            value=False,
            key=f"{key_prefix}_timeline_low_confidence",
        )

    filter_col5, filter_col6 = st.columns(2)
    with filter_col5:
        only_inferred_dates = st.checkbox(
            "Nur abgeleitete Daten",
            value=False,
            key=f"{key_prefix}_timeline_inferred_dates",
        )
    with filter_col6:
        pass

    filtered_entries = _filter_entries(
        entries,
        search_text=search_text,
        selected_categories=selected_categories,
        selected_scopes=selected_scopes,
        only_low_confidence=only_low_confidence,
        only_inferred_dates=only_inferred_dates,
    )

    st.caption(
        f"{len(filtered_entries)} von {summary.get('entry_count', len(entries))} Eintraegen angezeigt."
    )

    if filtered_entries:
        timeline_df = pd.DataFrame(timeline_entries_to_rows(filtered_entries))
        st.dataframe(timeline_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Gefilterte Chronologie als CSV herunterladen",
            data=timeline_df.to_csv(index=False, encoding="utf-8-sig"),
            file_name=f"chronologie_{key_prefix}.csv",
            mime="text/csv",
            key=f"{key_prefix}_download_csv",
        )
    else:
        st.info("Keine Eintraege entsprechen den aktuellen Filtern.")

    st.divider()
    for entry in filtered_entries:
        title = f"{entry.get('date') or 'Unbekannt'} - {entry.get('event') or 'Eintrag'}"
        with st.expander(title):
            st.write(f"**Kategorie:** {entry.get('category', 'Sonstiges')}")
            st.write(
                f"**Bereich:** "
                f"{EVENT_SCOPE_LABELS.get(entry.get('event_scope') or 'unclear', entry.get('event_scope') or 'unclear')}"
            )
            st.write(f"**Dienlichkeit:** {entry.get('relevance', '-')}")
            st.write(
                f"**Quelle:** {entry.get('source_document', '-')} "
                f"{entry.get('source_page_or_section', '')}"
            )
            st.write(f"**Datumsbasis:** {entry.get('date_basis', '-')}")
            st.write(f"**Methode:** {entry.get('extraction_method', '-')}")
            st.write(f"**Konfidenz:** {float(entry.get('confidence', 0) or 0):.2f}")
            if entry.get("evidence_snippet"):
                st.code(entry["evidence_snippet"])


def _display_documents_tab(report_data: Dict, key_prefix: str) -> None:
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
                "Auszuege": summary.get("chunk_count", 0),
                "Eintraege": summary.get("events_found", 0),
                "LLM-Kandidaten": summary.get("llm_candidates", 0),
                "Regex-Treffer": summary.get("regex_entries", 0),
                "LLM-Treffer": summary.get("llm_entries", 0),
                "LLM-Fehler": summary.get("llm_failures", 0),
                "Fundstellen verworfen": summary.get("rejected_ungrounded", 0),
                "Daten verworfen": summary.get("rejected_unsupported_date", 0),
                "Seiten": ", ".join(summary.get("page_spans") or []),
            }
        )

    if doc_rows:
        st.dataframe(pd.DataFrame(doc_rows), use_container_width=True, hide_index=True)

    no_hit_docs = [row["Dateiname"] for row in doc_rows if not row["Eintraege"]]
    if no_hit_docs:
        st.warning(
            "Ohne datierte Treffer: " + ", ".join(no_hit_docs)
        )

    for doc in report_data.get("documents", []):
        filename = doc.get("filename")
        summary = summaries.get(filename, {})
        with st.expander(f"{filename} ({doc.get('doc_type')})"):
            st.json({k: v for k, v in doc.items() if k != "text"})
            if summary:
                st.caption(
                    f"Auszuege: {summary.get('chunk_count', 0)} | "
                    f"Eintraege: {summary.get('events_found', 0)} | "
                    f"LLM akzeptiert: {summary.get('llm_entries', 0)} | "
                    f"Fundstellen verworfen: {summary.get('rejected_ungrounded', 0)} | "
                    f"Daten verworfen: {summary.get('rejected_unsupported_date', 0)} | "
                    f"Seiten: {', '.join(summary.get('page_spans') or []) or '-'}"
                )
            st.text_area(
                "Extrahierter Text",
                value=doc.get("text", ""),
                height=240,
                key=f"text_{key_prefix}_{filename}",
            )


def _display_review_tab(report_data: Dict) -> None:
    st.subheader("Pruefhinweise zur Vollstaendigkeit")
    notes = report_data.get("coverage_notes", [])
    entries = report_data.get("timeline_entries", [])

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
        st.markdown("#### Niedrig konfidente Treffer")
        st.dataframe(
            pd.DataFrame(timeline_entries_to_rows(low_confidence)),
            use_container_width=True,
            hide_index=True,
        )

    inferred_dates = [
        entry
        for entry in entries
        if str(entry.get("date_basis") or "").startswith("inferred_from_document_date")
    ]
    if inferred_dates:
        st.markdown("#### Eintraege mit abgeleitetem Datum")
        st.dataframe(
            pd.DataFrame(timeline_entries_to_rows(inferred_dates)),
            use_container_width=True,
            hide_index=True,
        )


def _display_note_tab(
    report_data: Dict,
    case_id: str | None,
    txt_path: str | None,
    json_path: str | None,
) -> None:
    st.subheader("Entwurf Aktennotiz")
    st.text_area(
        "Bearbeitbare Notiz",
        value=report_data.get("aktennotiz_de", ""),
        height=300,
        key=f"note_edit_{case_id or 'ad_hoc'}",
    )

    st.markdown("#### Exporte")
    col1, col2 = st.columns(2)
    if txt_path and os.path.exists(txt_path):
        with col1:
            with open(txt_path, "r", encoding="utf-8") as file_obj:
                st.download_button(
                    "Aktennotiz (.txt)",
                    file_obj.read(),
                    file_name=f"case_{case_id or 'akte'}_note.txt",
                    key=f"download_txt_{case_id or 'ad_hoc'}",
                )
    if json_path and os.path.exists(json_path):
        with col2:
            with open(json_path, "r", encoding="utf-8") as file_obj:
                st.download_button(
                    "Bericht (.json)",
                    file_obj.read(),
                    file_name=f"case_{case_id or 'akte'}_report.json",
                    key=f"download_json_{case_id or 'ad_hoc'}",
                )


def _filter_entries(
    entries: Iterable[Dict],
    search_text: str,
    selected_categories: List[str],
    selected_scopes: List[str],
    only_low_confidence: bool,
    only_inferred_dates: bool,
) -> List[Dict]:
    filtered_entries = []
    search_lower = (search_text or "").strip().lower()
    allowed_categories = set(selected_categories or [])
    allowed_scopes = set(selected_scopes or [])

    for entry in entries:
        if allowed_categories and (entry.get("category") or "Sonstiges") not in allowed_categories:
            continue
        entry_scope = EVENT_SCOPE_LABELS.get(entry.get("event_scope") or "unclear", entry.get("event_scope") or "unclear")
        if allowed_scopes and entry_scope not in allowed_scopes:
            continue
        if only_low_confidence and float(entry.get("confidence", 0) or 0) >= 0.5:
            continue
        if only_inferred_dates and not str(entry.get("date_basis") or "").startswith("inferred_from_document_date"):
            continue
        if search_lower:
            haystack = " ".join(
                [
                    str(entry.get("event") or ""),
                    str(entry.get("relevance") or ""),
                    str(entry.get("source_document") or ""),
                    str(entry.get("source_page_or_section") or ""),
                    str(entry.get("evidence_snippet") or ""),
                ]
            ).lower()
            if search_lower not in haystack:
                continue
        filtered_entries.append(entry)

    return filtered_entries


def _format_date_span(date_range: Dict) -> str:
    start = date_range.get("start")
    end = date_range.get("end")
    if start and end:
        return f"{start} bis {end}"
    if start:
        return start
    if end:
        return end
    return "Kein Datum"
