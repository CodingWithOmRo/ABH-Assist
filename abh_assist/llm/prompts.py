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

EXTRACT_TIMELINE_EVENTS_PROMPT = """
Du bist ein sehr gruendlicher Assistent fuer eine deutsche Auslaenderbehoerde.

Ziel der Aktenauswertung:
{goal}

Aufgabe:
Lies den folgenden Auszug aus einer digitalen Akte und extrahiere ALLE datierten
Eintraege, Entscheidungen, Schreiben, Dokumente und Ereignisse, die fuer dieses
Ziel dienlich sein koennen.

Wichtige Arbeitsregel:
- Verwende AUSSCHLIESSLICH Informationen aus DIESEM Textauszug.
- Verwende KEINE Informationen aus frueheren Dokumenten, frueheren Runs oder allgemeinem Fachwissen.
- Das Analyseziel beeinflusst nur die Frage der Dienlichkeit, NICHT die Tatsachenbeschreibung.
- Erfinde keine Ereignisse, keine Verfahrensschritte und keine Datumsangaben.
- Wenn ein Jahr oder Datum im Auszug nicht belegt ist, gib es nicht aus.
- Jede Ausgabe braucht eine kurze, exakt aus dem Auszug uebernommene Fundstelle in "evidence_snippet".
- Wenn du keine kurze exakte Fundstelle zitieren kannst, gib den Eintrag NICHT aus.
- Nichts Relevantes soll fehlen. Nimm im Zweifel einen Eintrag auf.
- Lieber zu viele Eintraege als zu wenige.
- Auch mittelbar relevante Daten aufnehmen, z.B. Aufenthaltstitel, Duldungen,
  Straftaten, Urteile, Haft, Entlassung, Ausreiseaufforderungen, Abschiebung,
  Identitaetsklaerung, Passbeschaffung, Fristen, Mitwirkung, Adresse,
  Familienstand, Erwerbstaetigkeit, Sozialleistungen, Krankheit, Schriftverkehr.
- Trenne historische Ereignisse im Herkunftsland von Verwaltungsvorgaengen in Deutschland.
- Keine rechtliche Entscheidung treffen.
- Jede Aufnahme braucht eine Datumsangabe. Wenn nur Monat/Jahr oder Jahr genannt
  ist, nutze diese Angabe und setze die passende date_precision.
- Wenn ein relevanter undatierter Eintrag direkt zu einem datierten Dokument
  gehoert, verwende das Dokumentdatum und erklaere dies in "date_basis".
- Zitiere nur kurze Fundstellen wortnah aus dem Auszug.

Dokument: {filename}
Dokumenttyp: {doc_type}
Auszug: {chunk_number}/{total_chunks}
Seitenbereich: {page_scope}

Textauszug:
{text_snippet}

Return ONLY valid JSON:
{{
  "entries": [
    {{
      "date": "DD.MM.YYYY, MM.YYYY, YYYY or null",
      "date_precision": "day|month|year|unknown",
      "date_basis": "Ereignisdatum, Dokumentdatum, Fristdatum, inferred_from_document_date, or unknown",
      "event": "Kurzer deutscher Satz: Was ist passiert?",
      "relevance": "Warum kann dies fuer das Ziel dienlich sein?",
      "category": "Asylverfahren|Herkunft/Flucht|Aufenthalt|Duldung|Straftat|Urteil|Haft|Ausreise|Abschiebung|Identitaet|Mitwirkung|Familie|Gesundheit|Arbeit|Sozialleistungen|Kommunikation|Frist|Sonstiges",
      "event_scope": "historical_origin|germany_administrative|germany_judicial|personal_context|unclear",
      "source_document": "{filename}",
      "source_page_or_section": "Seite/Abschnitt/Fundstelle falls erkennbar, sonst null",
      "evidence_snippet": "Kurzes EXAKTES Zitat aus dem Auszug",
      "confidence": 0.0
    }}
  ]
}}
"""

TIMELINE_CASE_NOTE_PROMPT = """
Schreibe eine formale deutsche Aktennotiz fuer eine zielbezogene Aktenauswertung.

Ziel:
{goal}

Chronologische Eintraege:
{timeline_json}

Zusammenfassung der Auswertung:
{timeline_summary_json}

Hinweise zur Abdeckung:
{coverage_notes_json}

Anforderungen:
- Keine rechtliche Entscheidung treffen.
- Kurz festhalten, dass die Liste bewusst weit gefasst ist, damit nichts fehlt.
- Die wichtigsten Linien der Chronologie zusammenfassen.
- Offene Pruefpunkte oder unsichere Fundstellen benennen, falls vorhanden.

Return ONLY valid JSON:
{{
  "aktennotiz": "..."
}}
"""
