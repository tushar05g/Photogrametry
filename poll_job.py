import requests
import time
import sys

job_id = "58fcd391-8e6c-45f1-8c03-8dc6633daa60"
url = f"http://localhost:8000/api/v1/scans/{job_id}/progress"

print(f"Polling {url}...")
# Poll every 10 seconds for up to 10 minutes
for _ in range(60):
    try:
        resp = requests.get(url)
        data = resp.json()
        print(f"[{data.get('current_stage')}] - {data.get('progress')}")
        if data.get('status') in ['completed', 'failed']:
            import json
            print(json.dumps(data, indent=2))
            sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(10)
print("Timeout waiting for job")
sys.exit(1)
