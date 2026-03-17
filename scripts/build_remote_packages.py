from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_BASE = "https://api.github.com"
WORKFLOW_FILE = "release-packages.yml"


def run_git_command(args: list[str], root: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def parse_repo(remote_url: str) -> tuple[str, str]:
    trimmed = remote_url.strip()
    if trimmed.endswith(".git"):
        trimmed = trimmed[:-4]

    if trimmed.startswith("git@github.com:"):
        slug = trimmed.split(":", 1)[1]
    elif trimmed.startswith("https://github.com/"):
        slug = trimmed.split("https://github.com/", 1)[1]
    else:
        raise ValueError(f"Unsupported GitHub remote URL: {remote_url}")

    owner, repo = slug.split("/", 1)
    return owner, repo


def github_request(url: str, token: str, method: str = "GET", data: dict | None = None) -> object:
    payload = None if data is None else json.dumps(data).encode("utf-8")
    request = Request(url, data=payload, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "scrum-updates-bot-remote-builder")
    if payload is not None:
        request.add_header("Content-Type", "application/json")

    with urlopen(request, timeout=60) as response:
        if response.status == 204:
            return None
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset)
        if not body:
            return None
        return json.loads(body)


def format_http_error(exc: HTTPError) -> str:
    detail = ""
    try:
        charset = exc.headers.get_content_charset() or "utf-8"
        detail = exc.read().decode(charset).strip()
    except Exception:
        detail = ""

    if detail:
        try:
            parsed = json.loads(detail)
            message = parsed.get("message")
            errors = parsed.get("errors")
            detail = message or detail
            if errors:
                detail = f"{detail} | errors: {errors}"
        except json.JSONDecodeError:
            pass

    base = f"HTTP Error {exc.code}: {exc.reason}"
    if detail:
        return f"{base} - {detail}"
    return base


def check_branch_push_state(root: Path, branch: str) -> None:
    try:
        upstream = run_git_command(["rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"], root)
        counts = run_git_command(["rev-list", "--left-right", "--count", f"{upstream}...HEAD"], root)
        behind_count, ahead_count = [int(value) for value in counts.split()]
    except subprocess.CalledProcessError:
        print("Warning: this branch has no upstream configured. Remote builds use code already pushed to GitHub.")
        return

    if ahead_count > 0:
        print(f"Warning: local branch '{branch}' is ahead of '{upstream}' by {ahead_count} commit(s).")
        print("Remote builds run the code on GitHub, not your unpushed local changes. Push first if you want those changes included.")
    elif behind_count > 0:
        print(f"Warning: local branch '{branch}' is behind '{upstream}' by {behind_count} commit(s).")
        print("Remote builds will run whatever is currently on GitHub for that branch.")


def trigger_workflow(owner: str, repo: str, ref: str, token: str) -> None:
    url = f"{API_BASE}/repos/{owner}/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    github_request(url, token, method="POST", data={"ref": ref})


def find_run(owner: str, repo: str, branch: str, token: str, started_after: datetime) -> dict:
    url = (
        f"{API_BASE}/repos/{owner}/{repo}/actions/workflows/{WORKFLOW_FILE}/runs"
        f"?event=workflow_dispatch&branch={quote(branch)}&per_page=20"
    )
    response = github_request(url, token)
    assert isinstance(response, dict)
    runs = response.get("workflow_runs", [])
    for run in runs:
        created_at = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if created_at >= started_after:
            return run
    raise RuntimeError("Triggered workflow run was not found yet.")


def wait_for_run(owner: str, repo: str, run_id: int, token: str, poll_seconds: int) -> dict:
    url = f"{API_BASE}/repos/{owner}/{repo}/actions/runs/{run_id}"
    while True:
        response = github_request(url, token)
        assert isinstance(response, dict)
        status = response.get("status")
        conclusion = response.get("conclusion")
        html_url = response.get("html_url")
        print(f"Workflow status: {status or 'unknown'}; conclusion: {conclusion or 'pending'}")
        if status == "completed":
            if conclusion != "success":
                raise RuntimeError(f"Workflow failed with conclusion '{conclusion}'. See {html_url}")
            return response
        time.sleep(poll_seconds)


def download_artifacts(owner: str, repo: str, run_id: int, token: str, output_dir: Path) -> list[Path]:
    url = f"{API_BASE}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
    response = github_request(url, token)
    assert isinstance(response, dict)
    artifacts = response.get("artifacts", [])
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for artifact in artifacts:
        archive_url = artifact["archive_download_url"]
        name = artifact["name"]
        destination = output_dir / f"{name}.zip"
        request = Request(archive_url, method="GET")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        with urlopen(request, timeout=120) as response_handle:
            destination.write_bytes(response_handle.read())
        downloaded.append(destination)
    return downloaded


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Trigger the GitHub Actions packaging workflow and download its artifacts.")
    parser.add_argument("--ref", help="Git ref to build. Defaults to the current branch.")
    parser.add_argument("--poll-seconds", type=int, default=15, help="Seconds between workflow status checks.")
    parser.add_argument(
        "--output-dir",
        default=str(root / "output" / "github-actions-artifacts"),
        help="Directory where downloaded workflow artifact zip files will be saved.",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("Missing GITHUB_TOKEN or GH_TOKEN environment variable.", file=sys.stderr)
        print("Create a GitHub personal access token with repo/workflow access and export it before running this script.", file=sys.stderr)
        return 1

    try:
        remote_url = run_git_command(["remote", "get-url", "origin"], root)
        owner, repo = parse_repo(remote_url)
        ref = args.ref or run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], root)
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    check_branch_push_state(root, ref)

    started_after = datetime.now(timezone.utc)
    print(f"Triggering workflow '{WORKFLOW_FILE}' for {owner}/{repo} on ref '{ref}'")

    try:
        trigger_workflow(owner, repo, ref, token)
        run: dict | None = None
        for _ in range(20):
            try:
                run = find_run(owner, repo, ref, token, started_after)
                break
            except RuntimeError:
                time.sleep(3)
        if run is None:
            raise RuntimeError("Timed out while waiting for the workflow run to appear.")

        run_id = int(run["id"])
        print(f"Workflow run created: {run.get('html_url')}")
        wait_for_run(owner, repo, run_id, token, args.poll_seconds)
        artifact_paths = download_artifacts(owner, repo, run_id, token, Path(args.output_dir))
    except HTTPError as exc:
        message = format_http_error(exc)
        print(message, file=sys.stderr)
        if exc.code == 403:
            print(
                "GitHub rejected the request. Common causes:\n"
                "1. The token does not have permission for this repository.\n"
                "2. The token is missing Actions workflow permissions.\n"
                "3. The repository workflow file is not yet pushed to GitHub.\n\n"
                "Token requirements:\n"
                "- Fine-grained PAT: repository access to this repo with Actions=Read and write, Contents=Read and write, Metadata=Read.\n"
                "- Classic PAT: repo and workflow scopes.\n\n"
                "Also make sure you have pushed the latest commit before triggering the remote build.",
                file=sys.stderr,
            )
        return 1
    except (URLError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not artifact_paths:
        print("Workflow completed successfully but no artifacts were found.", file=sys.stderr)
        return 1

    print("Downloaded artifacts:")
    for artifact_path in artifact_paths:
        print(f"- {artifact_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())