"""Minimal unit tests with proper cleanup using tmp_path fixture."""

import json
import pytest
import polars as pl
from taskhut import AnnotationTool, default_hash_func


@pytest.fixture
def annotated_tool(tmp_path):
    """Create an AnnotationTool with 5 items, 3 annotated."""
    data = [{"id": i, "text": f"test {i}"} for i in range(5)]
    tool = AnnotationTool(data_source=data, username="alice", cache_path=str(tmp_path / "test.db"))

    # Annotate 3 tasks
    for _ in range(3):
        task = tool.get_current_task()
        tool.annotate(task, {"label": "positive"})

    return tool


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

    tool.annotate(tool.get_current_task(), {"label": "label"})
    tool.annotate(tool.get_current_task(), {"label": "label"})

    progress = tool.get_progress()
    assert progress["total"] == 5
    assert progress["completed"] == 2
    assert progress["remaining"] == 3
    assert progress["percent_complete"] == 40.0

    tool.annotate(tool.get_current_task(), {"label": "label"})
    tool.annotate(tool.get_current_task(), {"label": "label"})

    progress = tool.get_progress()
    assert progress["completed"] == 4
    assert progress["remaining"] == 1
    assert progress["percent_complete"] == 80.0

    tool.annotate(tool.get_current_task(), {"label": "label"})

    progress = tool.get_progress()
    assert progress["completed"] == 5
    assert progress["remaining"] == 0
    assert progress["percent_complete"] == 100.0


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
    """Export should write valid JSONL to file and infer format from extension."""
    data = [{"id": 1, "text": "test"}]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "export.db")
    )

    task = tool.get_current_task()
    tool.annotate(task, {"label": "positive"})

    export_path = tmp_path / "export.jsonl"
    tool.export_annotations(filepath=str(export_path))

    # Verify file exists and contains valid JSONL
    assert export_path.exists()
    with open(export_path) as f:
        record = json.loads(f.readline())
        assert "example" in record
        assert "annotation" in record
        assert record["user"] == "alice"


def test_annotation_loop(tmp_path):
    """Test useful loop for the frontend."""
    data = [{"id": i, "text": f"test {i}"} for i in range(15)]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "export.db")
    )

    for i in range(15):
        task = tool.get_current_task()
        tool.annotate(task, {"label": "positive"})

    assert tool.get_progress()["completed"] == 15
    assert len(tool.get_annotations()) == 15


def convert_to_list(result, return_as):
    """Convert different return types to list for uniform testing."""
    if return_as == "generator":
        return list(result)
    elif return_as == "polars":
        return result.to_dicts()
    else:  # list
        return result


def validate_polars_dataframe(df):
    """Validate Polars DataFrame has expected structure."""
    assert isinstance(df, pl.DataFrame)
    assert "example" in df.columns
    assert "annotation" in df.columns
    assert "user" in df.columns


@pytest.mark.parametrize("return_as", ["list", "generator", "polars"])
def test_get_annotations_return_formats(annotated_tool, return_as):
    """Test get_annotations with different return_as formats."""
    # Get annotations in the specified format
    result = annotated_tool.get_annotations(return_as=return_as)

    # Validate Polars-specific structure
    if return_as == "polars":
        validate_polars_dataframe(result)

    # Convert to list for uniform testing
    result_list = convert_to_list(result, return_as)

    assert len(result_list) == 3
    assert all("example" in ann for ann in result_list)
    assert all("annotation" in ann for ann in result_list)


@pytest.mark.parametrize(
    "file_ext,reader_func",
    [
        (".jsonl", lambda p: pl.read_ndjson(p)),
        (".ndjson", lambda p: pl.read_ndjson(p)),
        (".json", lambda p: pl.read_json(p)),
        (".parquet", lambda p: pl.read_parquet(p)),
    ],
)
def test_export_formats(tmp_path, file_ext, reader_func):
    """Test exporting annotations in different formats."""
    data = [{"id": i, "text": f"test {i}"} for i in range(3)]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "formats.db")
    )

    # Annotate some tasks
    for _ in range(3):
        task = tool.get_current_task()
        tool.annotate(task, {"label": "positive"})

    # Test export with the given format
    export_path = tmp_path / f"export{file_ext}"
    tool.export_annotations(filepath=str(export_path))
    assert export_path.exists()

    # Verify we can read the file back
    df = reader_func(export_path)
    assert len(df) == 3
    assert "user" in df.columns


def test_export_without_filepath_returns_jsonl_string(tmp_path):
    """Test that export_annotations without filepath returns JSONL string."""
    data = [{"id": 1, "text": "test"}]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "string.db")
    )

    task = tool.get_current_task()
    tool.annotate(task, {"label": "positive"})

    # Test without filepath returns string
    result = tool.export_annotations()
    assert isinstance(result, str)
    assert len(result) > 0

    # Verify it's valid JSONL
    record = json.loads(result.strip())
    assert "example" in record
    assert "annotation" in record


