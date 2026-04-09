import os
import modal

app = modal.App("check-env")
secret = modal.Secret.from_name("photogrammetry-env")

@app.function(secrets=[secret])
def check():
    print("=== MODAL ENV ===")
    for k, v in os.environ.items():
        if any(x in k.upper() for x in ["STORAGE", "CLOUDINARY", "MODAL"]):
            # Mask sensitive values slightly but show enough to verify
            if "SECRET" in k or "KEY" in k:
                print(f"{k}: {v[:4]}...{v[-4:] if len(v)>8 else ''}")
            else:
                print(f"{k}: {v}")

if __name__ == "__main__":
    with modal.enable_output():
        with app.run():
            check.remote()
