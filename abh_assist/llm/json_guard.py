import json

def validate_and_fix_json(response_text):
    """
    Attempts to parse JSON. If fails, could implement a retry loop with the LLM.
    For this PoC, we try to find the first { and last }.
    """
    try:
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end != -1:
            return json.loads(response_text[start:end])
    except:
        pass
    return None
