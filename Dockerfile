FROM python:3.11.2-slim

RUN pip install poetry
RUN mkdir diff_poetry_lock
COPY diff_poetry_lock/* ./diff_poetry_lock/
COPY poetry.lock ./diff_poetry_lock/
COPY pyproject.toml ./diff_poetry_lock/
WORKDIR diff_poetry_lock
RUN poetry install
ENV PYTHONPATH="/"

ENTRYPOINT ["poetry", "run", "python3", "/diff_poetry_lock/run_poetry.py"]
