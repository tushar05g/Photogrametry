import modal
from pathlib import Path

volume = modal.Volume.from_name("morphic-scan-data")
job_id = "52ad6098-7b8d-49a0-a89c-1760f44a2c34"

print(f"Files in jobs/{job_id}/output/sparse/:")
for entry in volume.listdir(f"jobs/{job_id}/output/sparse/", recursive=True):
    print(entry.path)
