"""Tests for the main module."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import main


def test_main():
    """Test that main function runs without error."""
    try:
        main()
    except Exception as e:
        raise AssertionError(f"main() raised {type(e).__name__}: {e}")
