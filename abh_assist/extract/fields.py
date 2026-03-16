import re
from abh_assist.llm.client import run_llm
from abh_assist.llm.prompts import (
    EXTRACT_FIELDS_PROMPT, 
    EXTRACT_PASSPORT_PROMPT, 
    EXTRACT_APPLICATION_FORM_PROMPT
)
import json

import re
from abh_assist.llm.client import run_llm
from abh_assist.llm.prompts import (
    EXTRACT_FIELDS_PROMPT, 
    EXTRACT_PASSPORT_PROMPT, 
    EXTRACT_APPLICATION_FORM_PROMPT
)
import json

def parse_form_data_section(text):
    """
    Parses the '--- FORM DATA START ---' section if present.
    Returns a dict of mapped fields.
    """
    data = {}
    if "--- FORM DATA START ---" not in text:
        return data
        
    try:
        start = text.find("--- FORM DATA START ---") + len("--- FORM DATA START ---")
        end = text.find("--- FORM DATA END ---")
        section = text[start:end].strip()
        
        raw_map = {}
        for line in section.split('\n'):
            if ": " in line:
                k, v = line.split(": ", 1)
                # Clean up key: remove array indices like [0], [1] etc.
                clean_key = re.sub(r'\[\d+\]', '', k.strip())
                raw_map[clean_key] = v.strip()
        
        # Map common German form fields to our schema
        # Handle various field name variations
        surname_keys = ['Nachname', 'Familienname', 'surname']
        for key in surname_keys:
            if key in raw_map and raw_map[key]:
                data['surname'] = raw_map[key]
                break

        given_name_keys = ['Vorname', 'Vornamen', 'given_names']
        for key in given_name_keys:
            if key in raw_map and raw_map[key]:
                data['given_names'] = raw_map[key]
                break
        
        # Construct full name
        if 'surname' in data or 'given_names' in data:
            data['full_name'] = f"{data.get('surname', '')}, {data.get('given_names', '')}".strip(', ')
        
        # Date of birth - try multiple variations
        dob_keys = ['Geburtsdatum', 'RP_Geburtsdatum', 'date_of_birth']
        for key in dob_keys:
            if key in raw_map and raw_map[key]:
                data['date_of_birth'] = raw_map[key]
                break
        
        # Nationality
        nationality_keys = ['Staatsangehörigkeit', 'Staatsangehoerigkeit', 'nationality']
        for key in nationality_keys:
            if key in raw_map and raw_map[key]:
                data['nationality'] = raw_map[key]
                break
        
        # Passport number
        passport_keys = ['Passnummer', 'Pass Nr', 'passport_number']
        for key in passport_keys:
            if key in raw_map and raw_map[key]:
                data['passport_number'] = raw_map[key]
                break
        
        # Application date
        date_keys = ['Ort, Datum', 'Tagesdatum', 'Datum']
        for key in date_keys:
            if key in raw_map and raw_map[key]:
                data['application_date'] = raw_map[key]
                break
        
        # Address
        address_keys = ['Anschrift', 'Adresse', 'address']
        for key in address_keys:
            if key in raw_map and raw_map[key]:
                data['address'] = raw_map[key]
                break
            
    except Exception as e:
        print(f"Error parsing form data section: {e}")
        
    return data

def extract_fields_regex(text):
    """
    Simple regex extraction for dates, emails, etc.
    """
    data = {}
    # Date pattern DD.MM.YYYY
    dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', text)
    if dates:
        data['dates_found'] = dates
        
    return data

def extract_fields_llm(text, doc_type):
    """
    Uses LLM to extract specific fields based on doc type.
    """
    # 1. Try deterministic parsing first for Forms
    pre_parsed_data = {}
    if doc_type == "application_form":
        pre_parsed_data = parse_form_data_section(text)

    # Select the best prompt based on doc_type
    if doc_type == "passport":
        prompt = EXTRACT_PASSPORT_PROMPT.format(text_snippet=text[:3000])
    elif doc_type == "application_form":
        # Inject the pre-parsed data into the prompt to help the LLM
        # or just rely on the text snippet if it contains the FORM DATA block
        prompt = EXTRACT_APPLICATION_FORM_PROMPT.format(text_snippet=text[:3000])
    else:
        prompt = EXTRACT_FIELDS_PROMPT.format(doc_type=doc_type, text_snippet=text[:3000])

    response = run_llm(prompt)
    
    extracted_data = {}
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start != -1 and end != -1:
            extracted_data = json.loads(response[start:end])
    except:
        pass
    
    # Merge pre-parsed data (giving it priority if LLM failed or returned null)
    if pre_parsed_data:
        for k, v in pre_parsed_data.items():
            if v and (k not in extracted_data or not extracted_data[k] or extracted_data[k] == "null"):
                extracted_data[k] = v
    
    # Ensure application forms always have expected keys (even if null)
    # This ensures comparison tables can display proper status
    if doc_type == "application_form":
        expected_keys = ["full_name", "date_of_birth", "nationality", "passport_number"]
        for key in expected_keys:
            if key not in extracted_data or extracted_data[key] == "null":
                extracted_data[key] = None
    
    # Same for passports
    if doc_type == "passport":
        expected_keys = ["full_name", "date_of_birth", "nationality", "passport_number"]
        for key in expected_keys:
            if key not in extracted_data or extracted_data[key] == "null":
                extracted_data[key] = None
                
    return extracted_data
