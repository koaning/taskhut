import json
import hashlib
from typing import Callable, Dict, Any, List, Optional, Iterator, Union, Literal, Iterable
from datetime import datetime
from collections import deque
from pathlib import Path
from diskcache import Cache
from pydantic import BaseModel
import polars as pl


class Annotation(BaseModel):
    example_hash: str
    example: Dict[str, Any]
    user: str
    annotation: Dict[str, Any]
    creation_date: str
    annotation_date: str
    metadata: Optional[Dict[str, Any]] = None


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
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


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
        hash_func: Callable[[Dict[str, Any]], str] = default_hash_func,
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

        # Track the current task
        self._current_task: Optional[Dict[str, Any]] = None
        self._task_iterator: Optional[Iterator[Dict[str, Any]]] = None

    def _cache_key(self, example: Dict[str, Any]) -> str:
        """
        Calculate the cache key for an example.

        Args:
            example: The example dict to calculate the key for

        Returns:
            Cache key in format "username:hash"
        """
        example_hash = self.hash_func(example)
        return f"{self.username}:{example_hash}"

    def get_tasks(self) -> Iterator[Dict[str, Any]]:
        """
        Iterate through incomplete tasks assigned to this user.

        Yields:
            Examples that are (1) assigned to this user and (2) not yet annotated

        Note: This method is provided for advanced use cases. For simpler workflows,
        use get_current_task() and annotate() which automatically track progress.
        """
        for example in self.data_source:
            # Check if this task is assigned to the current user
            if not self.routing_func(example, self.username):
                continue

            # Check if this example has already been annotated by this user
            cache_key = self._cache_key(example)

            if cache_key not in self.cache:
                yield example

    def get_current_task(self) -> Optional[Dict[str, Any]]:
        """
        Get the current task to annotate.

        Returns:
            The current task dict, or None if all tasks are complete

        Example:
            >>> tool = AnnotationTool(data_source=data, username="alice")
            >>> while task := tool.get_current_task():
            ...     label = input(f"Label for {task}: ")
            ...     tool.annotate(task, label)
        """
        # If we don't have a current task, try to get the next one
        if self._current_task is None:
            # Initialize or reset the iterator if needed
            if self._task_iterator is None:
                self._task_iterator = self.get_tasks()

            # Try to get the next task
            try:
                self._current_task = next(self._task_iterator)
            except StopIteration:
                self._current_task = None
                self._task_iterator = None

        return self._current_task

    def annotate(
        self,
        example: Dict[str, Any],
        annotation: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Save an annotation for an example.

        If the annotated example matches the current task (from get_current_task()),
        this automatically advances to the next task.

        Args:
            example: The example being annotated
            annotation: The annotation/label
            metadata: Optional metadata (timestamp, confidence, etc.)
        """
        cache_key = self._cache_key(example)

        # Check if this is an update or new annotation
        existing = self.cache.get(cache_key)
        creation_date = existing["creation_date"] if existing else datetime.now().isoformat()

        # Build annotation record
        example_hash = self.hash_func(example)
        metadata = metadata or {}
        record = {
            "example_hash": example_hash,
            "example": example,
            "user": self.username,
            "annotation": annotation,
            "creation_date": creation_date,
            "annotation_date": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        # Save to disk cache
        self.cache[cache_key] = Annotation(**record).model_dump()

        # Update recent history (remove if exists, then add to end)
        if cache_key in self._recent_hashes:
            self._recent_hashes.remove(cache_key)
        self._recent_hashes.append(cache_key)

        # If this was the current task, advance to the next one
        if self._current_task is not None:
            current_cache_key = self._cache_key(self._current_task)
            if current_cache_key == cache_key:
                self._current_task = None  # Will be fetched on next get_current_task() call

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

            cache_key = self._cache_key(example)
            if cache_key in self.cache:
                completed += 1

        remaining = total - completed
        percent_complete = (completed / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "completed": completed,
            "remaining": remaining,
            "percent_complete": round(percent_complete, 2),
        }

    def get_annotations(
        self,
        username: Optional[str] = None,
        return_as: Literal["list", "generator", "polars"] = "list",
        dedup: Optional[Union[str, Path, Iterable[Dict[str, Any]], pl.DataFrame]] = None,
    ) -> Union[List[Dict[str, Any]], Iterable[Dict[str, Any]], pl.DataFrame]:
        """
        Retrieve all annotations, optionally filtered by username and deduplicated.

        Args:
            username: If provided, only return annotations by this user.
                     If None, return all annotations from all users.
            return_as: Format to return annotations in:
                      - "list": Python list of dictionaries (default, loads all into memory)
                      - "generator": Python generator yielding one record at a time (memory efficient)
                      - "polars": Polars DataFrame (enables powerful data analysis)
            dedup: Optional source of existing annotations to deduplicate against.
                   Can be a filepath (str/Path), iterable of annotation dicts, or Polars DataFrame.
                   Deduplication is based on example_hash in metadata.
                   Note: When using dedup with return_as="generator", all annotations
                   must be loaded into memory for deduplication.

        Returns:
            Annotations in the requested format, excluding duplicates if dedup is provided
        """

        def _iter_annotations() -> Iterator[Dict[str, Any]]:
            """Internal generator for iterating through annotations."""
            for key in self.cache:
                # Keys are formatted as "username:hash"
                if username is not None:
                    if not key.startswith(f"{username}:"):
                        continue
                yield self.cache[key]

        # Get annotations as DataFrame for deduplication
        df = pl.DataFrame(list(_iter_annotations()))

        # Apply deduplication if requested
        if dedup is not None:
            # Load upstream annotations - convert to Path for consistent handling
            dedup_path = Path(dedup) if isinstance(dedup, (str, Path)) else None

            if dedup_path is not None:
                # It's a filepath - infer format and read
                suffix = dedup_path.suffix.lower()
                if suffix in (".jsonl", ".ndjson"):
                    upstream_df = pl.read_ndjson(dedup_path)
                elif suffix == ".json":
                    upstream_df = pl.read_json(dedup_path)
                elif suffix == ".parquet":
                    upstream_df = pl.read_parquet(dedup_path)
                else:
                    raise ValueError(
                        f"Unsupported file extension for dedup: '{suffix}'. "
                        f"Supported formats: .jsonl, .ndjson, .json, .parquet"
                    )
            else:
                # Cast to DataFrame (handles both DataFrame and iterable)
                upstream_df = pl.DataFrame(dedup)

            # Validate that upstream has required columns
            if "metadata" not in upstream_df.columns:
                raise ValueError("dedup source must have 'metadata' column containing example_hash")

            if "metadata" not in df.columns:
                raise ValueError(
                    "Current annotations missing 'metadata' column - cannot deduplicate"
                )

            # Perform anti-join to keep only annotations not in upstream
            # Use example_hash from metadata for deduplication
            df = df.with_columns(
                pl.col("metadata").struct.field("example_hash").alias("_example_hash")
            )
            upstream_df = upstream_df.with_columns(
                pl.col("metadata").struct.field("example_hash").alias("_example_hash")
            )

            # Anti-join: keep rows from df that don't have matching hash in upstream
            df = df.join(upstream_df.select("_example_hash"), on="_example_hash", how="anti").drop(
                "_example_hash"
            )

        # Return in requested format
        if return_as == "generator":
            # Convert back to generator
            def _deduped_generator():
                for row in df.iter_rows(named=True):
                    yield row

            return _deduped_generator()
        elif return_as == "polars":
            return df
        else:  # return_as == "list"
            return df.to_dicts()

    def _write_dataframe(self, df: pl.DataFrame, filepath: Union[str, Path]) -> str:
        """
        Write a Polars DataFrame to a file, inferring format from extension.

        Args:
            df: DataFrame to write
            filepath: Path to write to

        Returns:
            String representation for text formats, empty string for binary formats
        """
        path = Path(filepath)
        suffix = path.suffix.lower()

        if suffix in (".jsonl", ".ndjson"):
            df.write_ndjson(path)
            return df.write_ndjson()
        elif suffix == ".json":
            df.write_json(path)
            return df.write_json()
        elif suffix == ".parquet":
            df.write_parquet(path)
            # Parquet is binary, return empty string
            return ""
        else:
            raise ValueError(
                f"Unsupported file extension: '{suffix}'. "
                f"Supported formats: .jsonl, .ndjson, .json, .parquet"
            )

    def export_annotations(
        self,
        filepath: Optional[Union[str, Path]] = None,
        dedup: Optional[Union[str, Path, Iterable[Dict[str, Any]], pl.DataFrame]] = None,
    ) -> str:
        """
        Export annotations to a file or string. Format is inferred from the file extension.

        Supported formats:
        - .jsonl or .ndjson: Newline-delimited JSON (best for streaming large datasets)
        - .json: JSON array
        - .parquet: Apache Parquet format (best for data analysis and storage efficiency)

        Note: CSV format is not supported because annotations contain nested data structures.

        Args:
            filepath: Optional path to save the export. Format is inferred from extension.
                     If None, returns JSONL string for backward compatibility.
            dedup: Optional source of existing annotations to deduplicate against.
                   Can be a filepath (str/Path), iterable of annotation dicts, or Polars DataFrame.
                   Only annotations not present in the dedup source will be exported.

        Returns:
            Serialized annotations as string (only for JSONL/JSON when filepath is None)
        """
        # Get annotations as a Polars DataFrame with deduplication
        df = self.get_annotations(return_as="polars", dedup=dedup)

        # If no filepath, return JSONL string for backward compatibility
        if filepath is None:
            return df.write_ndjson()

        return self._write_dataframe(df, filepath)
