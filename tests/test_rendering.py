from scrum_updates_bot.core.models import YTBEntry, YTBReport
from scrum_updates_bot.core.rendering import render_report_html, render_report_markdown, render_report_text


def sample_report() -> YTBReport:
    return YTBReport(
        entries=[
            YTBEntry(
                story_title="Improve Cloud Cost Estimator Accuracy Through AWS Service Validation Framework",
                ticket_id="FCSCCE-8983",
                ticket_url="https://jira.faa.gov/browse/FCSCCE-8983",
                yesterday="Deployed changes addressing cost accuracy issues.",
                today="Developing a dynamic script to validate AWS service schemas.",
                blockers="None",
            )
        ]
    )


def test_render_report_text_contains_ticket() -> None:
    text = render_report_text(sample_report())
    assert "Story: Improve Cloud Cost Estimator Accuracy Through AWS Service Validation Framework (FCSCCE-8983)" in text
    assert "Blockers: None" in text


def test_render_report_html_contains_anchor() -> None:
    html = render_report_html(sample_report())
    assert "<strong>Story:</strong>" in html
    assert "href=\"https://jira.faa.gov/browse/FCSCCE-8983\"" in html
    assert ">Improve Cloud Cost Estimator Accuracy Through AWS Service Validation Framework (FCSCCE-8983)<" in html


def test_render_markdown_contains_hyperlink() -> None:
    markdown = render_report_markdown(sample_report())
    assert "[Improve Cloud Cost Estimator Accuracy Through AWS Service Validation Framework (FCSCCE-8983)](https://jira.faa.gov/browse/FCSCCE-8983)" in markdown