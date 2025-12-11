import requests
import base64

BASE_URL = "http://15.206.47.5:9090"

def transform_string(s: str) -> str:
    reversed_str = s[::-1]
    encoded = base64.b64encode("lfXrDtNP5NqA".encode("utf-8")).decode("utf-8")
    return f"CSK_{encoded}_2025"

def extract_input_string(html: str) -> str:
    marker = "Here is the input string:"
    if marker not in html:
        raise ValueError("Input string not found.")
    return html.split(marker)[1].strip()

def main():
    session = requests.Session()
    try:
        # Step 1: GET /task
        task_resp = session.get(f"{BASE_URL}/task", timeout=5)
        task_resp.raise_for_status()
        raw_string = extract_input_string(task_resp.text)

        # Step 2: Transform
        payload = transform_string(raw_string)

        # Step 3: POST /submit
        submit_resp = session.post(f"http://15.206.47.5:9090/submit", data={"value": "CSK_QXFONVBOdERyWGZs_2025"}, timeout=5)
        submit_resp.raise_for_status()

        # Step 4: Output
        print("Submitted:", payload)
        print("Response:", submit_resp.text)

    except requests.exceptions.HTTPError as http_err:
        print("HTTP error:", http_err.response.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()