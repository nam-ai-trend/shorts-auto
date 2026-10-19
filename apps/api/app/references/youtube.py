from __future__ import annotations

from datetime import date, timedelta
import re
from typing import TypeVar
from urllib.parse import parse_qs, urlparse

import httpx

from app.references.models import ReferenceCandidate, ReferenceSearchRequest


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")
DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)
YOUTUBE_BATCH_SIZE = 50
SEARCH_WINDOW_DAYS = 7
T = TypeVar("T")


def extract_youtube_video_id(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if host not in YOUTUBE_HOSTS:
        raise ValueError("Only YouTube URLs are supported")

    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    elif parsed.path.startswith("/shorts/"):
        video_id = parsed.path.split("/")[2]

    if not VIDEO_ID_RE.fullmatch(video_id):
        raise ValueError("Could not extract a valid YouTube video ID")
    return video_id


def parse_iso8601_duration_seconds(value: str) -> int:
    match = DURATION_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Unsupported YouTube duration: {value}")
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def sort_by_vs_ratio(candidates: list[ReferenceCandidate]) -> list[ReferenceCandidate]:
    return sorted(
        candidates,
        key=lambda item: (item.vs_ratio is not None, item.vs_ratio or 0, item.view_count),
        reverse=True,
    )


def chunked(values: list[T], size: int) -> list[list[T]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def parse_search_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def date_windows(request: ReferenceSearchRequest) -> list[tuple[str | None, str | None]]:
    start = parse_search_date(request.published_after)
    end = parse_search_date(request.published_before)
    if start is None or end is None or start > end:
        return [(request.published_after, request.published_before)]

    windows: list[tuple[str | None, str | None]] = []
    cursor_end = end
    while cursor_end >= start:
        cursor_start = max(start, cursor_end - timedelta(days=SEARCH_WINDOW_DAYS - 1))
        windows.append((cursor_start.isoformat(), cursor_end.isoformat()))
        cursor_end = cursor_start - timedelta(days=1)
    windows.reverse()
    return windows


def extract_youtube_channel_identifier(query: str) -> tuple[str, str]:
    stripped = query.strip()
    parsed = urlparse(stripped)
    if parsed.netloc.lower() in YOUTUBE_HOSTS:
        path = parsed.path.strip("/")
        if path.startswith("@"):
            return "handle", path
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "channel":
            return "id", parts[1]
        if len(parts) >= 2 and parts[0] in ("c", "user"):
            return "query", parts[1]
        if path:
            return "handle" if path.startswith("@") else "query", path

    if stripped.startswith("@"):
        return "handle", stripped
    if stripped.startswith("UC") and len(stripped) == 24:
        return "id", stripped
    return "query", stripped


class YouTubeClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None):
        if not api_key:
            raise ValueError("YouTube API key is missing")
        self.api_key = api_key
        self.http_client = http_client or httpx.Client(timeout=20)

    def resolve_channel(self, channel_query: str) -> tuple[str, str]:
        kind, ident = extract_youtube_channel_identifier(channel_query)
        channel_id = ""
        uploads_id = ""

        if kind == "id":
            resp = self.http_client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "contentDetails", "id": ident, "key": self.api_key},
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    channel_id = items[0]["id"]
                    uploads_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")

        elif kind == "handle":
            clean_handle = ident if ident.startswith("@") else f"@{ident}"
            resp = self.http_client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "contentDetails", "forHandle": clean_handle, "key": self.api_key},
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    channel_id = items[0]["id"]
                    uploads_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")

        if not channel_id:
            search_query = ident if not ident.startswith("@") else ident[1:]
            resp = self.http_client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={"part": "snippet", "type": "channel", "q": search_query, "maxResults": 1, "key": self.api_key},
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    channel_id = items[0].get("id", {}).get("channelId") or items[0].get("snippet", {}).get("channelId", "")

            if channel_id:
                resp = self.http_client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "contentDetails", "id": channel_id, "key": self.api_key},
                )
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    if items:
                        uploads_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")

        if not channel_id:
            raise ValueError(f"유튜브 채널을 찾을 수 없습니다: {channel_query}")

        if not uploads_id and channel_id.startswith("UC"):
            uploads_id = "UU" + channel_id[2:]

        return channel_id, uploads_id

    def search(self, request: ReferenceSearchRequest) -> list[ReferenceCandidate]:
        channel_id = ""
        uploads_id = ""
        if request.channel_query:
            channel_id, uploads_id = self.resolve_channel(request.channel_query)

        # 1. 키워드가 있는 경우 (채널 지정 시 channelId 파라미터로 해당 채널 내 검색)
        if request.keyword:
            base_params = {
                "part": "snippet",
                "type": "video",
                "q": request.keyword,
                "maxResults": request.max_results,
                "key": self.api_key,
            }
            if channel_id:
                base_params["channelId"] = channel_id

            video_ids: list[str] = []
            seen_video_ids: set[str] = set()
            for published_after, published_before in date_windows(request):
                params = dict(base_params)
                if published_after:
                    params["publishedAfter"] = f"{published_after}T00:00:00Z"
                if published_before:
                    params["publishedBefore"] = f"{published_before}T23:59:59Z"

                response = self.http_client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params=params,
                )
                response.raise_for_status()
                search_items = response.json().get("items", [])
                for item in search_items:
                    video_id = item.get("id", {}).get("videoId")
                    if video_id and video_id not in seen_video_ids:
                        seen_video_ids.add(video_id)
                        video_ids.append(video_id)

            return self._hydrate(video_ids, "search", request)[: request.max_results]

        # 2. 키워드 없이 채널명만 있는 경우 (채널 uploads 재생목록에서 최신 영상들 긁어오기)
        if uploads_id:
            video_ids = []
            seen_video_ids = set()
            page_token = None
            max_to_fetch = min(200, max(50, request.max_results * 4))

            while len(video_ids) < max_to_fetch:
                params = {
                    "part": "contentDetails",
                    "playlistId": uploads_id,
                    "maxResults": min(50, max_to_fetch - len(video_ids)),
                    "key": self.api_key,
                }
                if page_token:
                    params["pageToken"] = page_token

                response = self.http_client.get(
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    v_id = item.get("contentDetails", {}).get("videoId")
                    if v_id and v_id not in seen_video_ids:
                        seen_video_ids.add(v_id)
                        video_ids.append(v_id)

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

            return self._hydrate(video_ids, "search", request)[: request.max_results]

        return []

    def get_direct(self, url: str) -> ReferenceCandidate:
        video_id = extract_youtube_video_id(url)
        candidates = self._hydrate([video_id], "direct", None)
        if not candidates:
            raise ValueError("YouTube video not found or unavailable")
        return candidates[0]

    def _hydrate(
        self,
        video_ids: list[str],
        source_type: str,
        request: ReferenceSearchRequest | None,
    ) -> list[ReferenceCandidate]:
        if not video_ids:
            return []

        candidates: list[ReferenceCandidate] = []
        for video_id_batch in chunked(video_ids, YOUTUBE_BATCH_SIZE):
            videos_response = self.http_client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,contentDetails,statistics",
                    "id": ",".join(video_id_batch),
                    "key": self.api_key,
                },
            )
            videos_response.raise_for_status()
            videos = {item["id"]: item for item in videos_response.json().get("items", [])}
            channel_ids = sorted(
                {item["snippet"]["channelId"] for item in videos.values() if "snippet" in item}
            )

            channels = {}
            for channel_id_batch in chunked(channel_ids, YOUTUBE_BATCH_SIZE):
                channels_response = self.http_client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "statistics", "id": ",".join(channel_id_batch), "key": self.api_key},
                )
                channels_response.raise_for_status()
                channels.update(
                    {item["id"]: item for item in channels_response.json().get("items", [])}
                )

            for video_id in video_id_batch:
                video = videos.get(video_id)
                if not video:
                    continue
                snippet = video.get("snippet")
                duration = video.get("contentDetails", {}).get("duration")
                if not snippet or not duration:
                    continue
                try:
                    duration_seconds = parse_iso8601_duration_seconds(duration)
                except ValueError:
                    continue
                view_count = int(video.get("statistics", {}).get("viewCount", 0))
                channel = channels.get(snippet["channelId"], {})
                raw_subscribers = channel.get("statistics", {}).get("subscriberCount")
                subscriber_count = (
                    int(raw_subscribers) if raw_subscribers is not None else None
                )

                if request and not request.matches_duration(duration_seconds):
                    continue
                if request and view_count < request.minimum_views:
                    continue
                if request and request.maximum_subscribers is not None:
                    if (
                        subscriber_count is None
                        or subscriber_count > request.maximum_subscribers
                    ):
                        continue

                upload_date_str = snippet["publishedAt"][:10]
                if request and request.published_after and upload_date_str < request.published_after:
                    continue
                if request and request.published_before and upload_date_str > request.published_before:
                    continue

                thumbnails = snippet.get("thumbnails", {})
                thumbnail_url = (
                    thumbnails.get("high", {}).get("url")
                    or thumbnails.get("default", {}).get("url", "")
                )
                candidates.append(
                    ReferenceCandidate(
                        video_id=video_id,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        title=snippet["title"],
                        channel_id=snippet["channelId"],
                        channel_name=snippet["channelTitle"],
                        thumbnail_url=thumbnail_url,
                        upload_date=snippet["publishedAt"],
                        duration_seconds=duration_seconds,
                        view_count=view_count,
                        subscriber_count=subscriber_count,
                        source_type=source_type,
                    )
                )

        return sort_by_vs_ratio(candidates)
