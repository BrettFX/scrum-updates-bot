from __future__ import annotations

from html import escape

from scrum_updates_bot.core.models import YTBEntry, YTBReport


def story_label(entry: YTBEntry) -> str:
    if entry.ticket_id and entry.ticket_id not in entry.story_title:
        return f"{entry.story_title} ({entry.ticket_id})"
    return entry.story_title


def story_heading(entry: YTBEntry) -> str:
    label = escape(story_label(entry))
    if entry.ticket_url:
        return f'<a href="{escape(entry.ticket_url)}">{label}</a>'
    return label


def render_report_html(report: YTBReport) -> str:
    sections: list[str] = ["<html><body>"]
    for index, entry in enumerate(report.entries):
        if index:
            sections.append("<hr />")
        sections.append(f"<p><strong>Story:</strong> {story_heading(entry)}<br />")
        sections.append(f"<strong>Yesterday:</strong> {escape(entry.yesterday)}<br />")
        sections.append(f"<strong>Today:</strong> {escape(entry.today)}<br />")
        sections.append(f"<strong>Blockers:</strong> {escape(entry.blockers)}</p>")
    sections.append("</body></html>")
    return "".join(sections)


def render_report_text(report: YTBReport) -> str:
    lines: list[str] = []
    for index, entry in enumerate(report.entries):
        if index:
            lines.append("---")
        story = story_label(entry)
        lines.append(f"Story: {story}")
        lines.append(f"Yesterday: {entry.yesterday}")
        lines.append(f"Today: {entry.today}")
        lines.append(f"Blockers: {entry.blockers}")
    return "\n".join(lines)


def render_report_markdown(report: YTBReport) -> str:
    lines: list[str] = []
    for index, entry in enumerate(report.entries):
        if index:
            lines.append("\n---\n")
        label = story_label(entry)
        if entry.ticket_url:
            story = f"[{label}]({entry.ticket_url})"
        else:
            story = label
        lines.append(f"**Story**: {story}")
        lines.append(f"**Yesterday**: {entry.yesterday}")
        lines.append(f"**Today**: {entry.today}")
        lines.append(f"**Blockers**: {entry.blockers}")
    return "\n".join(lines)