#!/usr/bin/env python3
"""Comprehensive project diagnostic"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.getcwd())

print("\n" + "="*70)
print("🔍 PHOTOGRAMMETRY PROJECT DIAGNOSTIC REPORT")
print("="*70 + "\n")

issues = []
warnings = []
info = []

# 1. Check environment
print("1️⃣  ENVIRONMENT CHECK")
print("-" * 70)

try:
    import dotenv
    dotenv.load_dotenv()
    db_url = os.getenv('DATABASE_URL', 'NOT SET')
    redis_url = os.getenv('REDIS_URL', 'NOT SET')
    info.append(f"DATABASE_URL: {db_url[:50]}..." if len(db_url) > 50 else f"DATABASE_URL: {db_url}")
    info.append(f"REDIS_URL: {redis_url}")
    print(f"✅ .env file loaded")
except Exception as e:
    warnings.append(f"⚠️  Could not load .env: {str(e)}")

# 2. Check config
print("\n2️⃣  CONFIG CHECK")
print("-" * 70)

try:
    from backend.config import settings
    print(f"✅ Backend config loaded")
    info.append(f"API Version: {settings.API_V1_STR}")
    info.append(f"Project: {settings.PROJECT_NAME}")
except Exception as e:
    issues.append(f"❌ Backend config error: {str(e)}")

# 3. Check database models
print("\n3️⃣  DATABASE MODELS")
print("-" * 70)

try:
    from backend.models.models import Job, Stage
    from backend.core.db import Base, engine
    print(f"✅ Models imported: Job, Stage")
    print(f"✅ Database engine created")
    info.append(f"Database tables: {[table for table in Base.metadata.tables.keys()]}")
except Exception as e:
    issues.append(f"❌ Database models error: {str(e)}")

# 4. Check API routers
print("\n4️⃣  API ROUTERS")
print("-" * 70)

try:
    from backend.api import upload, scans, worker_api
    print(f"✅ Upload router: {upload.router}")
    print(f"✅ Scans router: {scans.router}")
    print(f"✅ Worker API router: {worker_api.router}")
except Exception as e:
    issues.append(f"❌ API routers error: {str(e)}")

# 5. Check worker/pipeline
print("\n5️⃣  WORKER PIPELINE")
print("-" * 70)

try:
    from worker.pipeline import tasks
    print(f"✅ Worker pipeline tasks module found")
    
    # List available tasks
    task_funcs = [name for name in dir(tasks) if callable(getattr(tasks, name)) and not name.startswith('_')]
    info.append(f"Available tasks: {task_funcs[:5]}...")
except Exception as e:
    warnings.append(f"⚠️  Worker pipeline: {str(e)}")

# 6. Check storage
print("\n6️⃣  STORAGE")
print("-" * 70)

try:
    from storage.factory import get_storage_provider
    print(f"✅ Storage factory found")
    storage_type = os.getenv('STORAGE_TYPE', 'cloudinary')
    info.append(f"Storage type: {storage_type}")
except Exception as e:
    warnings.append(f"⚠️  Storage: {str(e)}")

# 7. Check shared schemas
print("\n7️⃣  SHARED SCHEMAS")
print("-" * 70)

try:
    from shared.schemas import JobStatus, JobStage, JobStatusResponse
    print(f"✅ Shared schemas loaded")
    
    stages = [stage.name for stage in JobStage]
    info.append(f"Job stages: {stages}")
except Exception as e:
    issues.append(f"❌ Shared schemas: {str(e)}")

# 8. Check test files
print("\n8️⃣  TEST FILES")
print("-" * 70)

test_dir = Path("tests")
if test_dir.exists():
    test_files = list(test_dir.glob("*.py"))
    info.append(f"Test files found: {[f.name for f in test_files]}")
    print(f"✅ Tests directory found with {len(test_files)} files")
else:
    warnings.append(f"⚠️  Tests directory not found")

# 9. Check dependencies
print("\n9️⃣  DEPENDENCIES")
print("-" * 70)

critical_packages = ['fastapi', 'redis', 'sqlalchemy', 'numpy', 'opencv-python-headless', 'torch']
missing = []

for pkg in critical_packages:
    try:
        __import__(pkg.replace('-', '_'))
        print(f"✅ {pkg}")
    except ImportError:
        missing.append(pkg)
        print(f"❌ {pkg} - NOT INSTALLED")

if missing:
    issues.append(f"Missing packages: {missing}")

# 10. Backend main check
print("\n🔟 BACKEND MAIN")
print("-" * 70)

try:
    from backend.main import app
    print(f"✅ Backend FastAPI app created")
    # Check routes
    routes = [route.path for route in app.routes]
    info.append(f"API routes: {len(routes)} registered")
except Exception as e:
    issues.append(f"❌ Backend main: {str(e)}")

# Summary
print("\n" + "="*70)
print("📊 DIAGNOSTIC SUMMARY")
print("="*70)

print(f"\n✅ INFO ({len(info)} items):")
for item in info:
    print(f"   {item}")

if warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)} items):")
    for item in warnings:
        print(f"   {item}")

if issues:
    print(f"\n❌ ISSUES ({len(issues)} critical):")
    for item in issues:
        print(f"   {item}")
    print("\n⚠️  Project has CRITICAL issues that need attention!")
    sys.exit(1)
else:
    print(f"\n✅ NO CRITICAL ISSUES FOUND!")
    print("\n✅ The project appears to be properly configured and ready for testing.")
    sys.exit(0)
