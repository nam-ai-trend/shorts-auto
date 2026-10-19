from pathlib import Path

from app.references.files import (
    read_reference_state,
    write_reference_candidates,
    write_reference_script,
    write_selected_reference,
)
from app.references.models import ReferenceCandidate


def make_candidate() -> ReferenceCandidate:
    return ReferenceCandidate(
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


def test_reference_state_reads_persisted_candidates_selection_and_script(tmp_path: Path):
    project_dir = tmp_path / "261011_2130"
    project_dir.mkdir()
    candidate = make_candidate()

    write_reference_candidates(project_dir, [candidate])
    write_selected_reference(project_dir, candidate)
    write_reference_script(project_dir, "첫 문장입니다.")

    state = read_reference_state(project_dir)

    assert state.candidates[0].video_id == "abc123DEF45"
    assert state.selected_reference is not None
    assert state.selected_reference.title == "테스트 쇼츠"
    assert state.reference_script == "첫 문장입니다."
