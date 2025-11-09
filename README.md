# taskhut

A data annotation tool with disk-backed caching and task routing.

## Features

- **Disk-backed storage**: Uses diskcache (SQLite under the hood) for persistent annotations
- **Task routing**: Flexible routing functions to assign tasks to specific annotators
- **Correction workflow**: Quick access to recently annotated items for corrections
- **Progress tracking**: Monitor annotation progress per user
- **Export**: Export annotations to JSONL format
- **Customizable hashing**: Provide your own hash function for example identification

## Installation

### Quick Setup (Recommended)

```bash
make install
```

This will:
- Create a virtual environment using `uv`
- Install all dependencies
- Install taskhut in editable mode

### Manual Installation

```bash
uv venv
uv pip install -e .
```

Or with pip:
```bash
pip install -e .
```

### Available Make Commands

- `make install` - Set up virtual environment and install dependencies
- `make demo` - Run the demo script
- `make test` - Run tests (if available)
- `make clean` - Remove virtual environment and generated files
- `make help` - Show available commands

## Quick Start

```python
from taskhut import AnnotationTool

# Your data to annotate
data = [
    {"id": 1, "text": "The cat sat on the mat"},
    {"id": 2, "text": "Dogs are loyal animals"},
    {"id": 3, "text": "Birds can fly"}
]

# Create annotation tool
tool = AnnotationTool(
    data_source=data,
    username="alice",
    cache_path="./annotations.db"
)

# Annotate tasks
for example in tool.get_tasks():
    label = input(f"Label for '{example['text']}': ")
    tool.save_annotation(example, label)

# Check progress
progress = tool.get_progress()
print(f"Progress: {progress['completed']}/{progress['total']}")

# Review and correct recent annotations
recent = tool.get_recent_tasks(limit=5)
for example in recent:
    print(f"Recent: {example['text']}")
    # Optionally correct
    # tool.save_annotation(example, "new_label")

# Export annotations
jsonl_output = tool.export_annotations(format="jsonl")
with open("annotations.jsonl", "w") as f:
    f.write(jsonl_output)
```

## API Reference

### AnnotationTool

```python
AnnotationTool(
    data_source: List[Dict[str, Any]],
    username: str,
    cache_path: str = "./annotations.db",
    routing_func: Optional[Callable[[Dict[str, Any], str], bool]] = None,
    recent_history_size: int = 5,
    hash_func: Callable[[Dict[str, Any]], str] = default_hash_func
)
```

**Parameters:**
- `data_source`: List of examples (dicts) to annotate
- `username`: Current annotator's username
- `cache_path`: Path to disk cache database
- `routing_func`: Optional function to determine task assignment (defaults to assigning all tasks to all users)
- `recent_history_size`: Number of recent tasks to keep in memory
- `hash_func`: Function to hash examples for unique identification

### Methods

#### `get_tasks() -> Iterator[Dict[str, Any]]`
Iterate through incomplete tasks assigned to this user.

#### `save_annotation(example: Dict[str, Any], annotation: Any, metadata: Optional[Dict[str, Any]] = None)`
Save an annotation for an example. Overwrites if the same example is annotated again.

#### `get_recent_tasks(limit: Optional[int] = None) -> List[Dict[str, Any]]`
Get recently annotated tasks by this user for quick corrections (most recent first).

#### `get_progress() -> Dict[str, Any]`
Get annotation progress statistics. Returns dict with `total`, `completed`, `remaining`, `percent_complete`.

#### `get_all_annotations(username: Optional[str] = None) -> List[Dict[str, Any]]`
Retrieve all annotations, optionally filtered by username.

Each annotation record contains:
- `original_example`: The example that was annotated
- `user`: Username of the annotator
- `annotation`: The annotation/label
- `creation_date`: When the annotation was first created
- `annotation_date`: When the annotation was last updated
- `metadata`: Optional metadata dict

#### `export_annotations(format: str = "jsonl") -> str`
Export annotations in JSONL format.

## Examples

See the `examples/demo.py` file for working examples including:
- Basic annotation workflow
- Correction workflow
- Reviewing recent annotations
- Exporting annotations

Run the demo:
```bash
make demo
```

Or manually:
```bash
.venv/bin/python examples/demo.py
```

## Custom Routing

You can provide a custom routing function to assign tasks to specific users:

```python
def custom_router(example: Dict[str, Any], username: str) -> bool:
    # Route tasks with even IDs to alice, odd to bob
    if example["id"] % 2 == 0:
        return username == "alice"
    else:
        return username == "bob"

tool = AnnotationTool(
    data_source=data,
    username="alice",
    routing_func=custom_router
)
```

## Custom Hash Function

Provide your own hash function for example identification:

```python
def custom_hash(example: Dict[str, Any]) -> str:
    # Use the ID field if available
    return str(example.get("id", hash(str(example))))

tool = AnnotationTool(
    data_source=data,
    username="alice",
    hash_func=custom_hash
)
```

## License

MIT
