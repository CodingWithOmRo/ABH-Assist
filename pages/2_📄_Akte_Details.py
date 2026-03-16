"""
Akte Details (Case Detail View)
Shows complete analysis for a selected case.
"""
import streamlit as st
import os
import pandas as pd
from abh_assist.case import load_case_metadata, update_case_status, get_case_documents
from abh_assist.checklist.engine import load_checklist

st.set_page_config(page_title="Akte Details", layout="wide", page_icon="📄")

def normalize_name(name_value):
    """Convert name dict to string format."""
    if isinstance(name_value, dict):
        surname = name_value.get('surname', '')
        given_names = name_value.get('given_names', '')
        return f"{given_names} {surname}".strip()
    return str(name_value) if name_value else "Unbekannt"

# Check if a case is selected
if 'selected_case_id' not in st.session_state:
    st.warning("⚠️ Keine Akte ausgewählt. Bitte wählen Sie eine Akte auf der Akten-Übersicht-Seite aus.")
    if st.button("Zur Akten-Übersicht"):
        st.switch_page("pages/1_📁_Akten.py")
    st.stop()

case_id = st.session_state['selected_case_id']
metadata = load_case_metadata(case_id)

if not metadata:
    st.error(f"❌ Akte '{case_id}' konnte nicht geladen werden.")
    if st.button("Zur Akten-Übersicht"):
        st.switch_page("pages/1_📁_Akten.py")
    st.stop()

# Header
applicant_name = normalize_name(metadata.get('applicant_name', 'Unbekannt'))
st.title(f"📄 Akte: {applicant_name}")
st.caption(f"**Akte-ID:** `{case_id}`")

# Breadcrumb navigation
if st.button("← Zurück zur Übersicht"):
    st.switch_page("pages/1_📁_Akten.py")

st.divider()

# Case info header
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Name", applicant_name)

with col2:
    st.metric("Falltyp", metadata.get('case_type', 'Nicht angegeben'))

with col3:
    current_status = metadata.get('status', 'Unbekannt')
    st.metric("Status", current_status)

with col4:
    docs = get_case_documents(case_id)
    st.metric("Dokumente", len(docs))

# Status update
st.divider()
with st.expander("⚙️ Status aktualisieren"):
    new_status = st.selectbox(
        "Neuer Status",
        ["Neu", "Unvollständig", "Vollständig", "Abgeschlossen"],
        index=["Neu", "Unvollständig", "Vollständig", "Abgeschlossen"].index(current_status) 
              if current_status in ["Neu", "Unvollständig", "Vollständig", "Abgeschlossen"] else 0
    )
    
    if st.button("Status speichern"):
        update_case_status(case_id, new_status)
        st.success(f"✅ Status aktualisiert auf: {new_status}")
        st.rerun()

st.divider()

# Add documents section (always available)
with st.expander("📎 Weitere Dokumente hinzufügen"):
    st.write("Laden Sie zusätzliche Dokumente hoch und führen Sie die Analyse erneut durch.")
    
    add_files = st.file_uploader(
        "Dokumente hinzufügen", 
        accept_multiple_files=True, 
        type=['pdf'],
        key="add_more_docs"
    )
    
    col_upload, col_analyze = st.columns(2)
    
    with col_upload:
        if st.button("📤 Dokumente hochladen", disabled=not add_files):
            case_dir = os.path.join("cases", case_id)
            os.makedirs(case_dir, exist_ok=True)
            
            uploaded_count = 0
            for uploaded_file in add_files:
                file_path = os.path.join(case_dir, uploaded_file.name)
                if not os.path.exists(file_path):
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    uploaded_count += 1
            
            if uploaded_count > 0:
                st.success(f"✅ {uploaded_count} Dokument(e) hochgeladen!")
                st.rerun()
    
    with col_analyze:
        if st.button("🔄 Analyse erneut durchführen"):
            # Delete existing report to trigger re-analysis
            report_path = os.path.join("cases", case_id, f"case_{case_id}_report.json")
            if os.path.exists(report_path):
                os.remove(report_path)
            st.info("Analyse wird neu gestartet...")
            st.rerun()

st.divider()

# Load report data if exists
report_path = os.path.join("cases", case_id, f"case_{case_id}_report.json")
report_data = None

if os.path.exists(report_path):
    import json
    with open(report_path, 'r', encoding='utf-8') as f:
        report_data = json.load(f)

