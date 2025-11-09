# taskhut

A task routing utility, meant for help with simple team-based annotation situations. It's pretty darn minimal, but really helps with getting started.

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

# Annotate tasks using get_current_task (recommended)
while task := tool.get_current_task():
    label = input(f"Label for '{task['text']}': ")
    tool.annotate(task, label)  # Automatically advances to next task

# Check progress
progress = tool.get_progress()
print(f"Progress: {progress['completed']}/{progress['total']}")

# Review and correct recent annotations
recent = tool.get_recent_tasks(limit=5)
for example in recent:
    print(f"Recent: {example['text']}")
    # Optionally correct
    # tool.annotate(example, "new_label")

# Export annotations (saves directly to file)
tool.export_annotations(filepath="annotations.jsonl", format="jsonl")
```
