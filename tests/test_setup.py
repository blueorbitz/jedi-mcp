"""Test to verify the project setup is correct."""

import jedi_mcp


def test_package_version():
    """Verify the package version is set correctly."""
    assert jedi_mcp.__version__ == "0.1.0"


def test_package_imports():
    """Verify all required dependencies can be imported."""
    import strands
    import fastmcp
    import httpx
    import bs4
    import click
    import lxml
    import pytest
    import hypothesis
    
    # If we get here, all imports succeeded
    assert True
