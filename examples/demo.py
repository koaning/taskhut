"""Basic demonstration of the AnnotationTool"""

from taskhut import AnnotationTool

# Sample data
data = [
    {"id": 1, "text": "The cat sat on the mat"},
    {"id": 2, "text": "Dogs are loyal animals"},
    {"id": 3, "text": "Birds can fly"},
    {"id": 4, "text": "Python is a programming language"},
    {"id": 5, "text": "The sun is shining today"}
]


def example_1_basic_annotation():
    """Example 1: Basic annotation with correction capability"""
    print("=" * 60)
    print("Example 1: Basic annotation with correction")
    print("=" * 60)

    tool = AnnotationTool(
        data_source=data,
        username="alice",
        cache_path="./demo_annotations.db",
        recent_history_size=5
    )

    # Show progress
    progress = tool.get_progress()
    print(f"\nProgress: {progress['completed']}/{progress['total']} "
          f"({progress['percent_complete']}% complete)")

    # Annotate first 3 examples
    print("\nAnnotating first 3 examples...")
    for i, example in enumerate(tool.get_tasks()):
        if i >= 3:
            break
        print(f"\nExample: {example['text']}")
        # Simulating user input with predefined labels
        sentiments = ["positive", "positive", "neutral"]
        sentiment = sentiments[i]
        print(f"Label: {sentiment}")
        tool.save_annotation(example, sentiment)

    # Check progress again
    progress = tool.get_progress()
    print(f"\nProgress: {progress['completed']}/{progress['total']} "
          f"({progress['percent_complete']}% complete)")

    # Correct the last one
    print("\n--- Correcting last annotation ---")
    recent = tool.get_recent_tasks(limit=1)
    if recent:
        print(f"Correcting: {recent[0]['text']}")
        print(f"New label: negative")
        tool.save_annotation(recent[0], "negative")

    # View recent annotations
    print("\n--- Recent annotations ---")
    all_annotations = tool.get_all_annotations(username="alice")
    for ann in all_annotations[-3:]:
        print(f"{ann['original_example']['text']}: {ann['annotation']}")


def example_2_review_recent():
    """Example 2: Review recent annotations"""
    print("\n" + "=" * 60)
    print("Example 2: Review recent annotations")
    print("=" * 60)

    tool = AnnotationTool(
        data_source=data,
        username="alice",
        cache_path="./demo_annotations.db"
    )

    # Get all annotations by alice
    annotations = tool.get_all_annotations(username="alice")
    print(f"\nFound {len(annotations)} annotations by alice")

    # Show recent 3
    print("\n--- Last 3 annotations ---")
    recent = tool.get_recent_tasks(limit=3)
    for i, example in enumerate(recent, 1):
        # Find the annotation for this example
        ann = next((a for a in annotations if a['original_example'] == example), None)
        if ann:
            print(f"{i}. Text: {example['text']}")
            print(f"   Label: {ann['annotation']}")
            print(f"   Annotated: {ann['annotation_date']}")


def example_3_export():
    """Example 3: Export annotations"""
    print("\n" + "=" * 60)
    print("Example 3: Export annotations to JSONL")
    print("=" * 60)

    tool = AnnotationTool(
        data_source=data,
        username="alice",
        cache_path="./demo_annotations.db"
    )

    # Export to JSONL
    jsonl_output = tool.export_annotations(format="jsonl")
    print("\nExported annotations (JSONL format):")
    print(jsonl_output)

    # Could save to file
    with open("./demo_export.jsonl", "w") as f:
        f.write(jsonl_output)
    print("\nSaved to demo_export.jsonl")


if __name__ == "__main__":
    example_1_basic_annotation()
    example_2_review_recent()
    example_3_export()

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
