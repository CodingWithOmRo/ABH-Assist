import yaml
import os

CHECKLIST_DIR = "checklists"

def load_checklist(case_type_key):
    # Map case type keys to filenames
    mapping = {
        "A": "general_renewal.yaml",
        "B": "fiktionsbescheinigung.yaml", # Assuming same requirements mostly or specific file
        "C": "permanent_residence.yaml",
        "D": "family_reunification.yaml",
        "E": "blue_card.yaml",
        "F": "student_extension.yaml"
    }
    
    filename = mapping.get(case_type_key)
    if not filename:
        return None
        
    path = os.path.join(CHECKLIST_DIR, filename)
    if not os.path.exists(path):
        return None
        
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def check_documents(case_type_key, classified_docs, case_details):
    """
    Compares classified docs against the checklist.
    classified_docs: list of dicts {doc_type: ...}
    case_details: dict of user inputs (e.g. {'employed': True})
    """
    checklist = load_checklist(case_type_key)
    if not checklist:
        return [], []

    present_types = {d['doc_type'] for d in classified_docs}
    missing = []
    
    # Check required
    for req in checklist.get('required_docs', []):
        if req not in present_types:
            missing.append({
                "doc_type": req,
                "required": True,
                "confidence": 1.0,
                "reason": "Required document not found in uploads."
            })
            
    # Check conditional
    for cond in checklist.get('conditional_docs', []):
        condition_key = cond.get('if')
        # Check if condition is met in case_details
        # case_details keys might need normalization
        if case_details.get(condition_key, False):
            for doc in cond.get('docs', []):
                if doc not in present_types:
                    missing.append({
                        "doc_type": doc,
                        "required": True, # It is required because condition is met
                        "confidence": 1.0,
                        "reason": f"Required because '{condition_key}' is selected."
                    })
                    
    return missing