# Tabs for detailed analysis
if report_data:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Übersicht", "Dokumente", "Analyse", "Fragen", "Aktennotiz"])
    
    with tab1:
        st.subheader("Status der Unterlagen")
        
        # Get checklist
        case_type_code = metadata.get('case_type_code', 'A')
        checklist_data = load_checklist(case_type_code)
        all_requirements = checklist_data.get('required_docs', []) if checklist_data else []
        
        # Build status table
        classified_docs = report_data.get('documents', [])
        present_docs = {d['doc_type']: d for d in classified_docs}
        
        status_data = []
        for req in all_requirements:
            is_present = req in present_docs
            doc_data = present_docs[req] if is_present else {}
            
            extracted_info_str = ""
            if is_present:
                ignored_keys = ['filename', 'text', 'doc_type', 'confidence', 'evidence_snippet', 'dates_found']
                info_items = [f"{k}: {v}" for k, v in doc_data.items() if k not in ignored_keys and v]
                extracted_info_str = ", ".join(info_items)

            status_data.append({
                "Dokumententyp": req,
                "Status": "✅ Vorhanden" if is_present else "❌ Fehlt",
                "Extrahierte Info": extracted_info_str if extracted_info_str else "-",
                "Hinweis": "Gefunden" if is_present else "Erforderlich"
            })
        
        # Add extra documents
        for doc in classified_docs:
            if doc['doc_type'] not in all_requirements:
                ignored_keys = ['filename', 'text', 'doc_type', 'confidence', 'evidence_snippet', 'dates_found']
                info_items = [f"{k}: {v}" for k, v in doc.items() if k not in ignored_keys and v]
                extracted_info_str = ", ".join(info_items)
                
                status_data.append({
                    "Dokumententyp": doc['doc_type'],
                    "Status": "ℹ️ Zusätzlich",
                    "Extrahierte Info": extracted_info_str if extracted_info_str else "-",
                    "Hinweis": "Zusätzlich hochgeladen"
                })

        if status_data:
            st.dataframe(pd.DataFrame(status_data), use_container_width=True)
        else:
            st.info("Keine spezifische Checkliste für diesen Falltyp verfügbar.")

    with tab2:
        st.subheader("Details der Dokumente")
        
        docs_table_data = []
        for doc in report_data['documents']:
            row = {
                "Dateiname": doc['filename'],
                "Typ": doc['doc_type'],
                "Konfidenz": f"{doc['confidence']:.2f}",
            }
            ignored_keys = ['filename', 'text', 'doc_type', 'confidence', 'evidence_snippet', 'dates_found']
            for k, v in doc.items():
                if k not in ignored_keys:
                    row[k] = v
            docs_table_data.append(row)
        
        if docs_table_data:
            st.dataframe(pd.DataFrame(docs_table_data), use_container_width=True)
        
        st.divider()
        st.caption("Dokumentenansicht")
        for doc in report_data['documents']:
            with st.expander(f"📄 {doc['filename']} ({doc['doc_type']})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Metadaten (JSON):**")
                    st.json({k:v for k,v in doc.items() if k != 'text'})
                
                with col2:
                    st.markdown("**Inhalt:**")
                    text_content = doc.get('text', '')
                    
                    if "--- FORM DATA START ---" in text_content:
                        try:
                            start = text_content.find("--- FORM DATA START ---") + len("--- FORM DATA START ---")
                            end = text_content.find("--- FORM DATA END ---")
                            form_data_str = text_content[start:end].strip()
                            form_lines = form_data_str.split('\n')
                            form_dict = {}
                            for line in form_lines:
                                if ": " in line:
                                    k, v = line.split(": ", 1)
                                    form_dict[k.strip()] = v.strip()
                            
                            st.info("📝 **Erkannte Formulardaten:**")
                            st.table(pd.DataFrame(list(form_dict.items()), columns=["Feld", "Wert"]))
                        except:
                            pass
                    
                    st.text_area("Rohdaten (Text)", text_content, height=200, key=f"text_{doc['filename']}")

    with tab3:
        st.subheader("🔍 Datenabgleich")
        
        st.markdown("#### 🚩 Auffälligkeiten / Hinweise")
        flags = report_data.get('flags', [])
        if flags:
            for f in flags:
                st.error(f"**{f['code']}**: {f['reason']}")
        else:
            st.success("Keine Auffälligkeiten gefunden.")
        
        st.divider()

        st.markdown("#### 🛂 Abgleich: Reisepass vs. Antrag")
        
        classified_docs = report_data.get('documents', [])
        passport_doc = next((d for d in classified_docs if d['doc_type'] == 'passport'), None)
        app_form_doc = next((d for d in classified_docs if d['doc_type'] == 'application_form'), None)
        
        if passport_doc and app_form_doc:
            comparison_data = []
            fields_to_compare = [
                ("Vollständiger Name", "full_name"),
                ("Geburtsdatum", "date_of_birth"),
                ("Staatsangehörigkeit", "nationality"),
                ("Passnummer", "passport_number")
            ]
            
            for label, key in fields_to_compare:
                pass_val = passport_doc.get(key, None)
                form_val = app_form_doc.get(key, None)
                
                # Convert None to empty string for cleaner display
                if pass_val is None or pass_val == "null":
                    pass_val = ""
                if form_val is None or form_val == "null":
                    form_val = ""
                
                if isinstance(pass_val, dict):
                    s = pass_val.get('surname', '')
                    g = pass_val.get('given_names', '')
                    pass_val = f"{s}, {g}".strip(', ')
                
                if isinstance(form_val, dict):
                    s = form_val.get('surname', '')
                    g = form_val.get('given_names', '')
                    form_val = f"{s}, {g}".strip(', ')

                match = "✅ OK"
                
                p_str = str(pass_val).lower().strip()
                f_str = str(form_val).lower().strip()
                
                # Check if either value is missing/empty
                if not p_str and not f_str:
                    match = "⚠️ Beide fehlen"
                    pass_val = "(leer)"
                    form_val = "(leer)"
                elif not p_str:
                    match = "⚠️ Pass fehlt"
                    pass_val = "(leer)"
                elif not f_str:
                    match = "⚠️ Antrag fehlt"
                    form_val = "(leer)"
                elif p_str != f_str:
                    if key == "full_name" and (p_str.replace(',', '') == f_str.replace(',', '') or 
                                             p_str.split(',')[0] in f_str):
                         match = "✅ OK (Ähnlich)"
                    else:
                        match = "❌ Abweichung"
                
                comparison_data.append({
                    "Feld": label,
                    "Wert im Pass": pass_val,
                    "Wert im Antrag": form_val,
                    "Status": match
                })
            
            st.table(pd.DataFrame(comparison_data))
        else:
            st.warning("Für den Abgleich werden Reisepass und Antrag benötigt.")

    with tab4:
        st.subheader("Offene Fragen")
        questions = report_data.get('questions_for_applicant', [])
        if questions:
            for q in questions:
                st.info(f"❓ {q.get('question')}")
                st.caption(f"Grund: {q.get('reason')}")
        else:
            st.success("Keine offenen Fragen.")

    with tab5:
        st.subheader("Entwurf Aktennotiz")
        note = report_data.get('aktennotiz_de', 'Keine Notiz generiert.')
        st.text_area("Bearbeitbare Notiz", value=note, height=300, key="note_edit")
        
        # Download buttons
        col1, col2 = st.columns(2)
        
        txt_path = os.path.join("cases", case_id, f"case_{case_id}_note.txt")
        json_path = os.path.join("cases", case_id, f"case_{case_id}_report.json")
        
        with col1:
            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding='utf-8') as f:
                    st.download_button("📄 Notiz herunterladen (.txt)", f.read(), file_name=f"case_{case_id}_note.txt")
        
        with col2:
            if os.path.exists(json_path):
                with open(json_path, "r", encoding='utf-8') as f:
                    st.download_button("📊 Bericht herunterladen (.json)", f.read(), file_name=f"case_{case_id}_report.json")

