import os
from pypdf import PdfReader
from PIL import Image
import pytesseract

try:
    import fitz
except ImportError:
    fitz = None

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
        try:
            text = _extract_pdf_text_with_pypdf(file_path)
            if len(text.strip()) < 50:
                print(f"Text too sparse ({len(text.strip())} chars). Attempting rendered OCR for {file_path}...")
                ocr_text = _ocr_pdf_with_pymupdf(file_path)
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


def _extract_pdf_text_with_pypdf(file_path):
    text = ""
    reader = PdfReader(file_path)

    try:
        fields = reader.get_form_text_fields()
        if fields:
            form_content = []
            for key, value in fields.items():
                if value:
                    form_content.append(f"{key}: {value}")

            if form_content:
                text += "--- FORM DATA START ---\n"
                text += "\n".join(form_content)
                text += "\n--- FORM DATA END ---\n\n"
    except Exception as exc:
        print(f"Form extraction warning: {exc}")

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text(extraction_mode="layout")
        except Exception as exc:
            print(f"Page text extraction warning on page {page_number}: {exc}")
            page_text = ""
        if page_text:
            text += f"\n--- PAGE {page_number} ---\n"
            text += page_text + "\n"

    return text


def _ocr_pdf_with_pymupdf(file_path):
    if fitz is None:
        print("Rendered OCR unavailable: PyMuPDF not installed.")
        return ""

    ocr_text = ""
    try:
        document = fitz.open(file_path)
        for page_number in range(document.page_count):
            page = document.load_page(page_number)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            page_text = pytesseract.image_to_string(image, lang="deu+eng")
            if page_text.strip():
                ocr_text += f"\n--- PAGE {page_number + 1} OCR ---\n"
                ocr_text += page_text + "\n"
    except Exception as exc:
        print(f"Rendered OCR failed: {exc}")
    return ocr_text
