import requests
from pydantic import BaseModel, Field, parse_obj_as
from requests import Response

from diff_poetry_lock.settings import Settings

MAGIC_COMMENT_IDENTIFIER = "<!-- posted by Github Action nborrmann/diff-poetry-lock -->\n\n"
MAGIC_BOT_USER_ID = 41898282


class GithubComment(BaseModel):
    class GithubUser(BaseModel):
        id_: int = Field(alias="id")

    body: str
    id_: int = Field(alias="id")
    user: GithubUser

    def is_bot_comment(self) -> bool:
        return self.body.startswith(MAGIC_COMMENT_IDENTIFIER) and self.user.id_ == MAGIC_BOT_USER_ID


class GithubApi:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.session = requests.session()

    def post_comment(self, comment: str) -> None:
        if not comment:
            print("No changes to lockfile detected")
            return

        r = self.session.post(
            f"{self.s.api_url}/repos/{self.s.repository}/issues/{self.s.pr_num()}/comments",
            headers={"Authorization": f"Bearer {self.s.token}", "Accept": "application/vnd.github+json"},
            json={"body": f"{MAGIC_COMMENT_IDENTIFIER}{comment}"},
            timeout=10,
        )
        r.raise_for_status()

    def update_comment(self, comment_id: int, comment: str) -> None:
        r = self.session.patch(
            f"{self.s.api_url}/repos/{self.s.repository}/issues/comments/{comment_id}",
            headers={"Authorization": f"Bearer {self.s.token}", "Accept": "application/vnd.github+json"},
            json={"body": f"{MAGIC_COMMENT_IDENTIFIER}{comment}"},
            timeout=10,
        )
        r.raise_for_status()

    def list_comments(self) -> list[GithubComment]:
        all_comments, comments, page = [], None, 1
        while comments is None or len(comments) == 100:  # noqa: PLR2004
            r = self.session.get(
                f"{self.s.api_url}/repos/{self.s.repository}/issues/{self.s.pr_num()}/comments",
                params={"per_page": 100, "page": page},
                headers={"Authorization": f"Bearer {self.s.token}", "Accept": "application/vnd.github+json"},
                timeout=10,
            )
            r.raise_for_status()
            comments = parse_obj_as(list[GithubComment], r.json())
            all_comments.extend(comments)
            page += 1
        return [c for c in all_comments if c.is_bot_comment()]

    def get_file(self, ref: str) -> Response:
        r = self.session.get(
            f"{self.s.api_url}/repos/{self.s.repository}/contents/{self.s.lockfile_path}",
            params={"ref": ref},
            headers={"Authorization": f"Bearer {self.s.token}", "Accept": "application/vnd.github.raw"},
            timeout=10,
            stream=True,
        )
        if r.status_code == 404:  # noqa: PLR2004
            raise FileNotFoundError(f"Lockfile {self.s.lockfile_path} not found on branch {ref}")
        r.raise_for_status()
        return r

    def delete_comment(self, comment_id: int) -> None:
        r = self.session.delete(
            f"{self.s.api_url}/repos/{self.s.repository}/issues/comments/{comment_id}",
            headers={"Authorization": f"Bearer {self.s.token}", "Accept": "application/vnd.github+json"},
        )
        r.raise_for_status()

    def upsert_comment(self, existing_comment: GithubComment | None, comment: str | None) -> None:
        if existing_comment is None and comment is None:
            return

        if existing_comment is None and comment is not None:
            print("Posting diff to new comment.")
            self.post_comment(comment)

        elif existing_comment is not None and comment is None:
            print("Deleting existing comment.")
            self.delete_comment(existing_comment.id_)

        elif existing_comment is not None and comment is not None:
            if existing_comment.body == f"{MAGIC_COMMENT_IDENTIFIER}{comment}":
                print("Content did not change, not updating existing comment.")
            else:
                print("Updating existing comment.")
                self.update_comment(existing_comment.id_, comment)
