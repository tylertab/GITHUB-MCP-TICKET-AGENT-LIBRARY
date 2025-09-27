#!/usr/bin/env python3
"""
Manual test to verify missing file handling works.
Run this script to test different scenarios.
"""

import os
import sys
import pathlib

# Add src to path
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ticketwatcher.handlers import handle_issue_event


def test_scenario_1_no_files():
    """Test: Issue with no file paths mentioned."""
    print("=== Testing: Issue with no file paths ===")
    
    event = {
        "action": "opened",
        "issue": {
            "number": 999,
            "title": "[agent-fix] Something is broken",
            "body": "The application crashes but I don't know which file.",
            "labels": [{"name": "agent-fix"}]
        }
    }
    
    try:
        result = handle_issue_event(event)
        print(f"No crash! Result: {result}")
        return True
    except Exception as e:
        print(f"Crashed: {e}")
        return False


def test_scenario_2_nonexistent_file():
    """Test: Issue mentions file that doesn't exist."""
    print("\n=== Testing: Issue with nonexistent file ===")
    
    event = {
        "action": "opened",
        "issue": {
            "number": 998,
            "title": "[agent-fix] Error in missing file",
            "body": '''
            Traceback (most recent call last):
              File "src/nonexistent/missing.py", line 10, in broken_function
                result = undefined_variable
            NameError: name 'undefined_variable' is not defined
            ''',
            "labels": [{"name": "agent-fix"}]
        }
    }
    
    try:
        result = handle_issue_event(event)
        print(f" No crash! Result: {result}")
        return True
    except Exception as e:
        print(f" Crashed: {e}")
        return False


def test_scenario_3_invalid_paths():
    """Test: Issue with malformed file paths."""
    print("\n=== Testing: Issue with invalid file paths ===")
    
    event = {
        "action": "opened",
        "issue": {
            "number": 997,
            "title": "[agent-fix] Weird file path error",
            "body": '''
            Some error in file \\\\invalid\\path\\file.py
            Also error in /root/system/file.py
            And in ../../../etc/passwd
            ''',
            "labels": [{"name": "agent-fix"}]
        }
    }
    
    try:
        result = handle_issue_event(event)
        print(f" No crash! Result: {result}")
        return True
    except Exception as e:
        print(f" Crashed: {e}")
        return False


def test_scenario_4_empty_issue():
    """Test: Issue with empty body."""
    print("\n=== Testing: Issue with empty body ===")
    
    event = {
        "action": "opened",
        "issue": {
            "number": 996,
            "title": "[agent-fix] Empty issue",
            "body": "",
            "labels": [{"name": "agent-fix"}]
        }
    }
    
    try:
        result = handle_issue_event(event)
        print(f" No crash! Result: {result}")
        return True
    except Exception as e:
        print(f" Crashed: {e}")
        return False


def main():
    """Run all manual tests."""
    print("Manual Test Suite: Missing Files Handling")
    print("=" * 50)
    
    # Set required environment variables for testing
    os.environ.setdefault("GITHUB_REPOSITORY", "test/repo")
    os.environ.setdefault("GITHUB_TOKEN", "fake_token_for_testing")
    
    tests = [
        test_scenario_1_no_files,
        test_scenario_2_nonexistent_file,
        test_scenario_3_invalid_paths,
        test_scenario_4_empty_issue
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n=== Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print(" All tests passed! Missing file handling is working.")
    else:
        print("  Some tests failed. Check the error handling.")


if __name__ == "__main__":
    main()
