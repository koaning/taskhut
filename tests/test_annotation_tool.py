import pytest
import tempfile
import os
import json
from pathlib import Path
from taskhut import AnnotationTool


@pytest.fixture
def sample_data():
    """Sample data for testing"""
    return [
        {"id": 1, "text": "The cat sat on the mat"},
        {"id": 2, "text": "Dogs are loyal animals"},
        {"id": 3, "text": "Birds can fly"},
        {"id": 4, "text": "Python is a programming language"},
        {"id": 5, "text": "The sun is shining today"}
    ]


@pytest.fixture
def temp_db():
    """Create a temporary database file"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


class TestGetCurrentTask:
    """Tests for get_current_task functionality"""

    def test_get_current_task_returns_first_task(self, sample_data, temp_db):
        """Test that get_current_task returns the first unannotated task"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        task = tool.get_current_task()
        assert task is not None
        assert task["id"] == 1
        assert task["text"] == "The cat sat on the mat"

    def test_get_current_task_returns_same_task_until_annotated(self, sample_data, temp_db):
        """Test that get_current_task returns the same task until it's annotated"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        task1 = tool.get_current_task()
        task2 = tool.get_current_task()

        assert task1 == task2

    def test_annotate_advances_current_task(self, sample_data, temp_db):
        """Test that annotate() advances to the next task"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        task1 = tool.get_current_task()
        assert task1["id"] == 1

        tool.annotate(task1, "positive")

        task2 = tool.get_current_task()
        assert task2 is not None
        assert task2["id"] == 2

    def test_get_current_task_returns_none_when_all_complete(self, sample_data, temp_db):
        """Test that get_current_task returns None when all tasks are complete"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        # Annotate all tasks
        for i in range(5):
            task = tool.get_current_task()
            if task:
                tool.annotate(task, f"label_{i}")

        # Should return None now
        task = tool.get_current_task()
        assert task is None

    def test_get_current_task_workflow(self, sample_data, temp_db):
        """Test the complete workflow with get_current_task"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        annotated_count = 0
        while task := tool.get_current_task():
            tool.annotate(task, f"label_{task['id']}")
            annotated_count += 1

        assert annotated_count == 5

        # Verify all are annotated
        progress = tool.get_progress()
        assert progress["completed"] == 5
        assert progress["remaining"] == 0


class TestGetAnnotations:
    """Tests for get_annotations (renamed from get_all_annotations)"""

    def test_get_annotations_returns_all_annotations(self, sample_data, temp_db):
        """Test that get_annotations returns all annotations"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        # Annotate a few
        for i, task in enumerate(tool.get_tasks()):
            if i >= 3:
                break
            tool.annotate(task, f"label_{i}")

        annotations = tool.get_annotations()
        assert len(annotations) == 3

    def test_get_annotations_filters_by_username(self, sample_data, temp_db):
        """Test that get_annotations filters by username"""
        tool_alice = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)
        tool_bob = AnnotationTool(data_source=sample_data, username="bob", cache_path=temp_db)

        # Alice annotates 2
        for i, task in enumerate(tool_alice.get_tasks()):
            if i >= 2:
                break
            tool_alice.annotate(task, f"alice_label_{i}")

        # Bob annotates 1
        for i, task in enumerate(tool_bob.get_tasks()):
            if i >= 1:
                break
            tool_bob.annotate(task, f"bob_label_{i}")

        alice_annotations = tool_alice.get_annotations(username="alice")
        bob_annotations = tool_bob.get_annotations(username="bob")
        all_annotations = tool_alice.get_annotations()

        assert len(alice_annotations) == 2
        assert len(bob_annotations) == 1
        assert len(all_annotations) == 3


class TestExportAnnotations:
    """Tests for export_annotations with file saving"""

    def test_export_annotations_to_string(self, sample_data, temp_db):
        """Test exporting annotations to string"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        # Annotate a few
        for i, task in enumerate(tool.get_tasks()):
            if i >= 2:
                break
            tool.annotate(task, f"label_{i}")

        output = tool.export_annotations(format="jsonl")

        # Verify it's valid JSONL
        lines = output.strip().split("\n")
        assert len(lines) == 2

        for line in lines:
            record = json.loads(line)
            assert "original_example" in record
            assert "annotation" in record
            assert "user" in record

    def test_export_annotations_to_file(self, sample_data, temp_db):
        """Test exporting annotations to file"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        # Annotate a few
        for i, task in enumerate(tool.get_tasks()):
            if i >= 2:
                break
            tool.annotate(task, f"label_{i}")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".jsonl") as f:
            export_path = f.name

        try:
            output = tool.export_annotations(filepath=export_path, format="jsonl")

            # Verify file was created
            assert os.path.exists(export_path)

            # Verify file contents match returned string
            with open(export_path, 'r') as f:
                file_contents = f.read()

            assert file_contents == output

            # Verify it's valid JSONL
            lines = file_contents.strip().split("\n")
            assert len(lines) == 2
        finally:
            if os.path.exists(export_path):
                os.remove(export_path)

    def test_export_annotations_invalid_format(self, sample_data, temp_db):
        """Test that invalid format raises error"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        with pytest.raises(ValueError, match="Unsupported format"):
            tool.export_annotations(format="csv")


class TestAnnotateWithCurrentTask:
    """Tests for annotate() interaction with get_current_task"""

    def test_annotate_non_current_task_doesnt_advance(self, sample_data, temp_db):
        """Test that annotating a non-current task doesn't advance the iterator"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        current = tool.get_current_task()
        assert current["id"] == 1

        # Annotate a different task (not the current one)
        tool.annotate(sample_data[2], "random_label")

        # Current task should still be task 1
        current_after = tool.get_current_task()
        assert current_after["id"] == 1

    def test_correction_workflow_with_current_task(self, sample_data, temp_db):
        """Test correction workflow doesn't interfere with current task tracking"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        # Annotate first task
        task1 = tool.get_current_task()
        tool.annotate(task1, "label_1")

        # Move to second task
        task2 = tool.get_current_task()
        assert task2["id"] == 2

        # Correct the first task (from recent)
        recent = tool.get_recent_tasks(limit=1)
        tool.annotate(recent[0], "corrected_label_1")

        # Current task should still be task 2
        current = tool.get_current_task()
        assert current["id"] == 2


class TestBackwardsCompatibility:
    """Tests to ensure backwards compatibility with get_tasks() iterator"""

    def test_get_tasks_still_works_as_iterator(self, sample_data, temp_db):
        """Test that the old get_tasks() iterator still works"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        count = 0
        for task in tool.get_tasks():
            count += 1
            if count >= 3:
                break

        assert count == 3

    def test_mixing_get_tasks_and_get_current_task(self, sample_data, temp_db):
        """Test that using both methods works (though not recommended)"""
        tool = AnnotationTool(data_source=sample_data, username="alice", cache_path=temp_db)

        # Use get_current_task
        task1 = tool.get_current_task()
        tool.annotate(task1, "label_1")

        # Use get_tasks iterator
        tasks_from_iterator = []
        for i, task in enumerate(tool.get_tasks()):
            if i >= 2:
                break
            tasks_from_iterator.append(task["id"])

        # Should get tasks 2 and 3 (task 1 was already annotated)
        assert 2 in tasks_from_iterator
        assert 3 in tasks_from_iterator
