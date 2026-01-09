import json
from abh_assist.llm.client import run_llm
from abh_assist.llm.prompts import CASE_NOTE_PROMPT, GENERATE_QUESTIONS_PROMPT
from abh_assist.llm.json_guard import validate_and_fix_json

def generate_final_report(case_data):
    """
    Aggregates all analysis and asks LLM for final questions and note.
    """
    
    # 1. Generate Questions
    q_prompt = GENERATE_QUESTIONS_PROMPT.format(
        missing_docs=json.dumps(case_data.get('missing_documents', [])),
        flags=json.dumps(case_data.get('flags', []))
    )
    q_resp = run_llm(q_prompt)
    q_json = validate_and_fix_json(q_resp)
    if q_json:
        case_data['questions_for_applicant'] = q_json.get('questions', [])
        
    # 2. Generate Case Note
    # Minimize context to fit in context window
    mini_context = {
        "case_type": case_data.get("case_type"),
        "present_docs": [d['doc_type'] for d in case_data.get('documents', [])],
        "missing_docs": [d['doc_type'] for d in case_data.get('missing_documents', [])],
        "flags": [f['code'] for f in case_data.get('flags', [])]
    }
    
    n_prompt = CASE_NOTE_PROMPT.format(context_json=json.dumps(mini_context))
    n_resp = run_llm(n_prompt)
    n_json = validate_and_fix_json(n_resp)
    if n_json:
        case_data['aktennotiz_de'] = n_json.get('aktennotiz', "")
        
    return case_data
