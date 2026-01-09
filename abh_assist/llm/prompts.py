CLASSIFY_DOC_PROMPT = """
You are an assistant for a German immigration office. 
Analyze the following document text snippet and classify it into one of these categories:
[passport, residence_permit_card, application_form, appointment_confirmation, meldebescheinigung, rental_contract, proof_of_income, employment_contract, health_insurance_proof, bank_statement, university_enrollment, marriage_certificate, birth_certificate, pension_insurance_record, other]

Return ONLY valid JSON.
{{
  "doc_type": "category_name",
  "confidence": 0.0 to 1.0,
  "evidence_snippet": "text from document proving this"
}}

Filename: {filename}
Text Snippet:
{text_snippet}
"""

EXTRACT_FIELDS_PROMPT = """
Extract key fields from this {doc_type}.
Return ONLY valid JSON.
Fields to look for (if applicable): full_name, date_of_birth, expiry_date, address, employer_name.
Format dates as DD.MM.YYYY.

Text Snippet:
{text_snippet}
"""

EXTRACT_PASSPORT_PROMPT = """
You are an expert document analyzer. Extract ALL details from this Passport (Reisepass).
Return ONLY valid JSON.

Required Fields:
- full_name (Surname, Given Names)
- date_of_birth (DD.MM.YYYY)
- nationality (e.g., Deutsch, Syrisch, Afghanisch)
- passport_number
- sex (M/F/X)
- place_of_birth
- issue_date (DD.MM.YYYY)
- expiry_date (DD.MM.YYYY)
- issuing_authority

Text Snippet:
{text_snippet}
"""

EXTRACT_APPLICATION_FORM_PROMPT = """
You are a strict document validator for the German Immigration Office.
Analyze this "Antrag auf Verlängerung/Erteilung eines Aufenthaltstitels" (Application Form).

Your Task:
1. Extract the applicant's details.
2. CRITICALLY CHECK for missing mandatory information.

Mandatory Fields to Check:
- Surname (Familienname)
- First Name (Vorname)
- Date of Birth (Geburtsdatum)
- Nationality (Staatsangehörigkeit)
- Passport Number (Passnummer)
- Signature (Unterschrift) - Look for a signature line. If it looks empty or blank, report it.
- Date of Application (Ort, Datum)

Return ONLY valid JSON:
{{
  "full_name": "Extracted Name or null",
  "date_of_birth": "DD.MM.YYYY or null",
  "nationality": "Extracted Nationality or null",
  "passport_number": "Extracted Passport No or null",
  "address": "Extracted Address or null",
  "signature_present": true/false,
  "validation_issues": [
    "Surname is missing",
    "Signature field appears blank",
    "Passport number is missing",
    "Date of birth is invalid format"
  ]
}}

If everything is perfect, "validation_issues" should be an empty list [].
If a field is present but illegible, mark it as an issue.

Text Snippet:
{text_snippet}
"""

SUMMARIZE_TRANSLATE_PROMPT = """
Summarize this document in German. If it is not in German, provide a German translation of the key points.
Return ONLY valid JSON.
{{
  "summary_de": "...",
  "translation_de": "...",
  "confidence": 0.8
}}

Text Snippet:
{text_snippet}
"""

GENERATE_QUESTIONS_PROMPT = """
Based on the missing documents and flags, generate polite clarifying questions for the applicant in German.
Missing Docs: {missing_docs}
Flags: {flags}

Return ONLY valid JSON.
{{
  "questions": [
    {{
      "question": "...",
      "reason": "..."
    }}
  ]
}}
"""

CASE_NOTE_PROMPT = """
Write a short formal German case note (Aktennotiz) summarizing the intake check.
Mention present documents, missing documents, and any issues.
Do NOT make a decision.

Context:
{context_json}

Return ONLY valid JSON.
{{
  "aktennotiz": "..."
}}
"""
