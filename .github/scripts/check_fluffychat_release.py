#!/usr/bin/env python3

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


API_BASE = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
UPSTREAM_REPO = os.getenv("UPSTREAM_REPO", "krille-chan/fluffychat")
TARGET_REPO = os.getenv("TARGET_REPO") or os.getenv("GITHUB_REPOSITORY")
DEPLOY_BRANCH = os.getenv("DEPLOY_BRANCH", "web")
MARKER_FILE = os.getenv("MARKER_FILE", ".fluffychat-release-tag")
TOKEN = os.getenv("GITHUB_TOKEN", "")


def github_get(path: str, allow_404: bool = False):
    url = f"{API_BASE}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "fluffychat-web-release-checker",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None

        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {body}") from exc


def get_latest_release():
    data = github_get(f"/repos/{UPSTREAM_REPO}/releases/latest")

    tag = str(data.get("tag_name", "")).strip()
    name = str(data.get("name", "")).strip()

    if not tag:
        raise RuntimeError(f"Could not find tag_name in latest release for {UPSTREAM_REPO}")

    return tag, name


def get_deployed_tag():
    if not TARGET_REPO:
        return ""

    encoded_file = urllib.parse.quote(MARKER_FILE, safe="/")
    encoded_ref = urllib.parse.quote(DEPLOY_BRANCH, safe="")

    data = github_get(
        f"/repos/{TARGET_REPO}/contents/{encoded_file}?ref={encoded_ref}",
        allow_404=True,
    )

    if not data:
        return ""

    if data.get("encoding") != "base64" or "content" not in data:
        return ""

    decoded = base64.b64decode(data["content"]).decode("utf-8", "replace").strip()
    return decoded.splitlines()[0].strip() if decoded else ""


def write_github_outputs(outputs: dict[str, str]):
    output_path = os.getenv("GITHUB_OUTPUT")

    if not output_path:
        for key, value in outputs.items():
            print(f"{key}={value}")
        return

    with open(output_path, "a", encoding="utf-8") as file:
        for key, value in outputs.items():
            value = "" if value is None else str(value)

            if "\n" in value:
                delimiter = f"EOF_{key}"
                file.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                file.write(f"{key}={value}\n")


def main():
    latest_tag, latest_name = get_latest_release()
    deployed_tag = get_deployed_tag()

    should_build = "true" if latest_tag != deployed_tag else "false"

    write_github_outputs(
        {
            "latest_tag": latest_tag,
            "latest_name": latest_name,
            "deployed_tag": deployed_tag,
            "should_build": should_build,
        }
    )

    print(f"Latest upstream release: {latest_tag}")
    print(f"Currently deployed tag: {deployed_tag or '<none>'}")
    print(f"Should build: {should_build}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
