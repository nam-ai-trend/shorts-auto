import httpx
import pytest

from app.references.models import ReferenceCandidate, ReferenceSearchRequest
from app.references.youtube import (
    date_windows,
    YouTubeClient,
    extract_youtube_channel_identifier,
    extract_youtube_video_id,
    parse_iso8601_duration_seconds,
    sort_by_vs_ratio,
)


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.youtube.com/watch?v=abc123DEF45", "abc123DEF45"),
        ("https://youtu.be/abc123DEF45", "abc123DEF45"),
        ("https://www.youtube.com/shorts/abc123DEF45", "abc123DEF45"),
        ("https://m.youtube.com/watch?v=abc123DEF45&t=12s", "abc123DEF45"),
    ],
)
def test_extract_youtube_video_id(url: str, video_id: str):
    assert extract_youtube_video_id(url) == video_id


def test_extract_youtube_video_id_rejects_invalid_url():
    with pytest.raises(ValueError):
        extract_youtube_video_id("https://example.com/watch?v=abc123DEF45")


@pytest.mark.parametrize(
    ("duration", "seconds"),
    [("PT45S", 45), ("PT1M5S", 65), ("PT1H2M3S", 3723), ("P1DT2H3M4S", 93784)],
)
def test_parse_iso8601_duration_seconds(duration: str, seconds: int):
    assert parse_iso8601_duration_seconds(duration) == seconds


def candidate(video_id: str, views: int, subscribers: int | None) -> ReferenceCandidate:
    return ReferenceCandidate(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=video_id,
        channel_id=f"channel-{video_id}",
        channel_name="채널",
        thumbnail_url="https://example.com/thumb.jpg",
        upload_date="2026-10-01T00:00:00Z",
        duration_seconds=45,
        view_count=views,
        subscriber_count=subscribers,
        source_type="search",
    )


def test_sort_by_vs_ratio_puts_unavailable_ratio_last():
    sorted_items = sort_by_vs_ratio(
        [
            candidate("low123DEF45", 1000, 1000),
            candidate("non123DEF45", 100000, None),
            candidate("hig123DEF45", 5000, 100),
        ]
    )

    assert [item.video_id for item in sorted_items] == [
        "hig123DEF45",
        "low123DEF45",
        "non123DEF45",
    ]


class FakeTransport(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "search" in url:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": {"videoId": "abc123DEF45"},
                            "snippet": {
                                "title": "검색 결과",
                                "channelId": "channel-1",
                                "channelTitle": "채널",
                                "publishedAt": "2026-10-01T00:00:00Z",
                                "thumbnails": {
                                    "default": {"url": "https://example.com/thumb.jpg"}
                                },
                            },
                        }
                    ]
                },
            )
        if "videos" in url:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "abc123DEF45",
                            "snippet": {
                                "title": "검색 결과",
                                "channelId": "channel-1",
                                "channelTitle": "채널",
                                "publishedAt": "2026-10-01T00:00:00Z",
                                "thumbnails": {
                                    "default": {"url": "https://example.com/thumb.jpg"}
                                },
                            },
                            "contentDetails": {"duration": "PT45S"},
                            "statistics": {"viewCount": "120000"},
                        }
                    ]
                },
            )
        if "channels" in url:
            return httpx.Response(
                200,
                json={"items": [{"id": "channel-1", "statistics": {"subscriberCount": "3000"}}]},
            )
        raise AssertionError(url)


class EmptyDirectTransport(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "videos" in url:
            return httpx.Response(200, json={"items": []})
        if "channels" in url:
            return httpx.Response(200, json={"items": []})
        raise AssertionError(url)


def test_youtube_client_search_hydrates_metadata():
    client = YouTubeClient("key", http_client=httpx.Client(transport=FakeTransport()))

    results = client.search(ReferenceSearchRequest(keyword="테스트"))

    assert results[0].video_id == "abc123DEF45"
    assert results[0].duration_seconds == 45
    assert results[0].view_count == 120000
    assert results[0].subscriber_count == 3000
    assert results[0].vs_ratio == 40


def test_youtube_client_search_supports_over_five_minute_duration_filter():
    class LongVideoTransport(FakeTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "search" in url:
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {"id": {"videoId": "abc123DEF45"}},
                            {"id": {"videoId": "xyz987ABCDE"}},
                        ]
                    },
                )
            if "videos" in url:
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "abc123DEF45",
                                "snippet": {
                                    "title": "짧은 영상",
                                    "channelId": "channel-1",
                                    "channelTitle": "채널",
                                    "publishedAt": "2026-10-01T00:00:00Z",
                                    "thumbnails": {"high": {"url": "https://example.com/short.jpg"}},
                                },
                                "contentDetails": {"duration": "PT45S"},
                                "statistics": {"viewCount": "120000"},
                            },
                            {
                                "id": "xyz987ABCDE",
                                "snippet": {
                                    "title": "긴 영상",
                                    "channelId": "channel-1",
                                    "channelTitle": "채널",
                                    "publishedAt": "2026-10-01T00:00:00Z",
                                    "thumbnails": {"high": {"url": "https://example.com/long.jpg"}},
                                },
                                "contentDetails": {"duration": "PT6M1S"},
                                "statistics": {"viewCount": "90000"},
                            },
                        ]
                    },
                )
            return super().handle_request(request)

    client = YouTubeClient("key", http_client=httpx.Client(transport=LongVideoTransport()))

    results = client.search(ReferenceSearchRequest(keyword="테스트", duration_filter="over_300"))

    assert [item.video_id for item in results] == ["xyz987ABCDE"]


