import streamlit as st
import os
import shutil
import pandas as pd
from abh_assist.ingest.extract_text import extract_text_from_file
from abh_assist.classify.doc_classifier import classify_document
from abh_assist.checklist.engine import check_documents, load_checklist
from abh_assist.extract.fields import extract_fields_llm
from abh_assist.extract.consistency import check_consistency
from abh_assist.report.build_report import generate_final_report
from abh_assist.report.export import save_report
from abh_assist.rag.index import build_index
from abh_assist.case import save_case_metadata

st.set_page_config(page_title="ABH-Assist", page_icon="🏛️", layout="wide")

def normalize_name(name_value):
    """Convert name dict to string format."""
    if isinstance(name_value, dict):
        surname = name_value.get('surname', '')
        given_names = name_value.get('given_names', '')
        return f"{given_names} {surname}".strip()
    return str(name_value) if name_value else "Unbekannt"

st.title("🏛️ ABH-Assist")
st.markdown("**Empfangsassistent für Ausländerbehörde** - *Lokal, Offline, Sicher*")

st.divider()

# Sidebar Configuration
st.sidebar.header("Fallkonfiguration")
case_type_map = {
    "A": "Verlängerung Aufenthaltstitel",
    "B": "Fiktionsbescheinigung",
    "C": "Niederlassungserlaubnis",
    "D": "Familiennachzug",
    "E": "Blaue Karte EU"
}
selected_case_code = st.sidebar.selectbox("Falltyp auswählen", list(case_type_map.keys()), format_func=lambda x: f"{x} - {case_type_map[x]}")

st.sidebar.subheader("Falldetails")
employed = st.sidebar.checkbox("Erwerbstätig?")
student = st.sidebar.checkbox("Student?")
child_joining = st.sidebar.checkbox("Familiennachzug (Kind)?")

case_details = {
    "employed": employed,
    "student": student,
    "child_joining": child_joining
}

# --- NEW: Display Checklist Requirements Upfront ---
checklist_data = load_checklist(selected_case_code)
if checklist_data:
    st.info(f"📋 **Erforderliche Unterlagen für: {case_type_map[selected_case_code]}**")
    
    req_docs = checklist_data.get('required_docs', [])
    if req_docs:
        st.markdown("Folgende Dokumente sind in der Regel erforderlich:")
        for doc in req_docs:
            st.markdown(f"- **{doc}**")
    
    # Optional: Show conditional requirements if you want to get fancy, 
    # but for now let's stick to the main list or what's in the yaml.
    
    st.markdown("---")
# ---------------------------------------------------

# File Upload
uploaded_files = st.file_uploader("Dokumente hochladen", accept_multiple_files=True, type=['pdf'])

