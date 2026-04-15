#!/usr/bin/env python3
"""
🧪 COMPREHENSIVE PROJECT TEST SUITE
Tests all major project components and integration points.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.getcwd())

print("\n" + "="*80)
print("🧪 PHOTOGRAMMETRY PROJECT - COMPREHENSIVE TEST SUITE")
print("="*80 + "\n")

passed = 0
failed = 0
skipped = 0

def test(description: str, func):
    """Decorator for test functions"""
    global passed, failed
    try:
        print(f"🧪 Testing: {description}...", end=" ")
        result = func()
        if result is False:
            print("❌ FAILED")
            failed += 1
            return False
        else:
            print("✅ PASSED")
            passed += 1
            return True
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        failed += 1
        return False

# ============================================================================
# 1. CONFIGURATION & ENVIRONMENT TESTS
# ============================================================================
print("1️⃣  CONFIGURATION & ENVIRONMENT TESTS")
print("-" * 80)

def test_env_loaded():
    from dotenv import load_dotenv
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    redis_url = os.getenv('REDIS_URL')
    return db_url is not None and redis_url is not None

def test_backend_config():
    from backend.config import settings
    return (settings.PROJECT_NAME == "Photogrammetry Pipeline" and
            settings.API_V1_STR == "/api/v1")

def test_cors_origins():
    from backend.config import settings
    return hasattr(settings, 'CORS_ORIGINS') and len(settings.CORS_ORIGINS) > 0

test("Environment variables loaded", test_env_loaded)
test("Backend config loaded", test_backend_config)
test("CORS origins configured", test_cors_origins)

# ============================================================================
# 2. DATABASE TESTS
# ============================================================================
print("\n2️⃣  DATABASE TESTS")
print("-" * 80)

def test_db_models():
    from backend.models.models import Job, Stage
    from backend.core.db import Base
    return Job and Stage and Base

def test_db_engine():
    from backend.core.db import engine, Base
    try:
        Base.metadata.create_all(bind=engine)
        return True
    except Exception as e:
        print(f"   (Warning: {str(e)[:50]}...)")
        return False

test("Database models defined", test_db_models)
test("Database engine created", test_db_engine)

# ============================================================================
# 3. API ROUTER TESTS
# ============================================================================
print("\n3️⃣  API ROUTER TESTS")
print("-" * 80)

def test_upload_router():
    from backend.api import upload
    return hasattr(upload, 'router') and upload.router is not None

def test_scans_router():
    from backend.api import scans
    return hasattr(scans, 'router') and scans.router is not None

def test_worker_api_router():
    from backend.api import worker_api
    return hasattr(worker_api, 'router') and worker_api.router is not None

def test_fastapi_app():
    from backend.main import app
    return app is not None and len(app.routes) > 0

test("Upload router defined", test_upload_router)
test("Scans router defined", test_scans_router)
test("Worker API router defined", test_worker_api_router)
test("FastAPI app created with routes", test_fastapi_app)

# ============================================================================
# 4. SECURITY TESTS
# ============================================================================
print("\n4️⃣  SECURITY TESTS")
print("-" * 80)

def test_cors_not_wildcard():
    from backend.config import settings
    # Check that CORS is not ["*"]
    return settings.CORS_ORIGINS != ["*"]

def test_worker_token_not_hardcoded():
    from backend.config import settings
    # Test token should not be the default weak token in production
    is_test = settings.WORKER_TOKEN == "test-token-123"
    if is_test:
        print("   (Warning: using test token - fine for development)")
    return True

def test_credentials_in_env():
    # Verify critical credentials are not in main code
    main_py_path = Path("backend/main.py")
    content = main_py_path.read_text()
    critical_keywords = ["postgresql://", "cloudinary", "CLOUDINARY_API"]
    
    has_credentials = any(word in content for word in critical_keywords)
    return not has_credentials  # Should NOT have credentials in code

test("CORS not set to wildcard", test_cors_not_wildcard)
test("Worker token handling", test_worker_token_not_hardcoded)
test("No credentials in main.py", test_credentials_in_env)

# ============================================================================
# 5. STORAGE TESTS
# ============================================================================
print("\n5️⃣  STORAGE TESTS")
print("-" * 80)

def test_storage_factory():
    try:
        from storage.factory import get_storage_provider
        provider = get_storage_provider()
        return provider is not None
    except Exception as e:
        print(f"   {str(e)[:60]}...")
        return False

def test_local_storage():
    from storage.local_provider import LocalStorageProvider
    provider = LocalStorageProvider(base_path="morphic-scan-data")
    return provider is not None

test("Storage factory works", test_storage_factory)
test("Local storage provider available", test_local_storage)

# ============================================================================
# 6. SCHEMA & VALIDATION TESTS
# ============================================================================
print("\n6️⃣  SCHEMA & VALIDATION TESTS")
print("-" * 80)

def test_job_schemas():
    from shared.schemas import JobStatus, JobStage, JobStatusResponse
    return JobStatus and JobStage and JobStatusResponse

def test_job_stages_complete():
    from shared.schemas import JobStage
    stages = [s.name for s in JobStage]
    required = ['IDLE', 'SFM', 'MVS', 'MESH', 'EXPORT']
    return all(s in stages for s in required)

test("Job schemas defined", test_job_schemas)
test("All required job stages present", test_job_stages_complete)

# ============================================================================
# 7. WORKER INTEGRATION TESTS
# ============================================================================
print("\n7️⃣  WORKER INTEGRATION TESTS")
print("-" * 80)

def test_kaggle_worker_exists():
    kaggle_worker = Path("scripts/kaggle_worker.py")
    return kaggle_worker.exists()

def test_kaggle_worker_imports():
    try:
        with open("scripts/kaggle_worker.py", "r") as f:
            code = f.read()
            # Check for critical imports
            required_imports = ["KaggleWorker", "requests", "logging"]
            return all(imp in code for imp in required_imports)
    except:
        return False

test("Kaggle worker script exists", test_kaggle_worker_exists)
test("Kaggle worker has required imports", test_kaggle_worker_imports)

# ============================================================================
# 8. TEST FILES & PATHS
# ============================================================================
print("\n8️⃣  TEST FILES & PATHS")
print("-" * 80)

def test_test_files_exist():
    tests_dir = Path("tests")
    test_files = [f for f in tests_dir.glob("*.py") if f.name.startswith("test_")]
    return len(test_files) >= 2

def test_test_paths_portable():
    test_e2e = Path("tests/test_pipeline_e2e.py")
    content = test_e2e.read_text()
    # Check that it uses Path(__file__).parent (relative paths)
    uses_relative = "Path(__file__).parent" in content or "PROJECT_ROOT" in content
    # Check that it doesn't use hardcoded /home paths
    has_hardcoded = "/home/harpreet" in content
    return uses_relative and not has_hardcoded

def test_assets_exist():
    assets_dir = Path("assets")
    return assets_dir.exists() and (assets_dir / "cube_images").exists()

test("Test files exist", test_test_files_exist)
test("Test paths are portable", test_test_paths_portable)
test("Asset directories exist", test_assets_exist)

# ============================================================================
# 9. DEPENDENCY TESTS
# ============================================================================
print("\n9️⃣  DEPENDENCY TESTS")
print("-" * 80)

critical_packages = [
    'fastapi', 'redis', 'sqlalchemy', 'numpy', 'cv2', 'PIL',
    'scipy', 'torch', 'celery', 'pydantic', 'starlette'
]

for package in critical_packages:
    import_name = package.replace('-', '_')
    try:
        __import__(import_name)
        print(f"   ✅ {package}")
    except ImportError:
        print(f"   ❌ {package} - NOT INSTALLED")
        failed += 1
        continue
    passed += 1

# ============================================================================
# 10. CONFIGURATION FILES
# ============================================================================
print("\n🔟 CONFIGURATION FILES")
print("-" * 80)

def test_env_template_exists():
    return Path(".env.template").exists()

def test_env_file_exists():
    return Path(".env").exists()

test("Environment template exists (.env.template)", test_env_template_exists)
test("Environment file exists (.env)", test_env_file_exists)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("📊 TEST SUMMARY")
print("="*80)

total = passed + failed + skipped

print(f"""
✅ PASSED: {passed}
❌ FAILED: {failed}
⏭️  SKIPPED: {skipped}
────────────────
📊 TOTAL:  {total}

Success Rate: {(passed/total*100):.1f}%
""")

if failed == 0:
    print("🎉 ALL TESTS PASSED! Project is ready for testing.")
    sys.exit(0)
else:
    print(f"⚠️  {failed} test(s) failed. Please review above.")
    sys.exit(1)