def test_date_windows_split_backwards_into_seven_day_windows():
    windows = date_windows(
        ReferenceSearchRequest(
            keyword="과학",
            published_after="2026-08-01",
            published_before="2026-08-15",
        )
    )

    assert windows == [
        ("2026-08-01", "2026-08-01"),
        ("2026-08-02", "2026-08-08"),
        ("2026-08-09", "2026-08-15"),
    ]


def test_youtube_client_search_splits_long_date_ranges_before_filtering():
    class DateWindowTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "search" in url:
                after = request.url.params.get("publishedAfter")
                before = request.url.params.get("publishedBefore")
                if after == "2026-08-01T00:00:00Z" and before == "2026-08-01T23:59:59Z":
                    return httpx.Response(200, json={"items": [{"id": {"videoId": "day123DEF45"}}]})
                if after == "2026-08-02T00:00:00Z" and before == "2026-08-08T23:59:59Z":
                    return httpx.Response(200, json={"items": [{"id": {"videoId": "week12DEF45"}}]})
                if after == "2026-08-09T00:00:00Z" and before == "2026-08-15T23:59:59Z":
                    return httpx.Response(200, json={"items": [{"id": {"videoId": "week23DEF45"}}]})
                return httpx.Response(200, json={"items": []})
            if "videos" in url:
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "day123DEF45",
                                "snippet": {
                                    "title": "첫날 영상",
                                    "channelId": "channel-1",
                                    "channelTitle": "채널",
                                    "publishedAt": "2026-08-01T00:00:00Z",
                                    "thumbnails": {"high": {"url": "https://example.com/day.jpg"}},
                                },
                                "contentDetails": {"duration": "PT45S"},
                                "statistics": {"viewCount": "9000"},
                            },
                            {
                                "id": "week12DEF45",
                                "snippet": {
                                    "title": "첫째 주 영상",
                                    "channelId": "channel-1",
                                    "channelTitle": "채널",
                                    "publishedAt": "2026-08-08T00:00:00Z",
                                    "thumbnails": {"high": {"url": "https://example.com/week1.jpg"}},
                                },
                                "contentDetails": {"duration": "PT45S"},
                                "statistics": {"viewCount": "30000"},
                            },
                            {
                                "id": "week23DEF45",
                                "snippet": {
                                    "title": "둘째 주 영상",
                                    "channelId": "channel-1",
                                    "channelTitle": "채널",
                                    "publishedAt": "2026-08-15T00:00:00Z",
                                    "thumbnails": {"high": {"url": "https://example.com/week2.jpg"}},
                                },
                                "contentDetails": {"duration": "PT45S"},
                                "statistics": {"viewCount": "12000"},
                            },
                        ]
                    },
                )
            if "channels" in url:
                return httpx.Response(
                    200,
                    json={"items": [{"id": "channel-1", "statistics": {"subscriberCount": "1000"}}]},
                )
            raise AssertionError(url)

    client = YouTubeClient("key", http_client=httpx.Client(transport=DateWindowTransport()))

    results = client.search(
            ReferenceSearchRequest(
                keyword="과학",
                published_after="2026-08-01",
                published_before="2026-08-15",
                max_results=50,
            )
        )

    assert {item.video_id for item in results} == {
        "day123DEF45",
        "week12DEF45",
        "week23DEF45",
    }


def test_youtube_client_direct_raises_controlled_error_when_video_missing():
    client = YouTubeClient("key", http_client=httpx.Client(transport=EmptyDirectTransport()))

    with pytest.raises(ValueError, match="not found or unavailable"):
        client.get_direct("https://www.youtube.com/watch?v=abc123DEF45")


