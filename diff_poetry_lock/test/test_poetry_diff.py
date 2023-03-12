from operator import attrgetter
from textwrap import dedent
from typing import Any

import pytest
import requests_mock
from _pytest.monkeypatch import MonkeyPatch
from requests_mock import Mocker

from diff_poetry_lock.github import MAGIC_COMMENT_IDENTIFIER
from diff_poetry_lock.run_poetry import PackageSummary, diff, do_diff, format_comment, load_packages, main
from diff_poetry_lock.settings import Settings

TESTFILE_1 = "diff_poetry_lock/test/res/poetry1.lock"
TESTFILE_2 = "diff_poetry_lock/test/res/poetry2.lock"


@pytest.fixture()
def cfg() -> Settings:
    return create_settings()


@pytest.fixture()
def data1() -> bytes:
    return load_file(TESTFILE_1)


@pytest.fixture()
def data2() -> bytes:
    return load_file(TESTFILE_2)


def test_settings(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_REF", "refs/pull/1/merge")
    monkeypatch.setenv("GITHUB_REPOSITORY", "account/repo")
    monkeypatch.setenv("INPUT_GITHUB_TOKEN", "foobar")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")

    s = Settings()

    assert s.pr_num() == "1"


def test_settings_not_pr(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_REF", "refs/pull/1/merge")
    monkeypatch.setenv("GITHUB_REPOSITORY", "account/repo")
    monkeypatch.setenv("INPUT_GITHUB_TOKEN", "foobar")

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0


def test_diff() -> None:
    old = load_packages(TESTFILE_1)
    new = load_packages(TESTFILE_2)

    summary: list[PackageSummary] = sorted(diff(old, new), key=attrgetter("name"))

    expected = [
        PackageSummary(name="certifi", old_version="2022.12.7", new_version="2022.12.7"),
        PackageSummary(name="charset-normalizer", old_version="3.1.0", new_version="3.1.0"),
        PackageSummary(name="idna", old_version="3.4", new_version="3.4"),
        PackageSummary(name="pydantic", old_version="1.10.6", new_version=None),
        PackageSummary(name="requests", old_version="2.28.2", new_version="2.28.2"),
        PackageSummary(name="typing-extensions", old_version="4.5.0", new_version=None),
        PackageSummary(name="urllib3", old_version="1.26.15", new_version="1.26.14"),
    ]
    assert summary == expected

    expected_comment = """\
    ### Detected 3 changes to dependencies in Poetry lockfile

    Removed **pydantic** (1.10.6)
    Removed **typing-extensions** (4.5.0)
    Updated **urllib3** (1.26.15 -> 1.26.14)

    *(0 added, 2 removed, 1 updated, 4 not changed)*"""
    assert format_comment(summary) == dedent(expected_comment)


def test_diff_2() -> None:
    old = load_packages(TESTFILE_2)
    new = load_packages(TESTFILE_1)

    summary: list[PackageSummary] = sorted(diff(old, new), key=attrgetter("name"))

    expected = [
        PackageSummary(name="certifi", old_version="2022.12.7", new_version="2022.12.7"),
        PackageSummary(name="charset-normalizer", old_version="3.1.0", new_version="3.1.0"),
        PackageSummary(name="idna", old_version="3.4", new_version="3.4"),
        PackageSummary(name="pydantic", old_version=None, new_version="1.10.6"),
        PackageSummary(name="requests", old_version="2.28.2", new_version="2.28.2"),
        PackageSummary(name="typing-extensions", old_version=None, new_version="4.5.0"),
        PackageSummary(name="urllib3", old_version="1.26.14", new_version="1.26.15"),
    ]
    assert summary == expected

    expected_comment = """\
    ### Detected 3 changes to dependencies in Poetry lockfile

    Added **pydantic** (1.10.6)
    Added **typing-extensions** (4.5.0)
    Updated **urllib3** (1.26.14 -> 1.26.15)

    *(2 added, 0 removed, 1 updated, 4 not changed)*"""
    assert format_comment(summary) == dedent(expected_comment)


def test_diff_no_changes() -> None:
    old = load_packages(TESTFILE_2)
    new = load_packages(TESTFILE_2)

    summary: list[PackageSummary] = sorted(diff(old, new), key=attrgetter("name"))

    expected = [
        PackageSummary(name="certifi", old_version="2022.12.7", new_version="2022.12.7"),
        PackageSummary(name="charset-normalizer", old_version="3.1.0", new_version="3.1.0"),
        PackageSummary(name="idna", old_version="3.4", new_version="3.4"),
        PackageSummary(name="requests", old_version="2.28.2", new_version="2.28.2"),
        PackageSummary(name="urllib3", old_version="1.26.14", new_version="1.26.14"),
    ]
    assert summary == expected
    assert format_comment(summary) is None


def test_file_loading_missing_file_base_ref(cfg: Settings) -> None:
    with requests_mock.Mocker() as m:
        m.get(
            f"https://api.github.com/repos/{cfg.repository}/contents/{cfg.lockfile_path}?ref={cfg.base_ref}",
            headers={"Authorization": f"Bearer {cfg.token}", "Accept": "application/vnd.github.raw"},
            status_code=404,
        )

        with pytest.raises(FileNotFoundError):
            do_diff(cfg)


def test_file_loading_missing_file_head_ref(cfg: Settings, data1: bytes) -> None:
    with requests_mock.Mocker() as m:
        m.get(
            f"https://api.github.com/repos/{cfg.repository}/contents/{cfg.lockfile_path}?ref={cfg.base_ref}",
            headers={"Authorization": f"Bearer {cfg.token}", "Accept": "application/vnd.github.raw"},
            content=data1,
        )
        m.get(
            f"https://api.github.com/repos/{cfg.repository}/contents/{cfg.lockfile_path}?ref={cfg.ref}",
            headers={"Authorization": f"Bearer {cfg.token}", "Accept": "application/vnd.github.raw"},
            status_code=404,
        )

        with pytest.raises(FileNotFoundError):
            do_diff(cfg)


def test_e2e_no_diff_existing_comment(cfg: Settings, data1: bytes) -> None:
    with requests_mock.Mocker() as m:
        mock_get_file(m, cfg, data1, cfg.base_ref)
        mock_get_file(m, cfg, data1, cfg.ref)
        comments = [
            {"body": "foobar", "id": 1334, "user": {"id": 123}},
            {"body": "foobar", "id": 1335, "user": {"id": 41898282}},
            {"body": f"{MAGIC_COMMENT_IDENTIFIER}", "id": 1336, "user": {"id": 123}},
            {"body": f"{MAGIC_COMMENT_IDENTIFIER}foobar", "id": 1337, "user": {"id": 41898282}},
        ]
        mock_list_comments(m, cfg, comments)
        m.delete(
            f"https://api.github.com/repos/{cfg.repository}/issues/comments/1337",
            headers={"Authorization": f"Bearer {cfg.token}", "Accept": "application/vnd.github.raw"},
        )

        do_diff(cfg)


def test_e2e_no_diff_inexisting_comment(cfg: Settings, data1: bytes) -> None:
    with requests_mock.Mocker() as m:
        mock_get_file(m, cfg, data1, cfg.base_ref)
        mock_get_file(m, cfg, data1, cfg.ref)
        mock_list_comments(m, cfg, [])

        do_diff(cfg)


def test_e2e_diff_inexisting_comment(cfg: Settings, data1: bytes, data2: bytes) -> None:
    summary = format_comment(diff(load_packages(TESTFILE_2), load_packages(TESTFILE_1)))

    with requests_mock.Mocker() as m:
        mock_get_file(m, cfg, data1, cfg.base_ref)
        mock_get_file(m, cfg, data2, cfg.ref)
        mock_list_comments(m, cfg, [])
        m.post(
            f"https://api.github.com/repos/{cfg.repository}/issues/{cfg.pr_num()}/comments",
            headers={"Authorization": f"Bearer {cfg.token}", "Accept": "application/vnd.github.raw"},
            json={"body": f"{MAGIC_COMMENT_IDENTIFIER}{summary}"},
        )

        do_diff(cfg)


def test_e2e_diff_existing_comment_same_data(cfg: Settings, data1: bytes, data2: bytes) -> None:
    summary = format_comment(diff(load_packages(TESTFILE_1), load_packages(TESTFILE_2)))

    with requests_mock.Mocker() as m:
        mock_get_file(m, cfg, data1, cfg.base_ref)
        mock_get_file(m, cfg, data2, cfg.ref)
        comments = [
            {"body": "foobar", "id": 1334, "user": {"id": 123}},
            {"body": "foobar", "id": 1335, "user": {"id": 41898282}},
            {"body": f"{MAGIC_COMMENT_IDENTIFIER}", "id": 1336, "user": {"id": 123}},
            {"body": f"{MAGIC_COMMENT_IDENTIFIER}{summary}", "id": 1337, "user": {"id": 41898282}},
        ]
        mock_list_comments(m, cfg, comments)

        do_diff(cfg)


def test_e2e_diff_existing_comment_different_data(cfg: Settings, data1: bytes, data2: bytes) -> None:
    summary = format_comment(diff(load_packages(TESTFILE_1), []))

    with requests_mock.Mocker() as m:
        mock_get_file(m, cfg, data1, cfg.base_ref)
        mock_get_file(m, cfg, data2, cfg.ref)
        comments = [
            {"body": "foobar", "id": 1334, "user": {"id": 123}},
            {"body": "foobar", "id": 1335, "user": {"id": 41898282}},
            {"body": f"{MAGIC_COMMENT_IDENTIFIER}", "id": 1336, "user": {"id": 123}},
            {"body": f"{MAGIC_COMMENT_IDENTIFIER}{summary}", "id": 1337, "user": {"id": 41898282}},
        ]
        mock_list_comments(m, cfg, comments)
        m.patch(
            f"https://api.github.com/repos/{cfg.repository}/issues/comments/1337",
            headers={"Authorization": f"Bearer {cfg.token}", "Accept": "application/vnd.github.raw"},
            json={"body": f"{MAGIC_COMMENT_IDENTIFIER}{summary}"},
        )

        do_diff(cfg)


def load_file(filename: str) -> bytes:
    with open(filename, "rb") as f:
        return f.read()


def mock_list_comments(m: Mocker, s: Settings, response_json: list[dict[Any, Any]]) -> None:
    m.get(
        f"https://api.github.com/repos/{s.repository}/issues/{s.pr_num()}/comments?per_page=100&page=1",
        headers={"Authorization": f"Bearer {s.token}", "Accept": "application/vnd.github.raw"},
        json=response_json,
    )


def mock_get_file(m: Mocker, s: Settings, data: bytes, ref: str) -> None:
    m.get(
        f"https://api.github.com/repos/{s.repository}/contents/{s.lockfile_path}?ref={ref}",
        headers={"Authorization": f"Bearer {s.token}", "Accept": "application/vnd.github.raw"},
        content=data,
    )


def create_settings(
    repository: str = "user/repo",
    lockfile_path: str = "poetry.lock",
    token: str = "foobar",  # noqa: S107
) -> Settings:
    return Settings(
        event_name="pull_request",
        ref="refs/pull/1/merge",
        repository=repository,
        token=token,
        base_ref="main",
        lockfile_path=lockfile_path,
    )
