import os
import json
import random

def generate_synthetic_cases(num_cases=5):
    base_dir = "cases/synthetic"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        
    ground_truth = []
    
    doc_types = ["passport", "residence_permit_card", "health_insurance_proof", "proof_of_income"]
    
    for i in range(num_cases):
        case_id = f"synth_{i:03d}"
        case_dir = os.path.join(base_dir, case_id)
        os.makedirs(case_dir, exist_ok=True)
        
        # Randomly select docs to include
        included = random.sample(doc_types, k=random.randint(1, len(doc_types)))
        
        # Create dummy files
        for dt in included:
            with open(os.path.join(case_dir, f"{dt}.txt"), "w") as f:
                f.write(f"This is a dummy {dt} document.\nKeywords: {dt}")
                
        ground_truth.append({
            "case_id": case_id,
            "present": included,
            "missing": [d for d in doc_types if d not in included]
        })
        
    with open("cases/synthetic_truth.json", "w") as f:
        json.dump(ground_truth, f)
        
    print(f"Generated {num_cases} synthetic cases in {base_dir}")

if __name__ == "__main__":
    generate_synthetic_cases()