def test_youtube_client_search_skips_partial_items():
    class PartialTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "search" in url:
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {"id": {"videoId": "bad123DEF45"}},
                            {
                                "id": {"videoId": "abc123DEF45"},
                                "snippet": {
                                    "title": "검색 결과",
                                    "channelId": "channel-1",
                                    "channelTitle": "채널",
                                    "publishedAt": "2026-10-01T00:00:00Z",
                                    "thumbnails": {
                                        "default": {"url": "https://example.com/thumb.jpg"}
                                    },
                                },
                            },
                        ]
                    },
                )
            if "videos" in url:
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {"id": "bad123DEF45"},
                            {
                                "id": "abc123DEF45",
                                "snippet": {
                                    "title": "검색 결과",
                                    "channelId": "channel-1",
                                    "channelTitle": "채널",
                                    "publishedAt": "2026-10-01T00:00:00Z",
                                    "thumbnails": {
                                        "default": {"url": "https://example.com/thumb.jpg"}
                                    },
                                },
                                "contentDetails": {"duration": "PT45S"},
                                "statistics": {"viewCount": "120000"},
                            },
                        ]
                    },
                )
            if "channels" in url:
                return httpx.Response(
                    200,
                    json={"items": [{"id": "channel-1", "statistics": {"subscriberCount": "3000"}}]},
                )
            raise AssertionError(url)

    client = YouTubeClient("key", http_client=httpx.Client(transport=PartialTransport()))

    results = client.search(ReferenceSearchRequest(keyword="테스트"))

    assert [item.video_id for item in results] == ["abc123DEF45"]


@pytest.mark.parametrize(
    ("query", "expected_type", "expected_value"),
    [
        ("@creator", "handle", "@creator"),
        ("https://www.youtube.com/@creator", "handle", "@creator"),
        ("https://www.youtube.com/channel/UC1234567890123456789012", "id", "UC1234567890123456789012"),
        ("UC1234567890123456789012", "id", "UC1234567890123456789012"),
        ("슈카월드", "query", "슈카월드"),
    ],
)
def test_extract_youtube_channel_identifier(query: str, expected_type: str, expected_value: str):
    kind, value = extract_youtube_channel_identifier(query)
    assert kind == expected_type
    assert value == expected_value


def test_youtube_client_search_by_channel_only():
    class ChannelOnlyTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "channels" in url:
                params = request.url.params
                if params.get("forHandle") in ("creator", "@creator") or params.get("id") == "UC1234567890123456789012":
                    return httpx.Response(
                        200,
                        json={
                            "items": [
                                {
                                    "id": "UC1234567890123456789012",
                                    "contentDetails": {
                                        "relatedPlaylists": {
                                            "uploads": "UU1234567890123456789012"
                                        }
                                    },
                                    "statistics": {"subscriberCount": "50000"},
                                }
                            ]
                        },
                    )
            if "playlistItems" in url:
                params = request.url.params
                if params.get("playlistId") == "UU1234567890123456789012":
                    return httpx.Response(
                        200,
                        json={
                            "items": [
                                {
                                    "contentDetails": {
                                        "videoId": "chan123DEF45",
                                    },
                                    "snippet": {
                                        "publishedAt": "2026-10-01T00:00:00Z",
                                    },
                                }
                            ]
                        },
                    )
            if "videos" in url:
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "chan123DEF45",
                                "snippet": {
                                    "title": "채널 업로드 영상",
                                    "channelId": "UC1234567890123456789012",
                                    "channelTitle": "크리에이터",
                                    "publishedAt": "2026-10-01T00:00:00Z",
                                    "thumbnails": {
                                        "high": {"url": "https://example.com/chan.jpg"}
                                    },
                                },
                                "contentDetails": {"duration": "PT50S"},
                                "statistics": {"viewCount": "150000"},
                            }
                        ]
                    },
                )
            raise AssertionError(f"Unexpected URL: {url}")

    client = YouTubeClient("key", http_client=httpx.Client(transport=ChannelOnlyTransport()))
    results = client.search(ReferenceSearchRequest(channel_query="@creator"))

    assert len(results) == 1
    assert results[0].video_id == "chan123DEF45"
    assert results[0].title == "채널 업로드 영상"
    assert results[0].vs_ratio == 3.0  # 150000 / 50000


def test_youtube_client_search_by_channel_and_keyword():
    recorded_search_params = {}

    class ChannelKeywordTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "channels" in url:
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "UC1234567890123456789012",
                                "statistics": {"subscriberCount": "10000"},
                            }
                        ]
                    },
                )
            if "search" in url:
                nonlocal recorded_search_params
                recorded_search_params = dict(request.url.params)
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {"id": {"videoId": "filt123DEF45"}}
                        ]
                    },
                )
            if "videos" in url:
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "filt123DEF45",
                                "snippet": {
                                    "title": "필터링 영상",
                                    "channelId": "UC1234567890123456789012",
                                    "channelTitle": "크리에이터",
                                    "publishedAt": "2026-10-01T00:00:00Z",
                                    "thumbnails": {
                                        "high": {"url": "https://example.com/filt.jpg"}
                                    },
                                },
                                "contentDetails": {"duration": "PT30S"},
                                "statistics": {"viewCount": "50000"},
                            }
                        ]
                    },
                )
            raise AssertionError(f"Unexpected URL: {url}")

    client = YouTubeClient("key", http_client=httpx.Client(transport=ChannelKeywordTransport()))
    results = client.search(ReferenceSearchRequest(keyword="투자", channel_query="UC1234567890123456789012"))

    assert len(results) == 1
    assert results[0].video_id == "filt123DEF45"
    assert recorded_search_params.get("channelId") == "UC1234567890123456789012"
    assert recorded_search_params.get("q") == "투자"

