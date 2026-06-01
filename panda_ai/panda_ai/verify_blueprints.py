#!/usr/bin/env python3
"""
Verification script for Panda AI V8.6 blueprint handlers.
Run this on Hugging Face Spaces to diagnose import issues.

Usage:
    python3 verify_blueprints.py
"""

import os
import sys

print("=" * 70)
print(" 🔍 PANDA AI V8.6 - BLUEPRINT HANDLER VERIFICATION")
print("=" * 70)
print()

# Get current working directory
cwd = os.getcwd()
print(f"📁 Working Directory: {cwd}")
print(f"📁 Python Path: {sys.executable}")
print()

# Step 1: Check file existence
print("─" * 70)
print("STEP 1: FILE EXISTENCE CHECK")
print("─" * 70)

files = [
    'orator_handler.py',
    'maps_handler.py',
    'charts_handler.py',
    'canvas_handler.py',
    'app.py',
    'modules/mail/mail_routes.py',
    'modules/pad/pad_routes.py',
    'modules/study/study_routes.py',
]

missing_files = []
for f in files:
    if os.path.exists(f):
        size = os.path.getsize(f)
        print(f"✅ {f:45} ({size:6} bytes)")
    else:
        print(f"❌ {f:45} NOT FOUND")
        missing_files.append(f)

if missing_files:
    print()
    print(f"⚠️  {len(missing_files)} file(s) missing!")
    sys.exit(1)

print()

# Step 2: Check Python syntax
print("─" * 70)
print("STEP 2: PYTHON SYNTAX CHECK")
print("─" * 70)

import py_compile
syntax_errors = []

handler_files = [
    'orator_handler.py',
    'maps_handler.py',
    'charts_handler.py',
    'canvas_handler.py',
]

for f in handler_files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"✅ {f:45} syntax valid")
    except py_compile.PyCompileError as e:
        print(f"❌ {f:45} syntax error!")
        print(f"   {e}")
        syntax_errors.append(f)

if syntax_errors:
    print()
    print(f"⚠️  {len(syntax_errors)} file(s) have syntax errors!")
    sys.exit(1)

print()

# Step 3: Test imports
print("─" * 70)
print("STEP 3: BLUEPRINT IMPORT TEST")
print("─" * 70)

import_errors = []

handlers = [
    ('orator_handler', 'orator_bp'),
    ('maps_handler', 'maps_bp'),
    ('charts_handler', 'charts_bp'),
    ('canvas_handler', 'canvas_bp'),
]

for module_name, bp_name in handlers:
    try:
        module = __import__(module_name)
        if hasattr(module, bp_name):
            bp = getattr(module, bp_name)
            print(f"✅ from {module_name:20} import {bp_name:15} → {bp}")
        else:
            print(f"❌ {module_name:20}.{bp_name} does not exist")
            print(f"   Available: {[x for x in dir(module) if 'bp' in x.lower()]}")
            import_errors.append(f"{module_name}.{bp_name}")
    except Exception as e:
        print(f"❌ {module_name:20} import failed: {type(e).__name__}: {e}")
        import_errors.append(module_name)

if import_errors:
    print()
    print(f"⚠️  {len(import_errors)} import(s) failed!")
    sys.exit(1)

print()

# Step 4: Test module imports
print("─" * 70)
print("STEP 4: MODULE BLUEPRINT IMPORT TEST")
print("─" * 70)

modules = [
    ('modules.mail.mail_routes', 'mail_bp'),
    ('modules.pad.pad_routes', 'pad_bp'),
    ('modules.study.study_routes', 'study_bp'),
]

for module_path, bp_name in modules:
    try:
        module = __import__(module_path, fromlist=[bp_name])
        if hasattr(module, bp_name):
            bp = getattr(module, bp_name)
            print(f"✅ from {module_path:35} import {bp_name:10} → {bp}")
        else:
            print(f"❌ {module_path:35}.{bp_name} does not exist")
            import_errors.append(f"{module_path}.{bp_name}")
    except Exception as e:
        print(f"❌ {module_path:35} import failed: {type(e).__name__}")
        import_errors.append(module_path)

if import_errors:
    print()
    print(f"⚠️  {len(import_errors)} module import(s) failed!")
    sys.exit(1)

print()

# Step 5: Full app import test
print("─" * 70)
print("STEP 5: FULL FLASK APP IMPORT TEST")
print("─" * 70)

try:
    import app
    print(f"✅ Flask app imported successfully")
    print(f"   Debug mode: {app.app.debug if hasattr(app, 'app') else 'unknown'}")
    print(f"   Max content length: {app.app.config.get('MAX_CONTENT_LENGTH')}")
except Exception as e:
    print(f"❌ Flask app import failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Final summary
print("=" * 70)
print(" ✅ ALL VERIFICATION CHECKS PASSED")
print("=" * 70)
print()
print("Your blueprints are correctly set up and ready to use!")
print()
print("To start the app, run:")
print("  python3 app.py")
print()
print("Or with Gunicorn:")
print("  gunicorn -w 1 -b 0.0.0.0:7860 app:app")
print()
