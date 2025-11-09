"""Minimal unit tests with proper cleanup using tmp_path fixture."""

import json
from taskhut import AnnotationTool, default_hash_func


def test_default_hash_func(tmp_path):
    """Hash function should be deterministic and produce different hashes for different inputs."""
    example = {"id": 1, "text": "hello world"}

    # Same input produces same hash
    hash1 = default_hash_func(example)
    hash2 = default_hash_func(example)
    assert hash1 == hash2

    # Different inputs produce different hashes
    example2 = {"id": 2, "text": "world"}
    hash3 = default_hash_func(example2)
    assert hash1 != hash3


def test_annotation_tool_basic_workflow(tmp_path):
    """Smoke test covering initialization, annotation, and retrieval."""
    data = [{"id": 1, "text": "test"}]
    cache_path = tmp_path / "test.db"

    # Init and verify setup
    tool = AnnotationTool(data_source=data, username="alice", cache_path=str(cache_path))
    assert tool.username == "alice"
    assert cache_path.exists()

    # Annotate and verify it was saved
    task = tool.get_current_task()
    tool.annotate(task, {"label": "positive"})
    annotations = tool.get_annotations()
    assert len(annotations) == 1


def test_get_progress(tmp_path):
    """Progress should calculate correctly with empty data and with annotations."""
    # Test empty data
    tool_empty = AnnotationTool(
        data_source=[], username="alice", cache_path=str(tmp_path / "empty.db")
    )
    progress = tool_empty.get_progress()
    assert progress["total"] == 0
    assert progress["completed"] == 0
    assert progress["remaining"] == 0

    # Test with annotations
    data = [{"id": i, "text": f"text {i}"} for i in range(5)]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "progress.db")
    )

    for i, task in enumerate(tool.get_tasks()):
        if i >= 2:
            break
        tool.annotate(task, {"label": f"label_{i}"})

    progress = tool.get_progress()
    assert progress["total"] == 5
    assert progress["completed"] == 2
    assert progress["remaining"] == 3
    assert progress["percent_complete"] == 40.0


def test_get_recent_tasks(tmp_path):
    """Recent tasks should handle empty state and limit parameter."""
    data = [{"id": i, "text": f"text {i}"} for i in range(5)]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "recent.db")
    )

    # Test empty state
    recent = tool.get_recent_tasks()
    assert len(recent) == 0

    # Annotate some tasks
    for _ in range(3):
        task = tool.get_current_task()
        if task:
            tool.annotate(task, {"label": f"label_{task['id']}"})

    # Test with limit parameter
    recent = tool.get_recent_tasks(limit=2)
    assert isinstance(recent, list)


def test_custom_routing_function(tmp_path):
    """Custom routing function should filter tasks per user."""
    data = [
        {"id": 0, "user_assigned": "alice"},
        {"id": 1, "user_assigned": "bob"},
        {"id": 2, "user_assigned": "alice"},
        {"id": 3, "user_assigned": "bob"},
    ]

    def custom_routing(example, username):
        return example.get("user_assigned") == username

    tool_alice = AnnotationTool(
        data_source=data,
        username="alice",
        cache_path=str(tmp_path / "routing.db"),
        routing_func=custom_routing,
    )

    tasks = list(tool_alice.get_tasks())

    # Alice should only see tasks assigned to her
    assert len(tasks) == 2
    assert all(t["user_assigned"] == "alice" for t in tasks)


def test_annotate_metadata_and_updates(tmp_path):
    """Annotate should preserve metadata and creation dates on updates."""
    data = [{"id": 1, "text": "test"}]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "metadata.db")
    )

    task = tool.get_current_task()

    # Test metadata preservation
    metadata = {"confidence": 0.95, "source": "manual"}
    tool.annotate(task, {"label": "positive"}, metadata=metadata)

    annotations = tool.get_annotations()
    assert len(annotations) == 1
    assert annotations[0]["user"] == "alice"
    assert annotations[0]["metadata"]["confidence"] == 0.95
    assert annotations[0]["metadata"]["source"] == "manual"

    # Test creation date preservation on update
    creation_date1 = annotations[0]["creation_date"]
    tool.annotate(task, {"label": "negative"})

    annotations2 = tool.get_annotations()
    creation_date2 = annotations2[0]["creation_date"]
    annotation_date2 = annotations2[0]["annotation_date"]

    assert creation_date1 == creation_date2
    assert annotation_date2 >= creation_date2


def test_export_to_file(tmp_path):
    """Export should write valid JSONL to file."""
    data = [{"id": 1, "text": "test"}]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "export.db")
    )

    task = tool.get_current_task()
    tool.annotate(task, {"label": "positive"})

    export_path = tmp_path / "export.jsonl"
    tool.export_annotations(filepath=str(export_path), format="jsonl")

    # Verify file exists and contains valid JSONL
    assert export_path.exists()
    with open(export_path) as f:
        record = json.loads(f.readline())
        assert "example" in record
        assert "annotation" in record
        assert record["user"] == "alice"
