FROM python:3.11.2-slim

RUN pip install "poetry<2"
RUN mkdir diff_poetry_lock
COPY diff_poetry_lock/* ./diff_poetry_lock/
COPY poetry.lock pyproject.toml entrypoint.sh ./diff_poetry_lock/
RUN python3 -m venv /diff_poetry_lock/.venv
RUN poetry install --directory /diff_poetry_lock
ENV PYTHONPATH="/"

ENTRYPOINT ["/diff_poetry_lock/entrypoint.sh"]
