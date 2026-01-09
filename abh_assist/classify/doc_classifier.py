import json
from abh_assist.llm.client import run_llm
from abh_assist.llm.prompts import CLASSIFY_DOC_PROMPT

# Strict mapping for filename-based classification
FILENAME_MAP = {
    "passport": ["reisepass", "passport", "pass"],
    "residence_permit_card": ["aufenthaltstitel", "residence_permit", "niederlassungserlaubnis", "fiktionsbescheinigung", "blue_card", "blaue_karte"],
    "application_form": ["antrag", "application", "formular"],
    "meldebescheinigung": ["meldebescheinigung", "registration", "meldebestätigung"],
    "rental_contract": ["mietvertrag", "rental_contract", "wohnungsgeber"],
    "proof_of_income": ["gehaltsabrechnung", "income", "payslip", "salary", "verdienst", "lohnabrechnung"],
    "health_insurance_proof": ["krankenkasse", "insurance", "versicherungsbescheinigung", "kv_nachweis"],
    "bank_statement": ["kontoauszug", "bank_statement", "finanzstatus"],
    "university_enrollment": ["immatrikulation", "enrollment", "studienbescheinigung", "semesterbescheinigung"],
    "employment_contract": ["arbeitsvertrag", "employment_contract"],
    "marriage_certificate": ["heiratsurkunde", "marriage_certificate", "eheurkunde"],
    "birth_certificate": ["geburtsurkunde", "birth_certificate"],
}

KEYWORDS = {
    "passport": ["passport", "reisepass", "pass", "nationality"],
    "residence_permit_card": ["aufenthaltstitel", "residence permit", "niederlassungserlaubnis", "fiktionsbescheinigung"],
    "meldebescheinigung": ["meldebescheinigung", "meldebestätigung", "wohnungsgeberbestätigung"],
    "health_insurance_proof": ["krankenkasse", "versicherungsbescheinigung", "health insurance", "aok", "tk", "barmer"],
    "proof_of_income": ["gehaltsabrechnung", "verdienstabrechnung", "payslip", "salary", "lohnsteuer"],
    "rental_contract": ["mietvertrag", "rental contract", "vermieter"],
    "bank_statement": ["kontoauszug", "bank statement", "sperrkonto", "blocked account"],
    "university_enrollment": ["immatrikulationsbescheinigung", "enrollment", "student"],
    "application_form": ["antrag", "application", "formular"],
}

def classify_document(filename, text):
    """
    Classifies a document based on FILENAME first (Strict Mode).
    If filename contains a known keyword, it forces that classification.
    """
    filename_lower = filename.lower()
    
    # 1. Strict Filename Check
    for doc_type, keywords in FILENAME_MAP.items():
        for kw in keywords:
            if kw in filename_lower:
                return {
                    "doc_type": doc_type,
                    "confidence": 1.0,
                    "evidence_snippet": f"Filename '{filename}' contains keyword '{kw}'"
                }

    # If filename doesn't match, we return 'unknown' to force the user to rename it
    # as per the requirement "worker has to title the pdf".
    # However, to be graceful, we can return 'unknown' and let the UI handle it,
    # or we can try to guess but mark it as low confidence.
    # Given the user's frustration with wrong guesses, returning 'unknown' or a generic type is safer.
    
    return {
        "doc_type": "unknown_please_rename",
        "confidence": 0.0,
        "evidence_snippet": "Filename did not match any required document type patterns."
    }

    # The old content-based logic is disabled to prevent "guessing" and "mixing it up".
    # If you want to re-enable content fallback, uncomment below, but the user specifically asked to avoid guessing.
    
    # text_lower = text.lower()
    # ... (rest of old logic)

