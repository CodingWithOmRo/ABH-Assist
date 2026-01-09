import os
import sys

# Add the project root to the python path so we can import from abh_assist
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from abh_assist.ingest.extract_text import extract_text_from_file

# Path to the file we want to test
# Using the one found in your workspace
pdf_path = r"cases\case_temp\Antrag_Verlaengerungg.pdf"

if not os.path.exists(pdf_path):
    print(f"File not found: {pdf_path}")
    # Try to find any pdf
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                print(f"Found alternative PDF: {pdf_path}")
                break
        if pdf_path != r"cases\case_temp\Antrag_Verlaengerungg.pdf":
            break

print(f"--- Testing extraction on: {pdf_path} ---")

try:
    text = extract_text_from_file(pdf_path)
    
    print("\n--- EXTRACTION RESULT (First 1000 chars) ---\n")
    print(text[:1000])
    print("\n--- END OF PREVIEW ---\n")
    
    if "FORM DATA START" in text:
        print("\nSUCCESS: Form data was detected!")
    else:
        print("\nWARNING: No 'FORM DATA' section found. This might not be a fillable form, or the fields are empty.")

except Exception as e:
    print(f"\nERROR during extraction: {e}")
