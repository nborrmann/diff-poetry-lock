FROM python:3.11.2-slim

RUN pip install poetry
RUN mkdir diff_poetry_lock
COPY diff_poetry_lock/* ./diff_poetry_lock/
COPY poetry.lock ./diff_poetry_lock/
COPY pyproject.toml ./diff_poetry_lock/
RUN python3 -m venv /diff_poetry_lock/.venv
RUN poetry install --directory /diff_poetry_lock
ENV PYTHONPATH="/"

ENTRYPOINT ["poetry", "--directory", "/diff_poetry_lock", "run", "python3", "/diff_poetry_lock/run_poetry.py"]