def make_file_dedup_source(annotations, tmp_path):
    """Create a JSONL file from annotations."""
    path = tmp_path / "upstream.jsonl"
    with open(path, "w") as f:
        for ann in annotations:
            f.write(json.dumps(ann) + "\n")
    return str(path)


def make_path_dedup_source(annotations, tmp_path):
    """Create a Parquet file from annotations and return Path object."""
    path = tmp_path / "upstream.parquet"
    pl.DataFrame(annotations).write_parquet(path)
    return path


def make_list_dedup_source(annotations, tmp_path):
    """Return annotations as list."""
    return annotations


def make_dataframe_dedup_source(annotations, tmp_path):
    """Return annotations as Polars DataFrame."""
    return pl.DataFrame(annotations)


@pytest.mark.parametrize(
    "make_dedup_source,num_upstream",
    [
        (make_file_dedup_source, 3),
        (make_list_dedup_source, 2),
        (make_dataframe_dedup_source, 4),
        (make_path_dedup_source, 3),
    ],
)
def test_get_annotations_with_dedup(tmp_path, make_dedup_source, num_upstream):
    """Test deduplication using different source types."""
    data = [{"id": i, "text": f"test {i}"} for i in range(5)]
    tool = AnnotationTool(
        data_source=data,
        username="alice",
        cache_path=str(tmp_path / "dedup.db"),
    )

    # Annotate 5 tasks
    for _ in range(5):
        task = tool.get_current_task()
        tool.annotate(task, {"label": "positive"})

    # Get all annotations and prepare dedup source
    all_annotations = tool.get_annotations()
    upstream_annotations = all_annotations[:num_upstream]
    dedup_source = make_dedup_source(upstream_annotations, tmp_path)

    # Get annotations with deduplication
    deduped = tool.get_annotations(dedup=dedup_source)

    # Should only have (5 - num_upstream) annotations
    expected = 5 - num_upstream
    assert len(deduped) == expected


def test_export_annotations_with_dedup(tmp_path):
    """Test export_annotations with deduplication."""
    data = [{"id": i, "text": f"test {i}"} for i in range(5)]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "dedup4.db")
    )

    # Annotate 5 tasks
    for _ in range(5):
        task = tool.get_current_task()
        tool.annotate(task, {"label": "positive"})

    # Export first 3 annotations as "upstream"
    all_annotations = tool.get_annotations()
    upstream_annotations = all_annotations[:3]
    upstream_path = tmp_path / "upstream.parquet"

    # Export upstream to parquet
    upstream_df = pl.DataFrame(upstream_annotations)
    upstream_df.write_parquet(upstream_path)

    # Export with deduplication
    export_path = tmp_path / "deduped_export.jsonl"
    tool.export_annotations(filepath=str(export_path), dedup=str(upstream_path))

    # Read back and verify
    assert export_path.exists()
    with open(export_path) as f:
        lines = f.readlines()

    # Should only have 2 lines (5 total - 3 upstream)
    assert len(lines) == 2


def test_dedup_with_no_overlap(tmp_path):
    """Test deduplication when there's no overlap between datasets."""
    data = [{"id": i, "text": f"test {i}"} for i in range(3)]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "dedup5.db")
    )

    # Annotate 3 tasks
    for _ in range(3):
        task = tool.get_current_task()
        tool.annotate(task, {"label": "positive"})

    # Create a completely different set of "upstream" annotations
    different_data = [{"id": i + 100, "text": f"different {i}"} for i in range(2)]
    different_tool = AnnotationTool(
        data_source=different_data, username="bob", cache_path=str(tmp_path / "different.db")
    )
    for _ in range(2):
        task = different_tool.get_current_task()
        different_tool.annotate(task, {"label": "negative"})

    upstream_annotations = different_tool.get_annotations()

    # Get annotations with deduplication - should keep all since no overlap
    deduped = tool.get_annotations(dedup=upstream_annotations)

    # Should still have all 3 annotations
    assert len(deduped) == 3


def test_dedup_validates_metadata_column(tmp_path):
    """Test that dedup raises error when data doesn't match Annotation schema."""
    data = [{"id": i, "text": f"test {i}"} for i in range(3)]
    tool = AnnotationTool(
        data_source=data, username="alice", cache_path=str(tmp_path / "dedup6.db")
    )

    # Annotate 3 tasks
    for _ in range(3):
        task = tool.get_current_task()
        tool.annotate(task, {"label": "positive"})

    # Create invalid upstream data missing required fields
    invalid_upstream = [{"example": {"id": 1}, "annotation": {"label": "test"}, "user": "bob"}]

    # Should raise error about schema validation
    try:
        tool.get_annotations(dedup=invalid_upstream)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "annotation schema" in str(e).lower()
