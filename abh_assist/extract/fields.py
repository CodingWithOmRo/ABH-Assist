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
                raw_map[k.strip()] = v.strip()
        
        # Map common German form fields to our schema
        # Adjust these keys based on what your specific PDF produces
        if 'Nachname' in raw_map:
            data['surname'] = raw_map['Nachname']
        elif 'Familienname' in raw_map:
            data['surname'] = raw_map['Familienname']

        if 'Vorname' in raw_map:
            data['given_names'] = raw_map['Vorname']
        elif 'Vornamen' in raw_map:
            data['given_names'] = raw_map['Vornamen']
        
        # Construct full name
        if 'surname' in data or 'given_names' in data:
            data['full_name'] = f"{data.get('surname', '')}, {data.get('given_names', '')}".strip(', ')
            
        if 'Geburtsdatum' in raw_map:
            data['date_of_birth'] = raw_map['Geburtsdatum']
        if 'Staatsangehörigkeit' in raw_map:
            data['nationality'] = raw_map['Staatsangehörigkeit']
        if 'Passnummer' in raw_map:
            data['passport_number'] = raw_map['Passnummer']
        if 'Ort, Datum' in raw_map:
            data['application_date'] = raw_map['Ort, Datum']
            
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
                
    return extracted_data
