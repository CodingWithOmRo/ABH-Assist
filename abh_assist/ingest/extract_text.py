import os
import io
from pypdf import PdfReader
from PIL import Image
import pytesseract

# Set tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_file(file_path):
    """
    Extracts text from PDF, Image, or Text files.
    Returns a string.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
            
    elif ext == ".pdf":
        text = ""
        try:
            reader = PdfReader(file_path)

            # 1. Extract Form Data (AcroForms)
            try:
                fields = reader.get_form_text_fields()
                if fields:
                    form_content = []
                    for k, v in fields.items():
                        if v: # Only include filled fields
                            form_content.append(f"{k}: {v}")
                    
                    if form_content:
                        text += "--- FORM DATA START ---\n"
                        text += "\n".join(form_content)
                        text += "\n--- FORM DATA END ---\n\n"
            except Exception as e:
                print(f"Form extraction warning: {e}")

            # 2. Extract Standard Text
            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text(extraction_mode="layout")
                if page_text:
                    text += f"\n--- PAGE {page_number} ---\n"
                    text += page_text + "\n"
                
            # 3. Fallback to OCR if text is too sparse (scanned PDF or image-only)
            if len(text.strip()) < 50:
                print(f"Text too sparse ({len(text.strip())} chars). Attempting OCR for {file_path}...")
                ocr_text = ""
                
                # Extract images directly from PDF (No Poppler required)
                try:
                    for page_number, page in enumerate(reader.pages, start=1):
                        for image_file in page.images:
                            try:
                                image_data = image_file.data
                                img = Image.open(io.BytesIO(image_data))
                                ocr_text += f"\n--- PAGE {page_number} OCR ---\n"
                                ocr_text += pytesseract.image_to_string(img, lang='deu+eng') + "\n"
                            except Exception as img_err:
                                print(f"Failed to process an image in PDF: {img_err}")
                except Exception as e:
                    print(f"OCR image extraction failed: {e}")
                
                if ocr_text.strip():
                    text += "\n--- OCR Extraction ---\n" + ocr_text
                    
        except Exception as e:
            return f"Error reading PDF: {e}"
            
        return text

    elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img, lang='deu+eng')
            return text
        except Exception as e:
            return f"Error reading Image: {e} (Ensure Tesseract is installed)"
            
    return ""
