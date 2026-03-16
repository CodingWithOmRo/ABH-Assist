import json
import os

def save_report(case_id, report_data):
    # Save in the case folder
    case_dir = os.path.join("cases", case_id)
    if not os.path.exists(case_dir):
        os.makedirs(case_dir)
    
    # Also create outputs dir for legacy support
    output_dir = "outputs"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Save JSON in case folder
    json_path = os.path.join(case_dir, f"case_{case_id}_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    # Also save copy in outputs for backward compatibility
    json_path_output = os.path.join(output_dir, f"{case_id}_report.json")
    with open(json_path_output, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
        
    # Save Text Note in case folder
    txt_path = os.path.join(case_dir, f"case_{case_id}_note.txt")
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
    
    # Also save copy in outputs
    txt_path_output = os.path.join(output_dir, f"{case_id}_note.txt")
    with open(txt_path_output, "w", encoding="utf-8") as f:
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
    return json_path, txt_path
