from pathlib import Path

from scrum_updates_bot.core.models import DraftDocument
from scrum_updates_bot.storage.drafts import DraftStore


def test_save_and_load_draft(tmp_path: Path) -> None:
    store = DraftStore(base_dir=tmp_path)
    draft = DraftDocument(name="Morning Standup", raw_input="Notes", output_text="Story: Example", activity_log=["Generated report"])
    path = store.save(draft)
    loaded = store.load(path)

    assert loaded.name == "Morning Standup"
    assert loaded.output_text == "Story: Example"
    assert loaded.activity_log == ["Generated report"]


def test_list_drafts_returns_saved_files(tmp_path: Path) -> None:
    store = DraftStore(base_dir=tmp_path)
    store.save(DraftDocument(name="Draft A"))
    store.save(DraftDocument(name="Draft B"))

    names = [item.name for item in store.list_drafts()]
    assert names == ["draft-a.json", "draft-b.json"]


def test_save_and_load_session(tmp_path: Path) -> None:
    store = DraftStore(base_dir=tmp_path)
    store.save_session(DraftDocument(name="Last Session", raw_input="Recovered notes", output_text="Story: Example"))

    session = store.load_session()

    assert session is not None
    assert session.raw_input == "Recovered notes"