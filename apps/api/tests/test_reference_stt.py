from pathlib import Path

from app.references.files import REFERENCE_RAW_STT_FILE, REFERENCE_SCRIPT_FILE
from app.references.openai_clients import write_reference_stt_outputs


def test_write_reference_stt_outputs_saves_raw_json_and_script(tmp_path: Path):
    raw = {
        "text": "첫 문장입니다.",
        "segments": [{"start": 0, "end": 1, "text": "첫 문장입니다."}],
    }

    script = write_reference_stt_outputs(tmp_path, raw)

    assert script == "첫 문장입니다."
    assert (tmp_path / REFERENCE_RAW_STT_FILE).exists()
    assert (tmp_path / REFERENCE_SCRIPT_FILE).read_text(encoding="utf-8") == "첫 문장입니다.\n"


def test_write_reference_stt_outputs_trims_script_text(tmp_path: Path):
    raw = {"text": "  첫 문장입니다.  "}

    script = write_reference_stt_outputs(tmp_path, raw)

    assert script == "첫 문장입니다."
    assert (tmp_path / REFERENCE_SCRIPT_FILE).read_text(encoding="utf-8") == "첫 문장입니다.\n"