if st.button("Fall analysieren"):
    if not uploaded_files:
        st.error("Bitte laden Sie zuerst Dokumente hoch.")
    else:
        # Create temp case folder
        case_id = "case_temp"
        case_dir = os.path.join("cases", case_id)
        if os.path.exists(case_dir):
            shutil.rmtree(case_dir)
        os.makedirs(case_dir)

        # Progress Bar
        progress_bar = st.progress(0)
        status_text = st.empty()

        # 1. Ingest & Classify
        status_text.text("Dokumente werden eingelesen und klassifiziert...")
        classified_docs = []
        
        for i, uploaded_file in enumerate(uploaded_files):
            file_path = os.path.join(case_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            text = extract_text_from_file(file_path)
            cls_result = classify_document(uploaded_file.name, text)
            
            if cls_result['doc_type'] == 'unknown_please_rename':
                st.error(f"⚠️ Dokument '{uploaded_file.name}' konnte nicht identifiziert werden. Bitte benennen Sie es um (z.B. 'reisepass', 'antrag', 'mietvertrag').")
            
            doc_info = {
                "filename": uploaded_file.name,
                "text": text,
                **cls_result
            }
            classified_docs.append(doc_info)
            progress_bar.progress((i + 1) / len(uploaded_files) * 0.3)

        # 2. Checklist
        status_text.text("Checkliste wird geprüft...")
        missing_docs = check_documents(selected_case_code, classified_docs, case_details)
        progress_bar.progress(0.5)

        # 3. Extraction & Consistency
        status_text.text("Daten werden extrahiert und geprüft...")
        extracted_data = []
        applicant_name = "Unbekannt"
        
        for doc in classified_docs:
            fields = extract_fields_llm(doc['text'], doc['doc_type'])
            doc.update(fields)
            extracted_data.append(doc)
            
            # Try to find applicant name
            if applicant_name == "Unbekannt" and 'full_name' in fields:
                applicant_name = normalize_name(fields['full_name'])
        
        # Create Case ID with name if found
        if applicant_name != "Unbekannt":
            # Sanitize name for folder usage
            safe_name = "".join([c for c in applicant_name if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
            new_case_id = f"Case_{safe_name}"
            
            # Rename folder
            new_case_dir = os.path.join("cases", new_case_id)
            
            # If case already exists, add timestamp to differentiate
            if os.path.exists(new_case_dir):
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_case_id = f"Case_{safe_name}_{timestamp}"
                new_case_dir = os.path.join("cases", new_case_id)
            
            try:
                os.rename(case_dir, new_case_dir)
                case_id = new_case_id
                case_dir = new_case_dir
                st.success(f"✅ Neue Akte erstellt: **{applicant_name}** (ID: {case_id})")
            except Exception as e:
                st.warning(f"Konnte Fallordner nicht umbenennen: {e}")
        else:
            st.warning("⚠️ Konnte keinen Namen aus den Dokumenten extrahieren. Akte wird mit ID 'case_temp' erstellt.")

        flags = check_consistency(extracted_data)
        progress_bar.progress(0.7)

        # 4. Report Generation (LLM)
        status_text.text("Bericht und Fragen werden generiert...")
        report_data = {
            "case_type": case_type_map[selected_case_code],
            "documents": classified_docs,
            "missing_documents": missing_docs,
            "flags": flags
        }
        
        final_report = generate_final_report(report_data)
        progress_bar.progress(1.0)
        status_text.text("Analyse abgeschlossen.")

        # Save case metadata
        case_status = "Vollständig" if not missing_docs else "Unvollständig"
        
        case_metadata = {
            'case_id': case_id,
            'applicant_name': applicant_name,
            'case_type': case_type_map[selected_case_code],
            'case_type_code': selected_case_code,
            'status': case_status,
            'missing_documents': missing_docs,
            'document_count': len(classified_docs),
            'case_details': case_details
        }
        
        save_case_metadata(case_id, case_metadata)
        
        # Store in session state for navigation
        st.session_state['current_case_id'] = case_id
        st.session_state['analysis_complete'] = True

        # Display Results
        st.divider()
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Übersicht", "Dokumente", "Analyse", "Fragen", "Aktennotiz"])
        
        with tab1:
            st.subheader("Status der Unterlagen")
            
            # Get the full list of requirements again to build a complete table
            checklist_data = load_checklist(selected_case_code)
            all_requirements = checklist_data.get('required_docs', []) if checklist_data else []
            
            # Determine which are present
            present_docs = {d['doc_type']: d for d in classified_docs}
            
            status_data = []
            for req in all_requirements:
                is_present = req in present_docs
                doc_data = present_docs[req] if is_present else {}
                
                # Format extracted info for the table
                extracted_info_str = ""
                if is_present:
                    # Filter out internal keys to show only relevant extracted fields
                    ignored_keys = ['filename', 'text', 'doc_type', 'confidence', 'evidence_snippet', 'dates_found']
                    info_items = [f"{k}: {v}" for k, v in doc_data.items() if k not in ignored_keys and v]
                    extracted_info_str = ", ".join(info_items)

                status_data.append({
                    "Dokumententyp": req,
                    "Status": "✅ Vorhanden" if is_present else "❌ Fehlt",
                    "Extrahierte Info": extracted_info_str if extracted_info_str else "-",
                    "Hinweis": "Gefunden" if is_present else "Erforderlich"
                })
            
            # Also add any extra documents that were uploaded but not strictly required
            for doc in classified_docs:
                if doc['doc_type'] not in all_requirements:
                    # Filter out internal keys
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
            
            # Create a clean DataFrame for the documents tab
            docs_table_data = []
            for doc in final_report['documents']:
                # Flatten the dict for the table
                row = {
                    "Dateiname": doc['filename'],
                    "Typ": doc['doc_type'],
                    "Konfidenz": f"{doc['confidence']:.2f}",
                }
                # Add extracted fields dynamically
                ignored_keys = ['filename', 'text', 'doc_type', 'confidence', 'evidence_snippet', 'dates_found']
                for k, v in doc.items():
                    if k not in ignored_keys:
                        row[k] = v
                docs_table_data.append(row)
            
            if docs_table_data:
                st.dataframe(pd.DataFrame(docs_table_data), use_container_width=True)
            
            st.divider()
            st.caption("Dokumentenansicht")
            for doc in final_report['documents']:
                with st.expander(f"📄 {doc['filename']} ({doc['doc_type']})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Metadaten (JSON):**")
                        st.json({k:v for k,v in doc.items() if k != 'text'})
                    
                    with col2:
                        st.markdown("**Inhalt:**")
                        text_content = doc.get('text', '')
                        
                        # Check for Form Data
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
                        
                        st.text_area("Rohdaten (Text)", text_content, height=200)

        with tab3:
            st.subheader("🔍 Datenabgleich")
            
            # 1. Consistency Flags
            st.markdown("#### 🚩 Auffälligkeiten / Hinweise")
            if final_report['flags']:
                for f in final_report['flags']:
                    st.error(f"**{f['code']}**: {f['reason']}")
            else:
                st.success("Keine Auffälligkeiten gefunden.")
            
            st.divider()

            # 2. Passport vs Application Form Comparison
            st.markdown("#### 🛂 Abgleich: Reisepass vs. Antrag")
            
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
                    
                    # Normalize Passport Value (handle dict if present)
                    if isinstance(pass_val, dict):
                        # Convert {'surname': 'X', 'given_names': 'Y'} to string
                        s = pass_val.get('surname', '')
                        g = pass_val.get('given_names', '')
                        pass_val = f"{s}, {g}".strip(', ')
                    
                    # Normalize Form Value
                    if isinstance(form_val, dict):
                        s = form_val.get('surname', '')
                        g = form_val.get('given_names', '')
                        form_val = f"{s}, {g}".strip(', ')

                    # Simple normalization for comparison
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
                        # Fuzzy check for names (order swap)
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
            for q in final_report.get('questions_for_applicant', []):
                st.info(f"❓ {q.get('question')}")
                st.caption(f"Grund: {q.get('reason')}")

        with tab5:
            st.subheader("Entwurf Aktennotiz")
            note = final_report.get('aktennotiz_de', 'Keine Notiz generiert.')
            st.text_area("Bearbeitbare Notiz", value=note, height=300)
            
            json_path, txt_path = save_report(case_id, final_report)
            
            with open(txt_path, "r") as f:
                st.download_button("Notiz herunterladen (.txt)", f, file_name=f"case_{case_id}_note.txt")
            
            with open(json_path, "r") as f:
                st.download_button("Bericht herunterladen (.json)", f, file_name=f"case_{case_id}_report.json")

# Sidebar Utils
st.sidebar.divider()
if st.sidebar.button("Wissensdatenbank neu aufbauen"):
    build_index()
    st.sidebar.success("Index neu aufgebaut.")
