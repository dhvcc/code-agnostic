"""Resolve skill install sources into local skill directories."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import unquote, urlparse

from code_agnostic.errors import SyncAppError

_GITHUB_SHORTHAND_RE = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)$"
)


class SkillInstallSourceError(SyncAppError):
    """Raised when a skill install source cannot be resolved."""


@dataclass(frozen=True)
class ParsedSkillInstallSource:
    raw: str
    kind: str
    path: Path | None = None
    clone_url: str | None = None
    tree_parts: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillInstallCandidate:
    name: str
    path: Path
    relative_path: str


@dataclass(frozen=True)
class SkillInstallResolution:
    source: str
    root: Path
    skill_dirs: tuple[Path, ...]
    candidates: tuple[SkillInstallCandidate, ...]
    checkout_dir: Path | None = None
    work_dir: Path | None = None


def parse_skill_install_source(source: str | Path) -> ParsedSkillInstallSource:
    """Parse a local path or supported GitHub source."""

    raw = str(source)
    path = Path(raw).expanduser()
    if path.exists():
        return ParsedSkillInstallSource(
            raw=raw,
            kind="local",
            path=path.resolve(),
        )

    github_source = _parse_github_source(raw)
    if github_source is not None:
        return github_source

    if urlparse(raw).scheme:
        raise SkillInstallSourceError(f"Unsupported skill source URL: {raw}")

    raise SkillInstallSourceError(f"Skill source does not exist: {path}")


def resolve_skill_install_source(
    source: str | Path,
    *,
    skill_selectors: list[str] | tuple[str, ...] = (),
    work_dir: Path | None = None,
) -> SkillInstallResolution:
    """Resolve a source into selected local skill directories.

    Remote sources are cloned into ``work_dir`` when provided, or into a new
    temporary directory. The caller owns cleanup for returned paths.
    """

    parsed = parse_skill_install_source(source)
    checkout_dir: Path | None = None
    checkout_work_dir: Path | None = None

    try:
        if parsed.kind == "local":
            if parsed.path is None:
                raise SkillInstallSourceError(
                    f"Invalid local skill source: {parsed.raw}"
                )
            root = parsed.path
        elif parsed.kind == "github":
            if parsed.clone_url is None:
                raise SkillInstallSourceError(
                    f"Invalid GitHub skill source: {parsed.raw}"
                )
            checkout_dir, checkout_work_dir = _clone_git_source(
                parsed.clone_url, work_dir=work_dir
            )
            root = checkout_dir
            if parsed.tree_parts:
                subpath = _checkout_tree_parts(checkout_dir, parsed.tree_parts)
                root = checkout_dir / subpath
        else:
            raise SkillInstallSourceError(f"Unsupported skill source: {parsed.raw}")

        candidates = _discover_skill_candidates(root)
        selected = _select_candidates(parsed.raw, candidates, skill_selectors)
        return SkillInstallResolution(
            source=parsed.raw,
            root=root,
            skill_dirs=tuple(candidate.path for candidate in selected),
            candidates=tuple(selected),
            checkout_dir=checkout_dir,
            work_dir=checkout_work_dir,
        )
    except Exception:
        if checkout_work_dir is not None and work_dir is None:
            _remove_tree(checkout_work_dir)
        raise


def cleanup_skill_install_resolution(resolution: SkillInstallResolution) -> None:
    """Remove temporary checkout files created for a resolution."""

    if resolution.work_dir is not None:
        _remove_tree(resolution.work_dir)


def _parse_github_source(raw: str) -> ParsedSkillInstallSource | None:
    shorthand = _GITHUB_SHORTHAND_RE.match(raw)
    if shorthand is not None:
        owner = shorthand.group("owner")
        repo = shorthand.group("repo").removesuffix(".git")
        return ParsedSkillInstallSource(
            raw=raw,
            kind="github",
            clone_url=_github_clone_url(owner, repo),
        )

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
        return None

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise SkillInstallSourceError(f"Invalid GitHub skill source: {raw}")

    owner = parts[0]
    repo = parts[1].removesuffix(".git")
    if len(parts) == 2:
        return ParsedSkillInstallSource(
            raw=raw,
            kind="github",
            clone_url=_github_clone_url(owner, repo),
        )

    if len(parts) >= 4 and parts[2] == "tree":
        tree_parts = tuple(parts[3:])
        _validate_tree_parts(raw, tree_parts)
        return ParsedSkillInstallSource(
            raw=raw,
            kind="github",
            clone_url=_github_clone_url(owner, repo),
            tree_parts=tree_parts,
        )

    raise SkillInstallSourceError(
        "Unsupported GitHub skill source path. Expected a repository URL or "
        f"/tree/<ref>/<path>: {raw}"
    )


def _github_clone_url(owner: str, repo: str) -> str:
    return f"https://github.com/{owner}/{repo}.git"


def _validate_tree_parts(raw: str, parts: tuple[str, ...]) -> None:
    if not parts or any(part in {"", ".."} for part in parts):
        raise SkillInstallSourceError(f"Invalid GitHub tree source: {raw}")


def _clone_git_source(source: str, *, work_dir: Path | None) -> tuple[Path, Path]:
    checkout_work_dir = (
        work_dir.expanduser().resolve()
        if work_dir is not None
        else Path(tempfile.mkdtemp(prefix="code-agnostic-skill-source-"))
    )
    checkout_work_dir.mkdir(parents=True, exist_ok=True)
    checkout_dir = _unique_child(checkout_work_dir, "checkout")
    try:
        _run_git(["clone", "--quiet", source, str(checkout_dir)])
        return checkout_dir, checkout_work_dir
    except Exception:
        if work_dir is None:
            _remove_tree(checkout_work_dir)
        raise


def _checkout_tree_parts(checkout_dir: Path, tree_parts: tuple[str, ...]) -> Path:
    for ref_part_count in range(len(tree_parts), 0, -1):
        ref = "/".join(tree_parts[:ref_part_count])
        result = _run_git(
            ["checkout", "--quiet", ref],
            cwd=checkout_dir,
            check=False,
        )
        if result.returncode == 0:
            path_parts = tree_parts[ref_part_count:]
            subpath = Path(*path_parts) if path_parts else Path()
            target = checkout_dir / subpath
            if not target.exists():
                raise SkillInstallSourceError(
                    f"GitHub tree path does not exist after checkout: {subpath}"
                )
            return subpath

    raise SkillInstallSourceError(
        "Could not check out a ref from GitHub tree source: " + "/".join(tree_parts)
    )


def _run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SkillInstallSourceError(
            "git is required to resolve this skill source"
        ) from exc

    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise SkillInstallSourceError(detail)
    return result


def _unique_child(parent: Path, name: str) -> Path:
    candidate = parent / name
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = parent / f"{name}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def _remove_tree(path: Path) -> None:
    def handle_readonly(
        func: object,
        path_string: str,
        _exc_info: object,
    ) -> None:
        os.chmod(path_string, stat.S_IWRITE)
        func(path_string)  # type: ignore[operator]

    shutil.rmtree(path, onerror=handle_readonly)


def _discover_skill_candidates(root: Path) -> list[SkillInstallCandidate]:
    if not root.exists():
        raise SkillInstallSourceError(f"Skill source path does not exist: {root}")
    if not root.is_dir():
        raise SkillInstallSourceError(f"Skill source is not a directory: {root}")
    if _is_skill_source(root):
        return [_candidate_for(root, root)]

    candidates: list[SkillInstallCandidate] = []
    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = [
            dirname for dirname in dirnames if dirname not in {".git", "__pycache__"}
        ]
        path = Path(dirpath)
        if _is_skill_source(path):
            candidates.append(_candidate_for(path, root))
            dirnames[:] = []

    return sorted(candidates, key=lambda candidate: candidate.relative_path)


def _is_skill_source(path: Path) -> bool:
    return path.is_dir() and (
        (path / "SKILL.md").exists()
        or ((path / "meta.yaml").exists() and (path / "prompt.md").exists())
    )


def _candidate_for(path: Path, root: Path) -> SkillInstallCandidate:
    relative_path = "." if path == root else path.relative_to(root).as_posix()
    return SkillInstallCandidate(
        name=path.name,
        path=path,
        relative_path=relative_path,
    )


def _select_candidates(
    source: str,
    candidates: list[SkillInstallCandidate],
    selectors: list[str] | tuple[str, ...],
) -> list[SkillInstallCandidate]:
    if not candidates:
        raise SkillInstallSourceError(f"No skill directories found in source: {source}")

    if not selectors:
        if len(candidates) == 1:
            return candidates
        raise SkillInstallSourceError(
            "Multiple skill candidates found in source: "
            + _format_candidates(candidates)
            + ". Pass --skill with one or more candidate names or paths."
        )

    selected: list[SkillInstallCandidate] = []
    selected_paths: set[Path] = set()
    for selector in selectors:
        normalized = _normalize_selector(selector)
        matches = [
            candidate
            for candidate in candidates
            if normalized in {candidate.name, candidate.relative_path}
        ]
        if not matches:
            raise SkillInstallSourceError(
                f"Skill selector did not match any candidates: {selector}. "
                f"Available candidates: {_format_candidates(candidates)}"
            )
        if len(matches) > 1:
            raise SkillInstallSourceError(
                f"Skill selector is ambiguous: {selector}. "
                f"Matched candidates: {_format_candidates(matches)}. "
                "Pass --skill with a candidate path."
            )
        match = matches[0]
        if match.path not in selected_paths:
            selected.append(match)
            selected_paths.add(match.path)

    return selected


def _normalize_selector(selector: str) -> str:
    normalized = selector.strip().replace("\\", "/").strip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized:
        raise SkillInstallSourceError("Skill selector cannot be empty")
    return normalized


def _format_candidates(candidates: list[SkillInstallCandidate]) -> str:
    return ", ".join(candidate.relative_path for candidate in candidates)
