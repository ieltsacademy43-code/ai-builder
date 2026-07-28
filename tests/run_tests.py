#!/usr/bin/env python3
"""Run tests directly: python tests/run_tests.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_all import run_all_tests

if __name__ == "__main__":
    run_all_tests()