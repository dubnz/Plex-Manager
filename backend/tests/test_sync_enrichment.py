from __future__ import annotations

from datetime import UTC, datetime
from xml.etree import ElementTree

from app.clients.plex import PlexClient, PlexMediaSummary
from app.services.sync import ManagerIndexes, ManagerInfo, _request_indexes_from_sources, _watch_stats_from_history


def test_plex_parser_sums_media_part_sizes() -> None:
    node = ElementTree.fromstring(
        """
        <Video
            ratingKey="42"
            title="Example"
            type="movie"
            year="2024"
            addedAt="1710000000"
            viewCount="3"
            lastViewedAt="1710000500"
            guid="com.plexapp.agents.imdb://tt1234567?lang=en"
        >
          <Guid id="tmdb://98765" />
          <Media>
            <Part size="1024" />
            <Part size="2048" />
          </Media>
        </Video>
        """
    )

    parsed = PlexClient("http://plex.local", "token")._parse_media_node(node)

    assert parsed.file_size_bytes == 3072
    assert parsed.imdb_id == "tt1234567"
    assert parsed.tmdb_id == 98765
    assert parsed.play_count == 3
    assert parsed.last_played == datetime.fromtimestamp(1710000500, UTC)


def test_watch_stats_aggregate_movies_and_tv_series() -> None:
    stats = _watch_stats_from_history(
        [
            {
                "media_type": "movie",
                "rating_key": "100",
                "date": 1000,
                "friendly_name": "Sam",
            },
            {
                "media_type": "episode",
                "rating_key": "episode-1",
                "grandparent_rating_key": "200",
                "date": 2000,
                "friendly_name": "Kyle",
            },
            {
                "media_type": "episode",
                "rating_key": "episode-2",
                "grandparent_rating_key": "200",
                "date": 3000,
                "user": "Alex",
            },
        ]
    )

    assert stats["100"].play_count == 1
    assert stats["100"].watched_by == {"Sam"}
    assert stats["200"].play_count == 2
    assert stats["200"].last_played == datetime.fromtimestamp(3000, UTC)
    assert stats["200"].watched_by == {"Kyle", "Alex"}


def test_request_indexes_preserve_current_source_then_fill_legacy() -> None:
    current = [
        {
            "type": "movie",
            "createdAt": "2026-06-24T07:11:44.000Z",
            "requestedBy": {"displayName": "Current User"},
            "media": {"ratingKey": "10", "externalServiceId": 5},
        }
    ]
    legacy = [
        {
            "type": "movie",
            "createdAt": "2026-06-21T10:21:56.000Z",
            "requestedBy": {"displayName": "Legacy User"},
            "media": {"ratingKey": "10", "externalServiceId": 5},
        },
        {
            "type": "tv",
            "createdAt": "2026-06-20T10:21:56.000Z",
            "requestedBy": {"plexUsername": "Show Requester"},
            "media": {"ratingKey": "20", "externalServiceId": 9},
        },
    ]

    indexes = _request_indexes_from_sources([current, legacy])

    assert indexes.find(
        rating_key="10",
        manager_kind="radarr",
        manager_id=5,
        tmdb_id=None,
        tvdb_id=None,
        imdb_id=None,
    ).requested_by == "Current User"
    assert indexes.find(
        rating_key="20",
        manager_kind="sonarr",
        manager_id=9,
        tmdb_id=None,
        tvdb_id=None,
        imdb_id=None,
    ).requested_by == "Show Requester"


def test_request_indexes_match_legacy_by_external_ids() -> None:
    legacy = [
        {
            "type": "movie",
            "createdAt": "2026-06-21T10:21:56.000Z",
            "requestedBy": {"displayName": "Movie Requester"},
            "media": {"tmdbId": 1234},
        },
        {
            "type": "tv",
            "createdAt": "2026-06-20T10:21:56.000Z",
            "requestedBy": {"displayName": "Show Requester"},
            "media": {"tvdbId": 5678},
        },
    ]

    indexes = _request_indexes_from_sources([[], legacy])

    assert indexes.find(
        rating_key="missing",
        manager_kind="none",
        manager_id=None,
        tmdb_id=1234,
        tvdb_id=None,
        imdb_id=None,
    ).requested_by == "Movie Requester"
    assert indexes.find(
        rating_key="missing",
        manager_kind="none",
        manager_id=None,
        tmdb_id=None,
        tvdb_id=5678,
        imdb_id=None,
    ).requested_by == "Show Requester"


def test_manager_indexes_match_by_external_ids() -> None:
    indexes = ManagerIndexes()
    indexes.add(
        title="Manager Title",
        year=2026,
        info=ManagerInfo(id=42, file_size_bytes=123, available=True, tmdb_id=9876),
    )
    item = PlexMediaSummary(
        rating_key="plex-1",
        title="Plex Title",
        media_type="movie",
        year=2026,
        added_at=datetime.fromtimestamp(1710000000, UTC),
        thumb=None,
        file_size_bytes=0,
        tmdb_id=9876,
    )

    assert indexes.find(item).id == 42