else:
    st.info("📁 Diese Akte wurde erstellt, aber noch keine vollständige Analyse durchgeführt.")
    
    # Show basic info
    st.subheader("Vorhandene Dokumente")
    docs = get_case_documents(case_id)
    if docs:
        for doc in docs:
            st.write(f"- {doc}")
    else:
        st.write("Keine Dokumente vorhanden.")
    
    st.divider()
    
    # File upload section for adding more documents
    st.subheader("📎 Weitere Dokumente hinzufügen")
    new_files = st.file_uploader(
        "Zusätzliche Dokumente hochladen", 
        accept_multiple_files=True, 
        type=['pdf'],
        key="add_docs_uploader"
    )
    
    # Upload button
    if new_files and st.button("📤 Dokumente hochladen", key="upload_btn"):
        case_dir = os.path.join("cases", case_id)
        os.makedirs(case_dir, exist_ok=True)
        
        uploaded_count = 0
        for uploaded_file in new_files:
            file_path = os.path.join(case_dir, uploaded_file.name)
            # Check if file already exists
            if not os.path.exists(file_path):
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                uploaded_count += 1
        
        if uploaded_count > 0:
            st.success(f"✅ {uploaded_count} Dokument(e) hochgeladen!")
            st.rerun()
    
    st.divider()
    
    # Run analysis button
    if st.button("🔍 Analyse durchführen", type="primary", use_container_width=True, key="analyze_btn"):
        # Refresh docs list to include newly uploaded files
        all_docs = get_case_documents(case_id)
        
        if not all_docs:
            st.error("Bitte laden Sie zuerst Dokumente hoch.")
        else:
            # Import necessary modules
            from abh_assist.ingest.extract_text import extract_text_from_file
            from abh_assist.classify.doc_classifier import classify_document
            from abh_assist.checklist.engine import check_documents
            from abh_assist.extract.fields import extract_fields_llm
            from abh_assist.extract.consistency import check_consistency
            from abh_assist.report.build_report import generate_final_report
            from abh_assist.report.export import save_report
            from abh_assist.case import save_case_metadata
            
            case_dir = os.path.join("cases", case_id)
            
            # Get case details from metadata
            case_details = metadata.get('case_details', {
                "employed": False,
                "student": False,
                "child_joining": False
            })
            
            case_type_code = metadata.get('case_type_code', 'A')
            case_type_name = metadata.get('case_type', 'Verlängerung Aufenthaltstitel')
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 1. Ingest & Classify all documents in the folder
            status_text.text("Dokumente werden eingelesen und klassifiziert...")
            classified_docs = []
            
            all_docs = get_case_documents(case_id)
            for i, filename in enumerate(all_docs):
                file_path = os.path.join(case_dir, filename)
                
                text = extract_text_from_file(file_path)
                cls_result = classify_document(filename, text)
                
                doc_info = {
                    "filename": filename,
                    "text": text,
                    **cls_result
                }
                classified_docs.append(doc_info)
                progress_bar.progress((i + 1) / len(all_docs) * 0.3)
            
            # 2. Checklist
            status_text.text("Checkliste wird geprüft...")
            missing_docs = check_documents(case_type_code, classified_docs, case_details)
            progress_bar.progress(0.5)
            
            # 3. Extraction & Consistency
            status_text.text("Daten werden extrahiert und geprüft...")
            extracted_data = []
            applicant_name_raw = metadata.get('applicant_name', 'Unbekannt')
            applicant_name = normalize_name(applicant_name_raw)
            
            for doc in classified_docs:
                fields = extract_fields_llm(doc['text'], doc['doc_type'])
                doc.update(fields)
                extracted_data.append(doc)
                
                # Update applicant name if found and was unknown
                if applicant_name == "Unbekannt" and 'full_name' in fields:
                    full_name_value = fields['full_name']
                    # Normalize the full_name value
                    if isinstance(full_name_value, dict):
                        surname = full_name_value.get('surname', '')
                        given_names = full_name_value.get('given_names', '')
                        applicant_name = f"{given_names} {surname}".strip()
                    else:
                        applicant_name = str(full_name_value) if full_name_value else "Unbekannt"
            
            flags = check_consistency(extracted_data)
            progress_bar.progress(0.7)
            
            # 4. Report Generation
            status_text.text("Bericht und Fragen werden generiert...")
            report_data = {
                "case_type": case_type_name,
                "documents": classified_docs,
                "missing_documents": missing_docs,
                "flags": flags
            }
            
            final_report = generate_final_report(report_data)
            progress_bar.progress(0.9)
            
            # 5. Save report and update metadata
            status_text.text("Bericht wird gespeichert...")
            save_report(case_id, final_report)
            
            # Update case metadata
            case_status = "Vollständig" if not missing_docs else "Unvollständig"
            
            metadata.update({
                'applicant_name': applicant_name,
                'status': case_status,
                'missing_documents': missing_docs,
                'document_count': len(classified_docs)
            })
            
            save_case_metadata(case_id, metadata)
            
            progress_bar.progress(1.0)
            status_text.text("✅ Analyse abgeschlossen!")
            
            st.success(f"✅ Analyse erfolgreich abgeschlossen! Status: {case_status}")
            st.info("Seite wird neu geladen um die Ergebnisse anzuzeigen...")
            
            # Reload page to show results
            import time
            time.sleep(2)
            st.rerun()
