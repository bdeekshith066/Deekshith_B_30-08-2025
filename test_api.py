# test_api.py
# Simple integration test for the API workflow.
# 1) Calls /trigger_report and retrieves a new report_id.
# 2) Polls /get_report until the job completes, then saves the CSV output.
# Validates the trigger + poll architecture end-to-end against a running server.

import time
import requests

BASE = "http://127.0.0.1:8000"

def main():
    # 1) trigger
    r = requests.post(f"{BASE}/trigger_report", timeout=30)
    r.raise_for_status()
    report_id = r.json()["report_id"]
    print("report_id:", report_id)

    # 2) poll until complete (max ~5 minutes)
    for _ in range(300):  # 300 * 1s = 5 min
        res = requests.get(f"{BASE}/get_report", params={"report_id": report_id}, timeout=60)
        # If still running, the endpoint returns plain text "Running"
        if res.headers.get("content-type", "").startswith("text/plain"):
            status = res.text.strip()
            print("status:", status)
            if status != "Running":
                print("Unexpected status:", status)
                return
            time.sleep(1)
            continue

        # Otherwise it's the CSV
        if res.headers.get("content-type", "").startswith("text/csv"):
            out = f"report_{report_id}.csv"
            with open(out, "wb") as f:
                f.write(res.content)
            print("✅ CSV saved as", out)
            return

        print("Unexpected response:", res.status_code, res.headers.get("content-type"))
        print(res.text[:200])
        return

    print("Timed out waiting for report.")

if __name__ == "__main__":
    main()
