import json
import os

OUTPUT_DIR = "outputs"

def save_report(case_id, report_data):
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    # Save JSON
    json_path = os.path.join(OUTPUT_DIR, f"{case_id}_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
        
    # Save Text Note
    txt_path = os.path.join(OUTPUT_DIR, f"{case_id}_note.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Fall: {case_id}\n")
        f.write(f"Typ: {report_data.get('case_type')}\n\n")
        f.write("AKTENNOTIZ:\n")
        
        note = report_data.get('aktennotiz_de', '')
        if isinstance(note, dict):
            note = json.dumps(note, ensure_ascii=False)
        f.write(str(note))
        
        f.write("\n\nFRAGEN AN ANTRAGSTELLER:\n")
        for q in report_data.get('questions_for_applicant', []):
            f.write(f"- {q.get('question')} ({q.get('reason')})\n")
            
    return json_path, txt_path
