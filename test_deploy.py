#!/usr/bin/env python3
"""Test script to verify deployment readiness."""

import sys
import os

print("=" * 60)
print("DEPLOYMENT TEST - Checking all critical imports")
print("=" * 60)

# Test 1: Core imports
print("\n[1/5] Testing core imports...")
try:
    from vgc_mcp_core.config import logger
    print("  OK vgc_mcp_core.config")
except Exception as e:
    print(f"  FAIL vgc_mcp_core.config: {e}")
    sys.exit(1)

# Test 2: Nature optimization module
print("\n[2/5] Testing nature_optimization module...")
try:
    from vgc_mcp_core.calc.nature_optimization import find_optimal_nature_for_benchmarks
    print("  OK nature_optimization imports")
except Exception as e:
    print(f"  FAIL nature_optimization: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Server module
print("\n[3/5] Testing server module...")
try:
    from vgc_mcp.server import main_http, mcp
    print(f"  OK Server module loaded ({len(mcp._tool_manager._tools)} tools)")
except Exception as e:
    print(f"  FAIL Server module: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: HTTP dependencies
print("\n[4/5] Testing HTTP server dependencies...")
try:
    import uvicorn
    import starlette
    from starlette.applications import Starlette
    from mcp.server.sse import SseServerTransport
    print("  OK All HTTP dependencies available")
except Exception as e:
    print(f"  FAIL HTTP dependencies: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Entry point
print("\n[5/5] Testing entry point function...")
try:
    os.environ['PORT'] = '8000'
    # Don't actually start the server, just verify it can be called
    import inspect
    sig = inspect.signature(main_http)
    print(f"  OK main_http signature: {sig}")
    print("  OK Entry point is callable")
except Exception as e:
    print(f"  FAIL Entry point: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("SUCCESS: ALL TESTS PASSED - Deployment should work!")
print("=" * 60)
