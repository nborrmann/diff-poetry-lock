FROM python:3.11.2-slim

RUN pip install poetry && mkdir /src
COPY poetry.lock pyproject.toml README.md /src/
COPY diff_poetry_lock /src/diff_poetry_lock
RUN python3 -m venv /src/.venv && poetry install --directory /src --without=dev

ENTRYPOINT ["poetry", "--directory", "/src", "run", "python3", "-m", "diff_poetry_lock.run_poetry"]