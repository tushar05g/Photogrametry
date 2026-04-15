#!/usr/bin/env python3
"""Test all major imports and identify issues"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

issues = []
passing = []

def test_import(module_name, description):
    """Test if a module can be imported"""
    try:
        __import__(module_name)
        passing.append(f"✅ {description}: {module_name}")
        return True
    except Exception as e:
        issues.append(f"❌ {description}: {module_name}")
        issues.append(f"   Error: {str(e)}")
        return False

print("🧪 Testing imports...\n")

# Test core dependencies
test_import("fastapi", "FastAPI")
test_import("redis", "Redis")
test_import("sqlalchemy", "SQLAlchemy")
test_import("celery", "Celery")
test_import("numpy", "NumPy")
test_import("cv2", "OpenCV")
test_import("PIL", "Pillow")
test_import("scipy", "SciPy")

# Test backend modules (with proper path)
test_import("backend.config", "Backend Config")
test_import("backend.core.db", "Backend DB")

# Print results
print("\n" + "="*60)
print(f"PASSING ({len(passing)}):")
print("="*60)
for item in passing:
    print(item)

print("\n" + "="*60)
print(f"ISSUES ({len(issues)//2 if issues else 0}):")
print("="*60)
if issues:
    for item in issues:
        print(item)
else:
    print("✅ No import issues found!")

sys.exit(0 if not issues else 1)
