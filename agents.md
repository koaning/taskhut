# Agent Instructions for taskhut

## Package Manager

This project uses **`uv`** as the package manager, not `pip` or `pip3`.

- To install dependencies: `uv pip install <package>`
- To install the project in editable mode: `uv pip install -e .`
- To create a virtual environment: `uv venv`

## Running Tests

```bash
uv pip install pytest
.venv/bin/python -m pytest tests/ -v
```

Or use the Makefile:
```bash
make test
```

## Running the Demo

```bash
make demo
```

Or manually:
```bash
.venv/bin/python examples/demo.py
```

## Project Structure

- `taskhut/annotation_tool.py` - Main annotation tool class
- `examples/demo.py` - Demo script showing usage
- `tests/test_annotation_tool.py` - Test suite
- `README.md` - User-facing documentation

## Key API Changes

The library recently underwent API improvements:

1. **`get_annotations()`** - Renamed from `get_all_annotations` (shorter name)
2. **`get_current_task()`** - New method to safely track current task without exposing generator
3. **`annotate()`** - Now automatically advances to next task when current task is annotated
4. **`export_annotations(filepath=...)`** - Now can save directly to disk with optional filepath parameter

The recommended workflow is now:
```python
from taskhut import TaskHut

# Create tool instance
tool = TaskHut(
    data_source=[{"id": 1, "text": "example"}],
    username="alice",
    cache_path="./annotations.db"
)

# Annotate tasks
while task := tool.get_current_task():
    # In real usage: label = input(f"Label: ")
    label = {"sentiment": "positive"}  # Example annotation
    tool.annotate(task, label)  # Automatically advances
```

This is safer than the old `get_tasks()` generator approach, as users won't accidentally call `next()` and lose track of their position.
