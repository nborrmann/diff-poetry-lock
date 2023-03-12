import sys
import tempfile
from operator import attrgetter
from pathlib import Path

import pydantic
from poetry.core.packages.package import Package
from poetry.packages import Locker

from diff_poetry_lock.github import GithubApi
from diff_poetry_lock.settings import Settings


def load_packages(filename: str = "poetry.lock") -> list[Package]:
    l_merged = Locker(Path(filename), local_config={})
    return l_merged.locked_repository().packages


@pydantic.dataclasses.dataclass(config={"arbitrary_types_allowed": True})
class PackageSummary:
    name: str
    old_version: str | None = None
    new_version: str | None = None

    def not_changed(self) -> bool:
        return self.new_version == self.old_version

    def changed(self) -> bool:
        return not self.not_changed()

    def updated(self) -> bool:
        return self.new_version is not None and self.old_version is not None and self.changed()

    def added(self) -> bool:
        return self.new_version is not None and self.old_version is None

    def removed(self) -> bool:
        return self.new_version is None and self.old_version is not None

    def summary_line(self) -> str:
        if self.updated():
            return f"Updated **{self.name}** ({self.old_version} -> {self.new_version})"
        if self.added() and self.new_version is not None:
            return f"Added **{self.name}** ({self.new_version})"
        if self.removed() and self.old_version is not None:
            return f"Removed **{self.name}** ({self.old_version})"

        if self.new_version is None:
            raise ValueError("Inconsistent State")

        return f"Not changed **{self.name}** ({self.new_version})"


def diff(old_packages: list[Package], new_packages: list[Package]) -> list[PackageSummary]:
    merged: dict[str, PackageSummary] = {}
    for package in old_packages:
        merged[package.pretty_name] = PackageSummary(name=package.pretty_name, old_version=package.full_pretty_version)
    for package in new_packages:
        if package.pretty_name not in merged:
            merged[package.pretty_name] = PackageSummary(
                name=package.pretty_name,
                new_version=package.full_pretty_version,
            )
        else:
            merged[package.pretty_name].new_version = package.full_pretty_version

    return list(merged.values())


def post_comment(api: GithubApi, comment: str | None) -> None:
    existing_comments = api.list_comments()

    if len(existing_comments) > 1:
        print("Found more than one existing comment, only updating first comment", file=sys.stderr)

    existing_comment = existing_comments[0] if existing_comments else None
    api.upsert_comment(existing_comment, comment)


def format_comment(packages: list[PackageSummary]) -> str | None:
    added = sorted([p for p in packages if p.added()], key=attrgetter("name"))
    removed = sorted([p for p in packages if p.removed()], key=attrgetter("name"))
    updated = sorted([p for p in packages if p.updated()], key=attrgetter("name"))
    not_changed = sorted([p for p in packages if p.not_changed()], key=attrgetter("name"))

    if len(added + removed + updated) == 0:
        return None

    comment = f"### Detected {len(added + removed + updated)} changes to dependencies in Poetry lockfile\n\n"
    comment += "\n".join(p.summary_line() for p in added + removed + updated)
    comment += (
        f"\n\n*({len(added)} added, {len(removed)} removed, {len(updated)} updated, {len(not_changed)} not changed)*"
    )

    return comment


def load_lockfile(api: GithubApi, ref: str) -> list[Package]:
    r = api.get_file(ref)
    with tempfile.NamedTemporaryFile(mode="wb", delete=True) as f:
        for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)
        f.flush()

        return load_packages(f.name)


def main() -> None:
    settings = Settings()
    print(settings)
    do_diff(settings)


def do_diff(settings: Settings) -> None:
    api = GithubApi(settings)
    base_packages = load_lockfile(api, settings.base_ref)
    head_packages = load_lockfile(api, settings.ref)

    packages = diff(base_packages, head_packages)
    summary = format_comment(packages)
    post_comment(api, summary)


if __name__ == "__main__":
    main()
