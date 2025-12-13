#!/bin/bash

echo "=== Security Audit ==="

echo "
1. Checking for hardcoded secrets..."
grep -r "password\|api_key\|secret\|token.*=" . --include="*.py" --include="*.js" --include="*.jsx" --exclude-dir=node_modules --exclude-dir=.venv310 --exclude-dir=.git

echo "
2. Checking localStorage usage..."
grep -r "localStorage\|sessionStorage" frontend/src --include="*.js" --include="*.jsx"

echo "
3. Checking for SQL injection risks..."
grep -r "\.execute.*format\|\.execute.*%" backend --include="*.py"

echo "
4. Checking for XSS vulnerabilities..."
grep -r "dangerouslySetInnerHTML\|innerHTML\|eval" frontend/src --include="*.js" --include="*.jsx"

echo "
5. Running Python security scan (Bandit)..."
if command -v bandit &> /dev/null; then
    bandit -r backend/ -f screen
else
    echo "Bandit not installed. Skipping."
fi

echo "
6. Checking Python dependencies (Safety)..."
if command -v safety &> /dev/null; then
    safety check
else
    echo "Safety not installed. Skipping."
fi

echo "
7. Running npm audit..."
cd frontend && npm audit && cd ..

echo "
=== Audit Complete ==="
