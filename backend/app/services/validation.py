from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.clients.base import ApiClientError
from app.clients.plex import PlexClient
from app.clients.radarr import RadarrClient
from app.clients.seerr import SeerrClient
from app.clients.sonarr import SonarrClient
from app.clients.tautulli import TautulliClient
from app.core.config import Settings
from app.models import ConnectionValidationResponse, IntegrationStatus
from app.services.configuration import is_placeholder


async def validate_connections(settings: Settings) -> ConnectionValidationResponse:
    results = [
        await _validate_plex(settings),
        await _validate_tautulli(settings),
        await _validate_sonarr(settings),
        await _validate_radarr(settings),
        await _validate_seerr(settings),
    ]
    return ConnectionValidationResponse(integrations=results)


async def _guarded(name: str, operation: Callable[[], Awaitable[str]]) -> IntegrationStatus:
    try:
        detail = await operation()
        return IntegrationStatus(name=name, state="ok", detail=detail)
    except ApiClientError as exc:
        return IntegrationStatus(name=name, state="error", detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive for external services
        return IntegrationStatus(name=name, state="error", detail=f"{type(exc).__name__}: {exc}")


async def _validate_plex(settings: Settings) -> IntegrationStatus:
    if is_placeholder(settings.plex_token):
        return IntegrationStatus(name="Plex", state="missing", detail="Enter a real Plex token.")

    async def operation() -> str:
        libraries = await PlexClient(settings.plex_url, settings.plex_token).list_libraries()
        names = {library.title for library in libraries}
        selected = set(settings.plex_library_names)
        missing = sorted(selected - names)
        if missing:
            return f"Connected. Missing selected libraries: {', '.join(missing)}."
        return f"Connected. Found selected libraries: {', '.join(settings.plex_library_names)}."

    return await _guarded("Plex", operation)


async def _validate_tautulli(settings: Settings) -> IntegrationStatus:
    if is_placeholder(settings.tautulli_api_key):
        return IntegrationStatus(name="Tautulli", state="missing", detail="Enter a real Tautulli API key.")

    async def operation() -> str:
        history = await TautulliClient(settings.tautulli_url, settings.tautulli_api_key).get_history(length=1)
        return f"Connected. History endpoint returned {len(history)} row(s)."

    return await _guarded("Tautulli", operation)


async def _validate_sonarr(settings: Settings) -> IntegrationStatus:
    if is_placeholder(settings.sonarr_api_key):
        return IntegrationStatus(name="Sonarr", state="missing", detail="Enter a real Sonarr API key.")

    async def operation() -> str:
        series = await SonarrClient(settings.sonarr_url, settings.sonarr_api_key).list_series()
        return f"Connected. Found {len(series)} series."

    return await _guarded("Sonarr", operation)


async def _validate_radarr(settings: Settings) -> IntegrationStatus:
    if is_placeholder(settings.radarr_api_key):
        return IntegrationStatus(name="Radarr", state="missing", detail="Enter a real Radarr API key.")

    async def operation() -> str:
        movies = await RadarrClient(settings.radarr_url, settings.radarr_api_key).list_movies()
        return f"Connected. Found {len(movies)} movies."

    return await _guarded("Radarr", operation)


async def _validate_seerr(settings: Settings) -> IntegrationStatus:
    if settings.seerr_kind not in {"overseerr", "jellyseerr"}:
        return IntegrationStatus(name="Seerr", state="missing", detail="Choose Overseerr or Jellyseerr.")
    if is_placeholder(settings.seerr_api_key):
        return IntegrationStatus(name="Seerr", state="missing", detail="Enter a real Seerr API key.")

    async def operation() -> str:
        requests = await SeerrClient(settings.seerr_url, settings.seerr_api_key, settings.seerr_kind).list_requests(take=1)
        return f"Connected to {settings.seerr_kind}. Requests endpoint returned {len(requests)} row(s)."

    return await _guarded("Seerr", operation)

