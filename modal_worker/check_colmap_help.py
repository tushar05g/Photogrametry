import modal

# Use the existing app image and secret
app = modal.App(name="photogrammetry-worker-debug")
image = modal.Image.from_registry("colmap/colmap:latest", add_python="3.10")

@app.function(image=image)
def check_colmap_help(command: str):
    import subprocess
    try:
        # COLMAP help usually returns non-zero exit code sometimes or prints to stderr
        res = subprocess.run(["colmap", command, "-h"], capture_output=True, text=True)
        return res.stdout + res.stderr
    except Exception as e:
        return str(e)

@app.local_entrypoint()
def main():
    print("--- EXHAUSTIVE MATCHER HELP ---")
    print(check_colmap_help.remote("exhaustive_matcher"))
    print("\n--- FEATURE EXTRACTOR HELP ---")
    print(check_colmap_help.remote("feature_extractor"))
