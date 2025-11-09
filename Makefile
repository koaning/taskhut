.PHONY: install clean test demo help

help:
	@echo "Available commands:"
	@echo "  make install    - Set up virtual environment and install dependencies"
	@echo "  make demo       - Run the demo script"
	@echo "  make test       - Run tests (if available)"
	@echo "  make clean      - Remove virtual environment and generated files"

install:
	@echo "Setting up taskhut project..."
	uv venv --allow-existing
	uv pip install -e .
	@echo "✓ Installation complete!"
	@echo "Activate the environment with: source .venv/bin/activate"

demo: install
	@echo "Running demo..."
	.venv/bin/python examples/demo.py

test: install
	@echo "Running tests..."
	.venv/bin/python -m pytest tests/ -v

clean:
	@echo "Cleaning up..."
	rm -rf .venv
	rm -rf *.egg-info
	rm -rf build dist
	rm -rf **/__pycache__
	rm -rf .pytest_cache
	rm -rf *.db demo_*.db examples/*.db
	rm -f demo_*.jsonl examples/*.jsonl
	@echo "✓ Cleanup complete!"
