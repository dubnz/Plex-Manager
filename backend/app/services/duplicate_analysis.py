"""Pure, I/O-free logic for identifying which LOCAL media files are safe to
delete because an equivalent copy exists on a PROTECTED (NAS) path.

Safety invariants (covered by tests):
- A file under a protected prefix is NEVER returned as deletable.
- For TV, a local episode is deletable only when the SAME season+episode
  exists under a protected path (per-episode, not per-show).
- A local file under neither local nor protected prefixes is ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# S01E02, s1e2, S01E02E03 (multi-episode) — capture season + all episode numbers.
_EPISODE_RE = re.compile(r"[Ss](\d{1,2})(?:[Ee]\d{1,4})+")
_EPISODE_NUMS_RE = re.compile(r"[Ee](\d{1,4})")
# Alternate numbering, e.g. "Show - 1x01 - Title" / "12x05". The \b guards avoid
# matching resolutions like 1920x1080.
_NXNN_RE = re.compile(r"\b(\d{1,2})x(\d{1,3})\b")
_RESOLUTION_RE = re.compile(r"(2160|1080|720|576|480)[pi]", re.IGNORECASE)
_SOURCE_TOKENS = (
    ("remux", "Remux"),
    ("bluray", "Bluray"),
    ("blu-ray", "Bluray"),
    ("web-dl", "WEBDL"),
    ("webdl", "WEBDL"),
    ("webrip", "WEBRip"),
    ("hdtv", "HDTV"),
    ("dvd", "DVD"),
)
_HDR_TOKENS = (
    ("dv hdr10plus", "DV"),
    ("dolby vision", "DV"),
    ("hdr10plus", "HDR10+"),
    ("hdr10", "HDR10"),
    ("hdr", "HDR"),
)

Location = str  # "local" | "protected" | "other"


@dataclass(frozen=True)
class FileVersion:
    path: str
    size: int
    location: Location
    quality: str
    season: int | None
    episodes: tuple[int, ...]  # empty for movies / unparseable


@dataclass(frozen=True)
class DeletableVersion:
    """A local file that has a matching copy on a protected path."""

    identity: str  # "S01E03" for TV, "movie" for movies
    local_path: str
    local_size: int
    local_quality: str
    protected_path: str
    protected_quality: str


def classify_location(
    path: str,
    local_prefixes: tuple[str, ...],
    protected_prefixes: tuple[str, ...],
) -> Location:
    if any(path.startswith(prefix) for prefix in local_prefixes):
        return "local"
    if any(path.startswith(prefix) for prefix in protected_prefixes):
        return "protected"
    return "other"


def parse_quality(filename: str) -> str:
    resolution_match = _RESOLUTION_RE.search(filename)
    resolution = f"{resolution_match.group(1)}p" if resolution_match else ""

    lowered = filename.lower()
    source = ""
    for token, label in _SOURCE_TOKENS:
        if token in lowered:
            source = label
            break

    hdr = ""
    for token, label in _HDR_TOKENS:
        if token in lowered:
            hdr = label
            break

    parts = []
    if source and resolution:
        parts.append(f"{source}-{resolution}")
    elif resolution:
        parts.append(resolution)
    elif source:
        parts.append(source)
    if hdr:
        parts.append(hdr)
    return " ".join(parts) if parts else "unknown"


def parse_episode(filename: str) -> tuple[int | None, tuple[int, ...]]:
    """Return (season, (episode_numbers,)).

    Handles SxxExx, multi-episode SxxExxExx, and alternate NxNN (e.g. 1x01).
    """
    match = _EPISODE_RE.search(filename)
    if match:
        season = int(match.group(1))
        episodes = tuple(int(num) for num in _EPISODE_NUMS_RE.findall(match.group(0)))
        return season, episodes
    alt = _NXNN_RE.search(filename)
    if alt:
        return int(alt.group(1)), (int(alt.group(2)),)
    return None, ()


def build_versions(
    file_versions: list[dict],
    media_type: str,
    local_prefixes: tuple[str, ...],
    protected_prefixes: tuple[str, ...],
) -> list[FileVersion]:
    versions: list[FileVersion] = []
    for entry in file_versions:
        path = entry.get("path", "")
        if not path:
            continue
        filename = path.rsplit("/", 1)[-1]
        season, episodes = (None, ()) if media_type == "movie" else parse_episode(filename)
        versions.append(
            FileVersion(
                path=path,
                size=int(entry.get("size") or 0),
                location=classify_location(path, local_prefixes, protected_prefixes),
                quality=parse_quality(filename),
                season=season,
                episodes=episodes,
            )
        )
    return versions


def find_deletable(
    versions: list[FileVersion],
    media_type: str,
) -> list[DeletableVersion]:
    """Return the local files that have an equivalent protected (NAS) copy.

    Protected files are never returned. For TV, matching is per season+episode.
    """
    local = [v for v in versions if v.location == "local"]
    protected = [v for v in versions if v.location == "protected"]
    if not local or not protected:
        return []

    if media_type == "movie":
        # The whole item is one movie; any protected copy makes the local copy
        # a safe duplicate.
        representative = protected[0]
        return [
            DeletableVersion(
                identity="movie",
                local_path=v.path,
                local_size=v.size,
                local_quality=v.quality,
                protected_path=representative.path,
                protected_quality=representative.quality,
            )
            for v in local
        ]

    # TV: index protected files by (season, episode).
    protected_by_ep: dict[tuple[int, int], FileVersion] = {}
    for v in protected:
        if v.season is None:
            continue
        for ep in v.episodes:
            protected_by_ep.setdefault((v.season, ep), v)

    deletable: list[DeletableVersion] = []
    for v in local:
        if v.season is None or not v.episodes:
            continue
        # A local file (possibly multi-episode) is deletable only if EVERY
        # episode it contains exists on a protected path.
        matches = [protected_by_ep.get((v.season, ep)) for ep in v.episodes]
        if any(m is None for m in matches):
            continue
        representative = matches[0]
        assert representative is not None  # for type-checkers; guarded above
        identity = _format_identity(v.season, v.episodes)
        deletable.append(
            DeletableVersion(
                identity=identity,
                local_path=v.path,
                local_size=v.size,
                local_quality=v.quality,
                protected_path=representative.path,
                protected_quality=representative.quality,
            )
        )
    return deletable


def _format_identity(season: int, episodes: tuple[int, ...]) -> str:
    return f"S{season:02d}" + "".join(f"E{ep:02d}" for ep in episodes)


_RES_NUM_RE = re.compile(r"(2160|1080|720|576|480)")

# Quality impact of deleting the local copy, judged by resolution.
QualityImpact = str  # "downgrade" | "same" | "nas_better" | "unknown"


def parse_resolution(quality: str) -> int | None:
    match = _RES_NUM_RE.search(quality or "")
    return int(match.group(1)) if match else None


def classify_quality_impact(deletable: list[DeletableVersion]) -> QualityImpact:
    """Worst-case resolution impact of deleting the local copies.

    Precedence is conservative: any single downgrade flags the whole item as a
    downgrade; an unresolved resolution flags it as unknown. Only items whose
    deletable files are all same-or-better on the NAS are considered safe.
    """
    if not deletable:
        return "unknown"
    saw_downgrade = saw_unknown = saw_nas_better = saw_same = False
    for d in deletable:
        local_res = parse_resolution(d.local_quality)
        nas_res = parse_resolution(d.protected_quality)
        if local_res is None or nas_res is None:
            saw_unknown = True
        elif local_res > nas_res:
            saw_downgrade = True
        elif local_res < nas_res:
            saw_nas_better = True
        else:
            saw_same = True
    if saw_downgrade:
        return "downgrade"
    if saw_unknown:
        return "unknown"
    if saw_nas_better and not saw_same:
        return "nas_better"
    return "same"
