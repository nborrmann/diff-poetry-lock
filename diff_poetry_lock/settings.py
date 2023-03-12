import sys
from typing import Any

from pydantic import BaseSettings, Field, ValidationError, validator


class Settings(BaseSettings):
    event_name: str = Field(env="github_event_name")  # must be 'pull_request'
    ref: str = Field(env="github_ref")
    repository: str = Field(env="github_repository")
    token: str = Field(env="input_github_token")
    base_ref: str = Field(env="github_base_ref")
    lockfile_path: str = Field(env="input_lockfile_path", default="poetry.lock")

    def __init__(self, **values: Any) -> None:  # noqa: ANN401
        try:
            super().__init__(**values)
        except ValidationError as ex:
            if e1 := next(e.exc for e in ex.raw_errors if e.loc_tuple() == ("event_name",)):  # type: ignore[union-attr]
                # event_name is not 'pull_request' - we fail early
                print(str(e1), file=sys.stderr)
                sys.exit(0)
            raise

    @validator("event_name")
    def event_must_be_pull_request(cls, v: str) -> str:  # noqa: N805
        if v != "pull_request":
            raise ValueError("This Github Action can only be run in the context of a pull request")
        return v

    def pr_num(self) -> str:
        # TODO: Validate early
        return self.ref.split("/")[2]
