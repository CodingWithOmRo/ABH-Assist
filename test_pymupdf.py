import sys
try:
    import pymupdf
    print(f"PyMuPDF version: {pymupdf.__version__}")
    doc = pymupdf.open()
    print("pymupdf.open() exists")
except ImportError as e:
    print(f"ImportError: {e}")
except AttributeError as e:
    print(f"AttributeError: {e}")
except Exception as e:
    print(f"Error: {e}")
