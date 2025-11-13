"""Test that code blocks in documentation work correctly."""

import pathlib
import pytest
from mktestdocs import check_md_file


@pytest.mark.parametrize(
    "fpath",
    pathlib.Path(".").glob("*.md"),
    ids=str,
)
def test_readme_code_blocks(fpath):
    """Test that code blocks in markdown files execute without errors."""
    check_md_file(fpath=fpath, memory=True)
