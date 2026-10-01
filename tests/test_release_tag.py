"""Check manual releases against actual lightweight and annotated Git refs."""

from pathlib import Path
import subprocess

import pytest

from scripts.check_release_tag import validate_release


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


@pytest.fixture
def release_repository(tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", str(origin))
    root = tmp_path / "checkout"
    root.mkdir()
    git(root, "init", "--initial-branch=main")
    git(root, "config", "user.name", "Release test")
    git(root, "config", "user.email", "release@example.invalid")
    (root / "src/eal").mkdir(parents=True)
    (root / "src/eal/__init__.py").write_text('__version__ = "3.2.1"\n', encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "engineering-argument-language"\nversion = "3.2.1"\n',
        encoding="utf-8",
    )
    git(root, "add", ".")
    git(root, "commit", "-m", "Release")
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "origin", "main")
    return root


@pytest.mark.parametrize("annotated", [False, True])
def test_release_resolves_real_tag_to_commit(release_repository, annotated):
    root = release_repository
    tag_args = ("-a", "-m", "Version 3.2.1") if annotated else ()
    git(root, "tag", *tag_args, "v3.2.1")
    git(root, "push", "origin", "refs/tags/v3.2.1")
    commit = git(root, "rev-parse", "HEAD")
    release = validate_release(root, "v3.2.1", "refs/tags/v3.2.1", commit)
    assert release.version == "3.2.1"
    assert release.commit == commit


@pytest.mark.parametrize("tag", ["main", "--all", "v3.2.1^{commit}", "v3.2.1\nmain",
                                 "v03.2.1", "v3.2.1rc1", "../v3.2.1"])
def test_invalid_tag_is_rejected_before_git(tmp_path, tag):
    with pytest.raises(ValueError, match="stable"):
        validate_release(tmp_path, tag, f"refs/tags/{tag}", "a" * 40)


def test_branch_dispatch_cannot_publish_a_tag(tmp_path):
    with pytest.raises(ValueError, match="same release tag"):
        validate_release(tmp_path, "v3.2.1", "refs/heads/main", "a" * 40)


@pytest.mark.parametrize("sha", ["HEAD", "123", "a" * 40 + "\ncommit=other"])
def test_invalid_dispatch_sha_is_rejected_before_git(tmp_path, sha):
    with pytest.raises(ValueError, match="full GitHub commit SHA"):
        validate_release(tmp_path, "v3.2.1", "refs/tags/v3.2.1", sha)


def test_checkout_must_match_dispatch_commit(release_repository):
    with pytest.raises(ValueError, match="immutable dispatch commit"):
        validate_release(release_repository, "v3.2.1", "refs/tags/v3.2.1", "a" * 40)


def test_unmerged_tag_is_rejected(release_repository):
    root = release_repository
    git(root, "checkout", "-b", "unmerged")
    (root / "unmerged.txt").write_text("unmerged", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "Unmerged")
    git(root, "tag", "v3.2.1")
    git(root, "push", "origin", "refs/tags/v3.2.1")
    commit = git(root, "rev-parse", "HEAD")
    with pytest.raises(subprocess.CalledProcessError):
        validate_release(root, "v3.2.1", "refs/tags/v3.2.1", commit)


@pytest.mark.parametrize("file,content", [
    ("pyproject.toml", '[project]\nname="engineering-argument-language"\nversion="3.2.0"\n'),
    ("src/eal/__init__.py", '__version__ = "3.2.0"\n'),
    ("src/eal/__init__.py", '__version__ = str("3.2.1")\n'),
    ("src/eal/__init__.py", '__version__ = "3.2.1"\n__version__ = str("3.2.0")\n'),
])
def test_release_metadata_must_agree(release_repository, file, content):
    root = release_repository
    (root / file).write_text(content, encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "Wrong version")
    git(root, "tag", "v3.2.1")
    git(root, "push", "origin", "main", "refs/tags/v3.2.1")
    commit = git(root, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="agree|literal string"):
        validate_release(root, "v3.2.1", "refs/tags/v3.2.1", commit)


def test_tag_cannot_resolve_to_a_different_dispatch_commit(release_repository):
    root = release_repository
    git(root, "tag", "v3.2.1")
    git(root, "push", "origin", "refs/tags/v3.2.1")
    (root / "later.txt").write_text("later", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "Later")
    git(root, "push", "origin", "main")
    with pytest.raises(ValueError, match="dispatch commit"):
        validate_release(root, "v3.2.1", "refs/tags/v3.2.1", git(root, "rev-parse", "HEAD"))


def test_release_commit_can_precede_current_main(release_repository):
    root = release_repository
    commit = git(root, "rev-parse", "HEAD")
    git(root, "tag", "v3.2.1")
    (root / "later.txt").write_text("later", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "Later")
    git(root, "push", "origin", "main", "refs/tags/v3.2.1")
    git(root, "checkout", "--detach", commit)
    assert validate_release(root, "v3.2.1", "refs/tags/v3.2.1", commit).commit == commit


def test_moved_remote_tag_is_rejected(release_repository):
    root = release_repository
    commit = git(root, "rev-parse", "HEAD")
    git(root, "tag", "v3.2.1")
    git(root, "push", "origin", "refs/tags/v3.2.1")
    (root / "later.txt").write_text("later", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "Later")
    git(root, "tag", "-f", "v3.2.1")
    git(root, "push", "--force", "origin", "main", "refs/tags/v3.2.1")
    git(root, "tag", "-f", "v3.2.1", commit)
    git(root, "checkout", "--detach", commit)
    with pytest.raises(subprocess.CalledProcessError):
        validate_release(root, "v3.2.1", "refs/tags/v3.2.1", commit)
