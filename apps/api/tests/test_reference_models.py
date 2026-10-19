import pytest
from pydantic import ValidationError

from app.references.models import (
    DirectReferenceRequest,
    ReferenceCandidate,
    ReferenceSearchRequest,
    SelectReferenceRequest,
)


def test_reference_candidate_calculates_ratio_when_subscribers_available():
    candidate = ReferenceCandidate(
        video_id="abc123DEF45",
        url="https://www.youtube.com/watch?v=abc123DEF45",
        title="테스트 쇼츠",
        channel_id="channel-1",
        channel_name="채널",
        thumbnail_url="https://img.youtube.com/vi/abc123DEF45/default.jpg",
        upload_date="2026-10-01T00:00:00Z",
        duration_seconds=45,
        view_count=120000,
        subscriber_count=3000,
        source_type="search",
    )

    assert candidate.vs_ratio == 40.0


def test_reference_candidate_handles_missing_subscribers():
    candidate = ReferenceCandidate(
        video_id="abc123DEF45",
        url="https://www.youtube.com/watch?v=abc123DEF45",
        title="테스트 쇼츠",
        channel_id="channel-1",
        channel_name="채널",
        thumbnail_url="https://img.youtube.com/vi/abc123DEF45/default.jpg",
        upload_date="2026-10-01T00:00:00Z",
        duration_seconds=45,
        view_count=120000,
        subscriber_count=None,
        source_type="direct",
    )

    assert candidate.vs_ratio is None


def test_search_request_bounds_max_results():
    with pytest.raises(ValidationError):
        ReferenceSearchRequest(keyword="ai", max_results=101)


@pytest.mark.parametrize(
    ("duration_filter", "max_duration_seconds"),
    [
        ("under_60", 60),
        ("under_120", 120),
        ("under_180", 180),
        ("under_300", 300),
        ("over_300", None),
        ("all", None),
    ],
)
def test_search_request_accepts_duration_filter_presets(duration_filter, max_duration_seconds):
    request = ReferenceSearchRequest(keyword="ai", duration_filter=duration_filter)

    assert request.duration_filter == duration_filter
    assert request.effective_max_duration_seconds == max_duration_seconds


def test_search_request_rejects_unknown_duration_filter():
    with pytest.raises(ValidationError):
        ReferenceSearchRequest(keyword="ai", duration_filter="short")


@pytest.mark.parametrize(
    "payload",
    [
        lambda: ReferenceSearchRequest(keyword="   "),
        lambda: DirectReferenceRequest(url="   "),
        lambda: SelectReferenceRequest(video_id="   "),
    ],
)
def test_reference_requests_reject_blank_text(payload):
    with pytest.raises(ValidationError):
        payload()


@pytest.mark.parametrize(
    "field_override",
    [
        {"video_id": " "},
        {"url": " "},
        {"title": " "},
        {"channel_id": " "},
        {"channel_name": " "},
        {"thumbnail_url": " "},
        {"upload_date": " "},
        {"duration_seconds": -1},
        {"view_count": -1},
        {"subscriber_count": -1},
    ],
)
def test_reference_candidate_rejects_invalid_core_fields(field_override):
    payload = {
        "video_id": "abc123DEF45",
        "url": "https://www.youtube.com/watch?v=abc123DEF45",
        "title": "테스트 쇼츠",
        "channel_id": "channel-1",
        "channel_name": "채널",
        "thumbnail_url": "https://img.youtube.com/vi/abc123DEF45/default.jpg",
        "upload_date": "2026-10-01T00:00:00Z",
        "duration_seconds": 45,
        "view_count": 120000,
        "subscriber_count": 3000,
        "source_type": "search",
    }
    payload.update(field_override)

    with pytest.raises(ValidationError):
        ReferenceCandidate(**payload)
