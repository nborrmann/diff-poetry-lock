import sys
from typing import Any

from pydantic import field_validator, Field, ValidationError
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    event_name: str = Field(validation_alias="github_event_name", default="poetry.lock")  # must be 'pull_request'
    ref: str = Field(validation_alias="github_ref")
    repository: str = Field(validation_alias="github_repository")
    token: str = Field(validation_alias="input_github_token")
    base_ref: str = Field(validation_alias="github_base_ref")
    lockfile_path: str = Field(validation_alias="input_lockfile_path", default="poetry.lock")

    def __init__(self, **values: Any) -> None:  # noqa: ANN401
        try:
            super().__init__(**values)
        except ValidationError as ex:
            if e1 := next(e.exc for e in ex.raw_errors if e.loc_tuple() == ("event_name",)):  # type: ignore[union-attr]
                # event_name is not 'pull_request' - we fail early
                print(str(e1), file=sys.stderr)
                sys.exit(0)
            raise

    @field_validator("event_name")
    @classmethod
    def event_must_be_pull_request(cls, v: str) -> str:  # noqa: N805
        if v != "pull_request":
            raise ValueError("This Github Action can only be run in the context of a pull request")
        return v

    def pr_num(self) -> str:
        # TODO: Validate early
        return self.ref.split("/")[2]
