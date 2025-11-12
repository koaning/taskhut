# taskhut

A task routing utility, meant for help with simple team-based annotation situations. It's pretty darn minimal, but really helps with getting started.

## Quick Start

```python
from taskhut import AnnotationTool

# Your data to annotate
data = [
    {"id": 1, "text": "Super duper happy"},
    {"id": 2, "text": "Oh no, negative sentiment!"},
    {"id": 3, "text": "But this sentiment is mega positive!"}
]

# Create annotation tool
tool = AnnotationTool(
    data_source=data,
    username="alice",
    cache_path="./annotations.db"
)

# Annotate tasks using get_current_task (recommended)
while task := tool.get_current_task():
    label = input(f"Label for '{task['text']}': ")
    tool.annotate(task, label)  # Automatically advances to next task

    # Check progress
    progress = tool.get_progress()
    print(f"Progress: {progress['completed']}/{progress['total']}")

# Export annotations (saves directly to file)
tool.export_annotations(filepath="annotations.jsonl")
```
