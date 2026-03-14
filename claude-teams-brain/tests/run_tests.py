#!/usr/bin/env python3
"""
Run all claude-teams-brain tests.

Usage:
    python3 tests/run_tests.py          # from plugin root
    python3 -m unittest discover tests  # alternative
"""

import sys
import os
import unittest

# Ensure we're running from the plugin root
plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(plugin_root)
sys.path.insert(0, os.path.join(plugin_root, 'scripts'))

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.join(plugin_root, 'tests'),
        pattern='test_*.py'
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
