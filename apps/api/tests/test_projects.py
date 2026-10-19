import json
from pathlib import Path

import pytest

from app.projects.service import (
    create_project,
    list_projects,
    read_project,
    save_project,
    update_project_step,
    update_project_title,
)


def test_create_project_uses_timestamp_folder(tmp_path: Path):
    project = create_project(tmp_path, project_title="테스트 쇼츠", now="261011_2130")

    assert project.project_id == "261011_2130"
    assert project.project_title == "테스트 쇼츠"
    assert project.display_name == "261011_테스트 쇼츠"
    assert (tmp_path / "261011_2130" / "project.json").exists()


def test_list_projects_sorts_newest_first(tmp_path: Path):
    create_project(tmp_path, project_title="첫번째", now="261011_2130")
    create_project(tmp_path, project_title="두번째", now="261011_2140")

    projects = list_projects(tmp_path)

    assert [project.project_id for project in projects] == ["261011_2140", "261011_2130"]


def test_update_project_title_updates_display_name(tmp_path: Path):
    create_project(tmp_path, project_title="초기", now="261011_2130")

    updated = update_project_title(tmp_path, "261011_2130", "새제목")

    assert updated.project_title == "새제목"
    assert updated.display_name == "261011_새제목"
    assert read_project(tmp_path, "261011_2130").display_name == "261011_새제목"


@pytest.mark.parametrize(
    "project_id",
    [
        "../261011_2130",
        "261011_2130/extra",
        "261011_213",
        "2610112130",
        "261011_21300",
        "261011_2460",
        "261332_2130",
        "261011_21ab",
        "261011_..",
    ],
)
def test_rejects_invalid_project_ids_for_read_and_update(tmp_path: Path, project_id: str):
    with pytest.raises(ValueError):
        read_project(tmp_path, project_id)

    with pytest.raises(ValueError):
        update_project_title(tmp_path, project_id, "새제목")


@pytest.mark.parametrize(
    "project_id",
    [
        "../261011_2130",
        "261011_2130/extra",
        "261011_213",
        "2610112130",
        "261011_21300",
        "261011_2460",
        "261332_2130",
        "261011_21ab",
        "261011_..",
    ],
)
def test_rejects_invalid_project_ids_for_create(tmp_path: Path, project_id: str):
    with pytest.raises(ValueError):
        create_project(tmp_path, project_title="테스트", now=project_id)


def test_list_projects_skips_malformed_project_json(tmp_path: Path):
    create_project(tmp_path, project_title="정상", now="261011_2130")
    malformed_project = tmp_path / "261011_2140"
    malformed_project.mkdir()
    (malformed_project / "project.json").write_text("{not json", encoding="utf-8")

    projects = list_projects(tmp_path)

    assert [project.project_id for project in projects] == ["261011_2130"]


def test_list_projects_skips_project_json_with_invalid_project_id(tmp_path: Path):
    create_project(tmp_path, project_title="정상", now="261011_2130")
    create_project(tmp_path, project_title="비정상", now="261011_2140")
    project_json = tmp_path / "261011_2140" / "project.json"
    data = json.loads(project_json.read_text(encoding="utf-8"))
    data["project_id"] = "../261011_2140"
    project_json.write_text(json.dumps(data), encoding="utf-8")

    projects = list_projects(tmp_path)

    assert [project.project_id for project in projects] == ["261011_2130"]


def test_blank_title_becomes_untitled_display_name(tmp_path: Path):
    project = create_project(tmp_path, project_title="   ", now="261011_2130")

    assert project.project_title == "untitled"
    assert project.display_name == "261011_untitled"


def test_duplicate_project_creation_does_not_overwrite(tmp_path: Path):
    original = create_project(tmp_path, project_title="원본", now="261011_2130")

    with pytest.raises(FileExistsError):
        create_project(tmp_path, project_title="덮어쓰기", now="261011_2130")

    assert read_project(tmp_path, "261011_2130").project_title == original.project_title


def test_update_project_step_rejects_missing_step_status(tmp_path: Path):
    project = create_project(tmp_path, project_title="레퍼런스", now="261011_2130")
    project.step_statuses = [
        status for status in project.step_statuses if status.name != "STT"
    ]
    save_project(tmp_path, project)

    with pytest.raises(ValueError, match="Step status not found"):
        update_project_step(tmp_path, "261011_2130", "STT", "running", "Ready")

    restored = read_project(tmp_path, "261011_2130")
    assert restored.current_step == "Reference"
