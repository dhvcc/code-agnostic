"""Tests for standalone skill install source resolution."""

from pathlib import Path
import subprocess

import pytest

from code_agnostic.skills import install_sources
from code_agnostic.skills.install_sources import (
    SkillInstallSourceError,
    parse_skill_install_source,
    resolve_skill_install_source,
)


def _legacy_skill(path: Path, content: str = "legacy skill\n") -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(content, encoding="utf-8")
    return path


def _bundle_skill(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "meta.yaml").write_text(
        "spec_version: v1\nkind: skill\nname: bundle-skill\n",
        encoding="utf-8",
    )
    (path / "prompt.md").write_text("bundle skill\n", encoding="utf-8")
    return path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _committed_repo(repo: Path) -> Path:
    repo.mkdir()
    subprocess.run(
        ["git", "init", str(repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    return repo


def test_resolve_local_legacy_skill_directory(tmp_path: Path) -> None:
    source = _legacy_skill(tmp_path / "my-skill")

    resolution = resolve_skill_install_source(source)

    assert resolution.skill_dirs == (source.resolve(),)
    assert resolution.candidates[0].name == "my-skill"
    assert resolution.checkout_dir is None


def test_resolve_local_bundle_skill_directory(tmp_path: Path) -> None:
    source = _bundle_skill(tmp_path / "bundle-skill")

    resolution = resolve_skill_install_source(source)

    assert resolution.skill_dirs == (source.resolve(),)
    assert resolution.candidates[0].name == "bundle-skill"


def test_parse_github_sources() -> None:
    shorthand = parse_skill_install_source("openai/codex")
    repo_url = parse_skill_install_source("https://github.com/openai/codex")
    tree_url = parse_skill_install_source(
        "https://github.com/acme/skills/tree/main/packs/review"
    )

    assert shorthand.kind == "github"
    assert shorthand.clone_url == "https://github.com/openai/codex.git"
    assert repo_url.clone_url == "https://github.com/openai/codex.git"
    assert tree_url.clone_url == "https://github.com/acme/skills.git"
    assert tree_url.tree_parts == ("main", "packs", "review")


def test_resolve_local_git_repo_uses_working_tree(
    tmp_path: Path,
) -> None:
    repo = _committed_repo(tmp_path / "repo")
    skill = _legacy_skill(repo / "skills" / "review", "committed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add skill")
    (skill / "SKILL.md").write_text("uncommitted\n", encoding="utf-8")

    resolution = resolve_skill_install_source(repo)

    assert resolution.checkout_dir is None
    assert resolution.work_dir is None
    assert resolution.skill_dirs == ((repo / "skills" / "review").resolve(),)
    assert (resolution.skill_dirs[0] / "SKILL.md").read_text(encoding="utf-8") == (
        "uncommitted\n"
    )


def test_multiple_candidates_without_selector_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _legacy_skill(source / "skills" / "alpha")
    _legacy_skill(source / "skills" / "beta")

    with pytest.raises(SkillInstallSourceError) as exc_info:
        resolve_skill_install_source(source)

    message = str(exc_info.value)
    assert "Multiple skill candidates found" in message
    assert "skills/alpha" in message
    assert "skills/beta" in message
    assert "--skill" in message


def test_repeatable_selectors_choose_multiple_candidates(tmp_path: Path) -> None:
    source = tmp_path / "source"
    alpha = _legacy_skill(source / "skills" / "alpha")
    beta = _legacy_skill(source / "skills" / "beta")

    resolution = resolve_skill_install_source(
        source,
        skill_selectors=["beta", "skills/alpha"],
    )

    assert resolution.skill_dirs == (beta.resolve(), alpha.resolve())


def test_selector_name_ambiguity_requires_candidate_path(tmp_path: Path) -> None:
    source = tmp_path / "source"
    first = _legacy_skill(source / "packs" / "one" / "review")
    second = _legacy_skill(source / "packs" / "two" / "review")

    with pytest.raises(SkillInstallSourceError) as exc_info:
        resolve_skill_install_source(source, skill_selectors=["review"])

    assert "Skill selector is ambiguous" in str(exc_info.value)

    resolution = resolve_skill_install_source(
        source,
        skill_selectors=["packs/two/review"],
    )
    assert resolution.skill_dirs == (second.resolve(),)
    assert first.resolve() not in resolution.skill_dirs


def test_remote_resolution_failure_cleans_temporary_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _committed_repo(tmp_path / "repo")
    _legacy_skill(repo / "skills" / "alpha")
    _legacy_skill(repo / "skills" / "beta")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add skills")
    temp_checkout_root = tmp_path / "resolver-temp"

    def fake_mkdtemp(prefix: str) -> str:
        temp_checkout_root.mkdir()
        return str(temp_checkout_root)

    monkeypatch.setattr(install_sources.tempfile, "mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(
        install_sources,
        "_parse_github_source",
        lambda raw: install_sources.ParsedSkillInstallSource(
            raw=raw,
            kind="github",
            clone_url=str(repo),
        ),
    )

    with pytest.raises(
        SkillInstallSourceError, match="Multiple skill candidates found"
    ):
        resolve_skill_install_source("remote-source")

    assert not temp_checkout_root.exists()
