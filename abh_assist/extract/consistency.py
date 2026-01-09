from datetime import datetime

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%d.%m.%Y")
    except:
        return None

def check_consistency(extracted_data):
    """
    Checks for issues like expired documents or name mismatches.
    extracted_data: list of dicts from extract_fields_llm
    """
    flags = []
    
    today = datetime.now()
    
    passport_data = None
    app_form_data = None

    for item in extracted_data:
        doc_type = item.get('doc_type')
        
        # Store for cross-check
        if doc_type == 'passport':
            passport_data = item
        elif doc_type == 'application_form':
            app_form_data = item
            
            # Check for validation issues in the form itself
            if 'validation_issues' in item and item['validation_issues']:
                for issue in item['validation_issues']:
                    flags.append({
                        "code": "FLAG_FORM_INVALID",
                        "severity": "MEDIUM",
                        "confidence": 1.0,
                        "reason": f"Application Form Issue: {issue}",
                        "evidence_snippet": "Validation Check"
                    })
            
            # Programmatic check for empty critical fields
            critical_fields = ['full_name', 'date_of_birth', 'nationality']
            for field in critical_fields:
                if not item.get(field):
                    flags.append({
                        "code": "FLAG_MISSING_DATA",
                        "severity": "HIGH",
                        "confidence": 1.0,
                        "reason": f"Application Form is missing critical field: {field}",
                        "evidence_snippet": "Field Check"
                    })

        # Check expiry
        if 'expiry_date' in item and item['expiry_date']:
            exp = parse_date(item['expiry_date'])
            if exp and exp < today:
                flags.append({
                    "code": "FLAG_EXPIRED_DOCUMENT",
                    "severity": "HIGH",
                    "confidence": 0.9,
                    "reason": f"Document {item.get('doc_type', 'unknown')} expired on {item['expiry_date']}.",
                    "evidence_snippet": item.get('evidence_snippet', '')
                })
    
    # Cross-Check: Passport vs Application Form
    if passport_data and app_form_data:
        # Helper to safely get name string
        def get_safe_name(data_dict):
            val = data_dict.get('full_name')
            if not val:
                return ""
            if isinstance(val, dict):
                # If LLM returned a dict (e.g. {first:..., last:...}), flatten it
                return " ".join(str(v) for v in val.values()).lower()
            return str(val).lower()

        # 1. Name Check
        pass_name = get_safe_name(passport_data)
        app_name = get_safe_name(app_form_data)
        
        if pass_name and app_name:
            # Simple fuzzy match or containment check
            # If we don't have fuzzywuzzy, we can use basic logic
            # "Doe, John" vs "John Doe" handling
            pass_parts = set(pass_name.replace(',', '').split())
            app_parts = set(app_name.replace(',', '').split())
            
            common = pass_parts.intersection(app_parts)
            if len(common) < min(len(pass_parts), len(app_parts)) * 0.5: # Less than 50% match
                 flags.append({
                    "code": "FLAG_NAME_MISMATCH",
                    "severity": "HIGH",
                    "confidence": 0.8,
                    "reason": f"Name mismatch between Passport ({passport_data.get('full_name')}) and Application ({app_form_data.get('full_name')}).",
                    "evidence_snippet": "Cross-Check"
                })

        # 2. DOB Check
        pass_dob = passport_data.get('date_of_birth')
        app_dob = app_form_data.get('date_of_birth')
        
        if pass_dob and app_dob and pass_dob != app_dob:
             flags.append({
                "code": "FLAG_DOB_MISMATCH",
                "severity": "HIGH",
                "confidence": 0.9,
                "reason": f"Date of Birth mismatch: Passport ({pass_dob}) vs Application ({app_dob}).",
                "evidence_snippet": "Cross-Check"
            })

    return flags
