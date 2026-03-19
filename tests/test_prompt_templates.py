from pathlib import Path

from scrum_updates_bot.storage.prompt_templates import (
    DEFAULT_PROMPT_TEMPLATE_CONTENT,
    DEFAULT_PROMPT_TEMPLATE_NAME,
    PromptTemplateStore,
)


def test_store_seeds_default_template(tmp_path: Path) -> None:
    store = PromptTemplateStore(base_dir=tmp_path)

    templates = [store.load(path) for path in store.list_templates()]

    assert [template.name for template in templates] == [DEFAULT_PROMPT_TEMPLATE_NAME]
    assert templates[0].content == DEFAULT_PROMPT_TEMPLATE_CONTENT


def test_save_and_load_prompt_template(tmp_path: Path) -> None:
    store = PromptTemplateStore(base_dir=tmp_path)
    path = store.template_path("Custom Follow-up")
    path.write_text(
        """{
  \"name\": \"Custom Follow-up\",
  \"content\": \"Story title is \\\"Example\\\"\",
  \"created_at\": \"2026-03-19T00:00:00Z\",
  \"updated_at\": \"2026-03-19T00:00:00Z\"
}""",
        encoding="utf-8",
    )

    loaded = store.load(path)

    assert loaded.name == "Custom Follow-up"
    assert loaded.content == 'Story title is "Example"'