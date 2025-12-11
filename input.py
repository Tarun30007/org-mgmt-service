import requests
import base64
import re
from bs4 import BeautifulSoup

BASE = "http://15.206.47.5:9090"
TASK = f"{BASE}/task"
SUBMIT = f"{BASE}/submit"

# Adjust these if the endpoint expects a specific field name or raw body
ANSWER_FIELD = "answer"  # Try "answer" first; if rejected, try raw text body

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (automation)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
})

def extract_string(html: str) -> str:
    # Try simple regex first for speed
    m = re.search(r'>([A-Za-z0-9+/=._-]{6,})<', html)
    if m:
        return m.group(1)

    # Fallback: parse any visible code/snippet tags
    soup = BeautifulSoup(html, "html.parser")

    # Common places for the prompt string
    for sel in ["code", "pre", "span", "div", "p"]:
        for el in soup.select(sel):
            text = el.get_text(strip=True)
            if text and re.fullmatch(r'[A-Za-z0-9+/=._-]{6,}', text):
                return text

    # Last resort: pick longest token-ish word
    tokens = re.findall(r'[A-Za-z0-9+/=._-]+', html)
    return max(tokens, key=len) if tokens else ""

def transform(s: str) -> str:
    rev = s[::-1]
    b64 = base64.b64encode(rev.encode()).decode()
    return f"CSK__{b64}__2025"

def submit_payload(payload: str):
    # Try form field first (tip mentioned raw text or form fields)
    resp = session.post(SUBMIT, data={ANSWER_FIELD: payload}, timeout=3)
    if resp.status_code == 200 and "flag" in resp.text.lower():
        return resp.text

    # Fallback: send raw text body
    resp2 = session.post(SUBMIT, data=payload, headers={"Content-Type": "text/plain"}, timeout=3)
    return resp2.text

def run_once():
    r = session.get(TASK, timeout=3)
    r.raise_for_status()
    s = extract_string(r.text)
    if not s:
        raise ValueError("Could not extract task string.")
    payload = transform(s)
    return submit_payload(payload)

if __name__ == "__main__":
    # Tight loop to beat the per-session timer
    for _ in range(20):
        try:
            result = run_once()
            print(result)
            if "flag" in result.lower():
                break
        except Exception as e:
            # Minimal logging to keep speed
            pass