#!/bin/bash
if [ -z "$INPUT_POETRY_VERSION" ]; then
    echo "Poetry version set to $INPUT_POETRY_VERSION, overriding default version"
    pip install --force-reinstall poetry=="$INPUT_POETRY_VERSION"
fi
poetry --directory /diff_poetry_lock run python3 /diff_poetry_lock/run_poetry.py