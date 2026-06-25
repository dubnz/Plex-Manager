from __future__ import annotations

from app.services.duplicate_analysis import (
    DeletableVersion,
    build_versions,
    classify_location,
    classify_quality_impact,
    find_deletable,
    parse_episode,
    parse_quality,
    parse_resolution,
)


def _dv(local_q: str, nas_q: str) -> DeletableVersion:
    return DeletableVersion(
        identity="S01E01",
        local_path="/mnt/local/tv/x.mkv",
        local_size=10,
        local_quality=local_q,
        protected_path="/mnt/remote-tv/x.mkv",
        protected_quality=nas_q,
    )


# Neutral example prefixes — the matching logic is prefix-agnostic, so these
# stand in for any local vs protected layout without encoding a real deployment.
LOCAL = ("/mnt/local/movies", "/mnt/local/tv")
PROTECTED = ("/mnt/remote-movies", "/mnt/remote-tv")


def _show_local(ep: int) -> str:
    return (
        f"/mnt/local/tv/Example Show (2024)/Season 01/"
        f"Example Show (2024) - S01E{ep:02d} - Title [WEBDL-2160p][HDR10][EAC3 Atmos 5.1][h265]-X.mkv"
    )


def _show_nas(ep: int) -> str:
    return (
        f"/mnt/remote-tv/Example Show/Season 01/"
        f"Example Show - S01E{ep:02d} - Title HDTV-720p.mkv"
    )


# --- location ---

def test_classify_location():
    assert classify_location("/mnt/local/tv/x.mkv", LOCAL, PROTECTED) == "local"
    assert classify_location("/mnt/remote-tv/TV/x.mkv", LOCAL, PROTECTED) == "protected"
    assert classify_location("/mnt/archive/x.mkv", LOCAL, PROTECTED) == "other"


# --- quality parsing ---

def test_parse_quality_resolution_and_source():
    assert parse_quality("Show - S01E01 [WEBDL-2160p][HDR10][h265]-X.mkv") == "WEBDL-2160p HDR10"
    assert parse_quality("Show - S01E01 HDTV-720p.mkv") == "HDTV-720p"
    assert parse_quality("Movie (2002) [Remux-2160p][DV HDR10Plus].mp4") == "Remux-2160p DV"
    assert parse_quality("Movie [Bluray-1080p][DTS 5.1][x264].mkv") == "Bluray-1080p"


def test_parse_quality_unknown():
    assert parse_quality("random_file.mkv") == "unknown"


# --- episode parsing ---

def test_parse_episode_single():
    assert parse_episode("Show - S01E03 - Title.mkv") == (1, (3,))


def test_parse_episode_multi():
    assert parse_episode("Show - S02E05E06 - Title.mkv") == (2, (5, 6))


def test_parse_episode_none():
    assert parse_episode("Some Movie (2019).mkv") == (None, ())


def test_parse_episode_nxnn_format():
    assert parse_episode("The Simpsons - 1x01 - Roasting on an Open Fire.mkv") == (1, (1,))
    assert parse_episode("Show - 12x05 - Title.mkv") == (12, (5,))


def test_parse_episode_resolution_not_mistaken_for_episode():
    # 1920x1080 in a name must NOT parse as season 19 / episode 20 etc.
    assert parse_episode("Movie 1920x1080 BluRay.mkv") == (None, ())


def test_cross_format_matching_sxxexx_vs_nxnn():
    # Local uses 1x01, NAS uses S01E01 — same episode, must match.
    local = "/mnt/local/tv/Show/Season 01/Show - 1x01 - Title [WEBDL-1080p].mkv"
    nas = "/mnt/remote-tv/Show/Season 01/Show - S01E01 - Title HDTV-720p.mkv"
    versions = build_versions(
        [{"path": local, "size": 100}, {"path": nas, "size": 50}],
        "show",
        LOCAL,
        PROTECTED,
    )
    deletable = find_deletable(versions, "show")
    assert len(deletable) == 1
    assert deletable[0].local_path == local


# --- SAFETY: protected files are never deletable ---

def test_protected_file_never_deletable():
    versions = build_versions(
        [
            {"path": _show_local(1), "size": 100},
            {"path": _show_nas(1), "size": 50},
        ],
        "show",
        LOCAL,
        PROTECTED,
    )
    deletable = find_deletable(versions, "show")
    assert len(deletable) == 1
    # Only the LOCAL path is ever the delete target.
    assert deletable[0].local_path == _show_local(1)
    assert deletable[0].protected_path == _show_nas(1)
    assert all(d.local_path.startswith("/mnt/local") for d in deletable)


# --- SAFETY: partial overlap only deletes matched episodes ---

