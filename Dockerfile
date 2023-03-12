FROM python:3.11.2-slim

RUN pip install poetry
RUN pip install requests
RUN pip install pydantic

RUN mkdir diff_poetry_lock
COPY diff_poetry_lock/* ./diff_poetry_lock/
ENV PYTHONPATH="/"

ENTRYPOINT ["/usr/local/bin/python3", "/diff_poetry_lock/run_poetry.py"]
