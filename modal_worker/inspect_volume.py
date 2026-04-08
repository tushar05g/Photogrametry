import modal
import os

app = modal.App(name="photogrammetry-worker-debug")
# Use the same image and volume as the main worker
volume = modal.Volume.from_name("morphic-scan-data")
image = modal.Image.from_registry("colmap/colmap:latest", add_python="3.10")

@app.function(image=image, volumes={"/mnt/data": volume})
def list_path(path: str):
    import subprocess
    try:
        res = subprocess.run(["ls", "-R", f"/mnt/data/{path}"], capture_output=True, text=True)
        return res.stdout + res.stderr
    except Exception as e:
        return str(e)

@app.function(image=image, volumes={"/mnt/data": volume})
def cat_file(path: str):
    try:
        with open(f"/mnt/data/{path}", "rb") as f:
            return f.read(1024) # just first kb
    except Exception as e:
        return str(e).encode()

@app.local_entrypoint()
def main(path: str):
    print(f"--- LISTING {path} ---")
    print(list_path.remote(path))
