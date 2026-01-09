from langdetect import detect, LangDetectException

def detect_language(text):
    try:
        if not text or len(text.strip()) < 10:
            return "unknown"
        return detect(text)
    except LangDetectException:
        return "unknown"
