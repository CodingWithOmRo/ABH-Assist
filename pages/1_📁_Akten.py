"""
Akten-Übersicht (Case Dashboard)
Shows list of all cases with clickable names to view details.
"""
import streamlit as st
import pandas as pd
import os
import shutil
from datetime import datetime
from abh_assist.case import list_all_cases, get_case_documents

st.set_page_config(page_title="Akten-Übersicht", layout="wide", page_icon="📁")

def normalize_name(name_value):
    """Convert name dict to string format."""
    if isinstance(name_value, dict):
        surname = name_value.get('surname', '')
        given_names = name_value.get('given_names', '')
        return f"{given_names} {surname}".strip()
    return str(name_value) if name_value else "Unbekannt"

st.title("📁 Akten-Übersicht")
st.markdown("**Alle Fälle im System**")

# Load all cases
cases = list_all_cases()

if not cases:
    st.info("Noch keine Akten vorhanden. Laden Sie Dokumente auf der Hauptseite hoch, um eine neue Akte zu erstellen.")
else:
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Gesamt Akten", len(cases))
    
    with col2:
        new_cases = len([c for c in cases if c.get('status') == 'Neu'])
        st.metric("Neue Akten", new_cases)
    
    with col3:
        incomplete_cases = len([c for c in cases if c.get('status') == 'Unvollständig'])
        st.metric("Unvollständig", incomplete_cases)
    
    with col4:
        complete_cases = len([c for c in cases if c.get('status') == 'Vollständig'])
        st.metric("Vollständig", complete_cases)
    
    st.divider()
    
    # Search and filter
    col_search, col_filter = st.columns([3, 1])
    
    with col_search:
        search_query = st.text_input("🔍 Suche nach Name oder Akte-ID", "")
    
    with col_filter:
        status_filter = st.selectbox(
            "Filter nach Status",
            ["Alle", "Neu", "Unvollständig", "Vollständig", "Abgeschlossen", "Unbekannt"]
        )
    
    # Filter cases
    filtered_cases = cases
    
    if search_query:
        search_lower = search_query.lower()
        filtered_cases = [
            c for c in filtered_cases 
            if search_lower in normalize_name(c.get('applicant_name', '')).lower() 
            or search_lower in c.get('case_id', '').lower()
        ]
    
    if status_filter != "Alle":
        filtered_cases = [c for c in filtered_cases if c.get('status') == status_filter]
    
    st.markdown(f"**{len(filtered_cases)} Akte(n) gefunden**")
    
    # Display cases as cards
    for case in filtered_cases:
        applicant_name = normalize_name(case.get('applicant_name', 'Unbekannt'))
        
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 0.5])
            
            with col1:
                # Show both ID and name
                case_display = f"👤 {applicant_name} (ID: {case['case_id'][:15]}...)"
                if st.button(
                    case_display, 
                    key=f"case_{case['case_id']}",
                    use_container_width=True
                ):
                    st.session_state['selected_case_id'] = case['case_id']
                    st.switch_page("pages/2_📄_Akte_Details.py")
            
            with col2:
                case_type = case.get('case_type', 'Nicht angegeben')
                st.write(f"**Typ:** {case_type}")
            
            with col3:
                created = case.get('created_date', '')
                if created:
                    try:
                        dt = datetime.fromisoformat(created)
                        st.write(f"**Erstellt:** {dt.strftime('%d.%m.%Y')}")
                    except:
                        st.write(f"**Erstellt:** {created}")
                else:
                    st.write("**Erstellt:** Unbekannt")
            
            with col4:
                status = case.get('status', 'Unbekannt')
                status_colors = {
                    'Neu': '🆕',
                    'Unvollständig': '⚠️',
                    'Vollständig': '✅',
                    'Abgeschlossen': '✔️',
                    'Unbekannt': '❓'
                }
                st.write(f"{status_colors.get(status, '❓')} {status}")
            
            with col5:
                # Delete button
                if st.button("🗑️", key=f"delete_{case['case_id']}", help="Akte löschen"):
                    st.session_state[f'confirm_delete_{case["case_id"]}'] = True
            
            # Confirmation dialog for delete
            if st.session_state.get(f'confirm_delete_{case["case_id"]}', False):
                st.warning(f"⚠️ Möchten Sie die Akte '{applicant_name}' (ID: {case['case_id']}) wirklich löschen?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Ja, löschen", key=f"confirm_yes_{case['case_id']}"):
                        import shutil
                        case_path = os.path.join("cases", case['case_id'])
                        if os.path.exists(case_path):
                            shutil.rmtree(case_path)
                            st.success(f"Akte gelöscht: {case['case_id']}")
                            del st.session_state[f'confirm_delete_{case["case_id"]}']
                            st.rerun()
                with col_no:
                    if st.button("❌ Abbrechen", key=f"confirm_no_{case['case_id']}"):
                        del st.session_state[f'confirm_delete_{case["case_id"]}']
                        st.rerun()
            
            # Additional info in expander
            with st.expander("Details anzeigen"):
                docs = get_case_documents(case['case_id'])
                st.write(f"**Anzahl Dokumente:** {len(docs)}")
                
                if docs:
                    st.write("**Hochgeladene Dokumente:**")
                    for doc in docs:
                        st.write(f"- {doc}")
                
                missing = case.get('missing_documents', [])
                if missing:
                    # Handle both dict and string formats
                    missing_list = []
                    for item in missing:
                        if isinstance(item, dict):
                            missing_list.append(item.get('doc_type', str(item)))
                        else:
                            missing_list.append(str(item))
                    st.write(f"**Fehlende Dokumente:** {', '.join(missing_list)}")
            
            st.divider()

# Sidebar
st.sidebar.header("Aktionen")
if st.sidebar.button("🔄 Aktualisieren"):
    st.rerun()

st.sidebar.divider()
st.sidebar.info("💡 **Tipp:** Klicken Sie auf einen Namen, um die vollständige Akte anzuzeigen.")
