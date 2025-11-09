import json
import hashlib
from typing import Callable, Dict, Any, List, Optional, Iterator
from datetime import datetime
from collections import deque
from diskcache import Cache


def default_hash_func(example: Dict[str, Any]) -> str:
    """
    Default hashing function for examples.

    Creates a stable hash from the JSON representation of the example dict.

    Args:
        example: The example dict to hash

    Returns:
        SHA256 hex digest of the example
    """
    json_str = json.dumps(example, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


def default_routing_func(example: Dict[str, Any], username: str) -> bool:
    """
    Default routing function that assigns all tasks to all users.
    """
    return True

class AnnotationTool:
    """
    A data annotation tool with disk-backed caching and task routing.

    Examples:
        >>> tool = AnnotationTool(
        ...     data_source=[{"id": 1, "text": "hello"}, {"id": 2, "text": "world"}],
        ...     username="alice",
        ...     cache_path="./annotations.db"
        ... )

        >>> # Annotate tasks
        >>> for example in tool.get_tasks():
        ...     label = input(f"Label for {example}: ")
        ...     tool.save_annotation(example, label)

        >>> # Correct the last annotation
        >>> recent = tool.get_recent_tasks()
        >>> tool.save_annotation(recent[0], "corrected_label")
    """

    def __init__(
        self,
        data_source: List[Dict[str, Any]],
        username: str,
        cache_path: str = "./annotations.db",
        routing_func: Callable[[Dict[str, Any], str], bool] = default_routing_func,
        recent_history_size: int = 5,
        hash_func: Callable[[Dict[str, Any]], str] = default_hash_func
    ):
        """
        Initialize the annotation tool.

        Args:
            data_source: List of examples (dicts) to annotate
            username: Current annotator's username
            cache_path: Path to disk cache database
            routing_func: Optional function to determine task assignment.
                         Should return True if example is assigned to this user.
                         Default: assigns all tasks to all users.
            recent_history_size: Number of recent task hashes to keep in memory
            hash_func: Function to hash examples for unique identification.
                      Default: default_hash_func (SHA256 of JSON)
        """
        self.data_source = data_source
        self.username = username
        self.cache = Cache(cache_path)
        self.routing_func = routing_func if routing_func is not None else lambda ex, user: True
        self.recent_history_size = recent_history_size
        self.hash_func = hash_func

        # In-memory tracking of recently annotated examples
        # Stores example hashes in order (most recent last)
        self._recent_hashes: deque = deque(maxlen=recent_history_size)

    def get_tasks(self) -> Iterator[Dict[str, Any]]:
        """
        Iterate through incomplete tasks assigned to this user.

        Yields:
            Examples that are (1) assigned to this user and (2) not yet annotated
        """
        for example in self.data_source:
            # Check if this task is assigned to the current user
            if not self.routing_func(example, self.username):
                continue

            # Check if this example has already been annotated by this user
            example_hash = self.hash_func(example)
            cache_key = f"{self.username}:{example_hash}"

            if cache_key not in self.cache:
                yield example

    def save_annotation(
        self,
        example: Dict[str, Any],
        annotation: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save an annotation for an example.

        Args:
            example: The example being annotated
            annotation: The annotation/label
            metadata: Optional metadata (timestamp, confidence, etc.)
        """
        example_hash = self.hash_func(example)
        cache_key = f"{self.username}:{example_hash}"

        # Check if this is an update or new annotation
        existing = self.cache.get(cache_key)
        creation_date = existing["creation_date"] if existing else datetime.now().isoformat()

        # Build annotation record
        record = {
            "original_example": example,
            "user": self.username,
            "annotation": annotation,
            "creation_date": creation_date,
            "annotation_date": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        # Save to disk cache
        self.cache[cache_key] = record

        # Update recent history (remove if exists, then add to end)
        if example_hash in self._recent_hashes:
            self._recent_hashes.remove(example_hash)
        self._recent_hashes.append(example_hash)

    def get_recent_tasks(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recently annotated tasks by this user for quick corrections.

        Args:
            limit: Maximum number of recent tasks to return.
                  If None, returns up to recent_history_size tasks.

        Returns:
            List of recently annotated examples (most recent first)
        """
        if limit is None:
            limit = self.recent_history_size

        # Get recent hashes (most recent last in deque)
        recent_hashes = list(self._recent_hashes)[-limit:]

        # Reverse to get most recent first
        recent_hashes.reverse()

        # Retrieve the original examples
        recent_examples = []
        for example_hash in recent_hashes:
            cache_key = f"{self.username}:{example_hash}"
            record = self.cache.get(cache_key)
            if record:
                recent_examples.append(record["original_example"])

        return recent_examples

    def get_progress(self) -> Dict[str, Any]:
        """
        Get annotation progress statistics for current user.

        Returns:
            Dict with 'total', 'completed', 'remaining', 'percent_complete'
        """
        # Count tasks assigned to this user
        total = sum(1 for ex in self.data_source if self.routing_func(ex, self.username))

        # Count completed tasks
        completed = 0
        for example in self.data_source:
            if not self.routing_func(example, self.username):
                continue

            example_hash = self.hash_func(example)
            cache_key = f"{self.username}:{example_hash}"
            if cache_key in self.cache:
                completed += 1

        remaining = total - completed
        percent_complete = (completed / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "completed": completed,
            "remaining": remaining,
            "percent_complete": round(percent_complete, 2)
        }

    def get_all_annotations(self, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all annotations, optionally filtered by username.

        Args:
            username: If provided, only return annotations by this user.
                     If None, return all annotations from all users.

        Returns:
            List of annotation records with example, annotation, username, and metadata
        """
        annotations = []

        # Iterate through all cache keys
        for key in self.cache:
            # Keys are formatted as "username:hash"
            if username is not None:
                if not key.startswith(f"{username}:"):
                    continue

            record = self.cache[key]
            annotations.append(record)

        return annotations

    def export_annotations(self, format: str = "jsonl") -> str:
        """
        Export annotations in specified format.

        Args:
            format: Export format ('jsonl' supported)

        Returns:
            Serialized annotations
        """
        if format != "jsonl":
            raise ValueError(f"Unsupported format: {format}. Only 'jsonl' is supported.")

        annotations = self.get_all_annotations()

        # Convert to JSONL (one JSON object per line)
        lines = [json.dumps(record, ensure_ascii=False) for record in annotations]
        return "\n".join(lines)
