"""
Case management system for storing and retrieving case metadata.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

CASES_DIR = "cases"
METADATA_FILE = "case_metadata.json"


def get_case_metadata_path(case_id: str) -> str:
    """Get the path to the metadata file for a case."""
    case_dir = os.path.join(CASES_DIR, case_id)
    return os.path.join(case_dir, METADATA_FILE)


def save_case_metadata(case_id: str, metadata: Dict) -> None:
    """Save metadata for a case."""
    case_dir = os.path.join(CASES_DIR, case_id)
    os.makedirs(case_dir, exist_ok=True)
    
    metadata_path = get_case_metadata_path(case_id)
    
    # Add timestamps
    if 'created_date' not in metadata:
        metadata['created_date'] = datetime.now().isoformat()
    metadata['last_updated'] = datetime.now().isoformat()
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def load_case_metadata(case_id: str) -> Optional[Dict]:
    """Load metadata for a case."""
    metadata_path = get_case_metadata_path(case_id)
    
    if not os.path.exists(metadata_path):
        return None
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_all_cases() -> List[Dict]:
    """List all cases with their metadata."""
    if not os.path.exists(CASES_DIR):
        return []
    
    cases = []
    for case_id in os.listdir(CASES_DIR):
        case_path = os.path.join(CASES_DIR, case_id)
        
        # Skip if not a directory or if temp folder
        if not os.path.isdir(case_path) or case_id == "case_temp":
            continue
        
        metadata = load_case_metadata(case_id)
        
        # If no metadata file, create basic metadata from folder
        if metadata is None:
            metadata = {
                'case_id': case_id,
                'applicant_name': case_id.replace('Case_', '').replace('_', ' '),
                'created_date': datetime.fromtimestamp(os.path.getctime(case_path)).isoformat(),
                'status': 'Unbekannt'
            }
        
        metadata['case_id'] = case_id  # Ensure case_id is set
        cases.append(metadata)
    
    # Sort by creation date (newest first)
    cases.sort(key=lambda x: x.get('created_date', ''), reverse=True)
    
    return cases


def find_case_by_name(applicant_name: str) -> Optional[str]:
    """Find a case by applicant name. Returns case_id if found."""
    cases = list_all_cases()
    
    # Normalize search name
    search_name = applicant_name.lower().strip().replace(' ', '_')
    
    for case in cases:
        case_name = case.get('applicant_name', '').lower().strip().replace(' ', '_')
        if case_name == search_name:
            return case.get('case_id')
    
    return None


def update_case_status(case_id: str, status: str) -> None:
    """Update the status of a case."""
    metadata = load_case_metadata(case_id)
    if metadata:
        metadata['status'] = status
        save_case_metadata(case_id, metadata)


def get_case_documents(case_id: str) -> List[str]:
    """Get list of documents in a case folder."""
    case_dir = os.path.join(CASES_DIR, case_id)
    
    if not os.path.exists(case_dir):
        return []
    
    documents = []
    supported_extensions = ('.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp')
    for filename in os.listdir(case_dir):
        if filename.lower().endswith(supported_extensions):
            documents.append(filename)
    
    return documents