def test_partial_overlap_only_matched_episodes():
    # Local has E01, E02, E03; NAS only has E01 and E03.
    versions = build_versions(
        [
            {"path": _show_local(1), "size": 10},
            {"path": _show_local(2), "size": 20},
            {"path": _show_local(3), "size": 30},
            {"path": _show_nas(1), "size": 5},
            {"path": _show_nas(3), "size": 7},
        ],
        "show",
        LOCAL,
        PROTECTED,
    )
    deletable = find_deletable(versions, "show")
    identities = sorted(d.identity for d in deletable)
    assert identities == ["S01E01", "S01E03"]  # E02 NOT deletable (no NAS copy)
    assert sum(d.local_size for d in deletable) == 40  # 10 + 30, not E02's 20


# --- SAFETY: no overlap => nothing deletable ---

def test_no_episode_overlap_nothing_deletable():
    versions = build_versions(
        [
            {"path": _show_local(1), "size": 10},  # S01E01 local
            {"path": _show_nas(5), "size": 5},     # S01E05 nas only
        ],
        "show",
        LOCAL,
        PROTECTED,
    )
    assert find_deletable(versions, "show") == []


# --- SAFETY: multi-episode local file needs ALL its episodes on NAS ---

def test_multi_episode_local_requires_all_present():
    multi = (
        "/mnt/local/tv/Show/Season 01/Show - S01E01E02 - Title [WEBDL-1080p].mkv"
    )
    nas_e1 = "/mnt/remote-tv/TV/Show/Season 01/Show - S01E01 - Title HDTV-720p.mkv"
    versions = build_versions(
        [{"path": multi, "size": 100}, {"path": nas_e1, "size": 40}],
        "show",
        LOCAL,
        PROTECTED,
    )
    # Only E01 on NAS, but local file also contains E02 -> not safe to delete.
    assert find_deletable(versions, "show") == []


# --- quality is surfaced for both sides ---

def test_quality_surfaced():
    versions = build_versions(
        [
            {"path": _show_local(1), "size": 10},
            {"path": _show_nas(1), "size": 5},
        ],
        "show",
        LOCAL,
        PROTECTED,
    )
    d = find_deletable(versions, "show")[0]
    assert d.local_quality == "WEBDL-2160p HDR10"
    assert d.protected_quality == "HDTV-720p"


# --- movies ---

def test_movie_local_with_nas_copy_is_deletable():
    versions = build_versions(
        [
            {"path": "/mnt/local/movies/Inception (2010)/Inception [Bluray-1080p].mkv", "size": 8000},
            {"path": "/mnt/remote-movies/Movies/Inception (2010)/Inception 720p.mkv", "size": 4000},
        ],
        "movie",
        LOCAL,
        PROTECTED,
    )
    deletable = find_deletable(versions, "movie")
    assert len(deletable) == 1
    assert deletable[0].identity == "movie"
    assert deletable[0].local_path.startswith("/mnt/local/movies")
    assert deletable[0].protected_path.startswith("/mnt/remote-movies")


def test_movie_local_only_not_deletable():
    versions = build_versions(
        [{"path": "/mnt/local/movies/Solo (2018)/Solo [Bluray-1080p].mkv", "size": 8000}],
        "movie",
        LOCAL,
        PROTECTED,
    )
    assert find_deletable(versions, "movie") == []


# --- quality impact classification ---

def test_parse_resolution():
    assert parse_resolution("WEBDL-2160p HDR10") == 2160
    assert parse_resolution("HDTV-720p") == 720
    assert parse_resolution("Bluray-1080p") == 1080
    assert parse_resolution("unknown") is None


def test_quality_impact_downgrade():
    assert classify_quality_impact([_dv("Remux-2160p DV", "WEBDL-1080p")]) == "downgrade"


def test_quality_impact_same():
    assert classify_quality_impact([_dv("WEBDL-1080p", "Bluray-1080p")]) == "same"


def test_quality_impact_nas_better():
    assert classify_quality_impact([_dv("HDTV-720p", "WEBDL-1080p")]) == "nas_better"


def test_quality_impact_unknown():
    assert classify_quality_impact([_dv("WEBDL-1080p", "unknown")]) == "unknown"


def test_quality_impact_any_downgrade_wins():
    # One downgrade episode among same-res ones flags the whole item.
    versions = [
        _dv("WEBDL-1080p", "WEBDL-1080p"),
        _dv("WEBDL-2160p", "WEBDL-1080p"),  # downgrade
    ]
    assert classify_quality_impact(versions) == "downgrade"


def test_quality_impact_mixed_same_and_nas_better_is_same():
    versions = [
        _dv("WEBDL-1080p", "WEBDL-1080p"),  # same
        _dv("HDTV-720p", "WEBDL-1080p"),    # nas better
    ]
    assert classify_quality_impact(versions) == "same"
