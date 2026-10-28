"""Verify an existing reviewed tag; optionally publish its release without retagging."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "Prasanna-K-123/credit-risk-model-validation"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_request(environment, checkout):
    require(environment.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "Explicit dispatch is required")
    require(environment.get("GITHUB_REPOSITORY") == REPOSITORY, "Unexpected repository")
    require(environment.get("GITHUB_REF") == "refs/heads/main", "Dispatch must use main")
    sha = environment.get("REVIEWED_COMMIT", "")
    tag = environment.get("RELEASE_TAG", "")
    require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None, "A full reviewed commit SHA is required")
    require(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?", tag) is not None,
            "Use an explicit version tag, for example v1.1.0")
    require(environment.get("GITHUB_SHA") == sha == checkout, "Dispatch, checkout and reviewed commit differ")
    return sha, tag


def tag_commit(api, tag):
    obj = api("/git/ref/tags/" + urllib.parse.quote(tag, safe=""))["object"]
    seen = set()
    for _ in range(8):
        require(obj["sha"] not in seen, "Tag object cycle")
        seen.add(obj["sha"])
        if obj["type"] == "commit":
            return obj["sha"]
        require(obj["type"] == "tag", "Tag does not resolve to a commit")
        obj = api("/git/tags/" + obj["sha"])["object"]
    raise ValueError("Too many tag indirections")


def verify_refs(api, sha, tag):
    require(api("/branches/main")["commit"]["sha"] == sha, "Main changed; review its new commit")
    require(tag_commit(api, tag) == sha, "Existing tag differs from reviewed commit; no retagging")


def release_text(sha, tag):
    title = "Bank-risk model validation — " + tag
    body = (
        f"Reviewed source: `{sha}`.\n\n"
        "Public FDIC bank-certificate failure research. The guarded workflow checks "
        "the existing tag and main, runs the original temporal and independent review tests, "
        "replays all frozen fits and paired uncertainty, and verifies generated reports "
        "and the cohort/failure explorer before publication.\n\n"
        "Strong pooled discrimination did not establish a reliable later monitoring rule. "
        "The post-hoc 2022–2025 cohorts retain nine missed failures out of ten. "
        "Current historical revisions and assumed report availability limit interpretation; "
        "this is not borrower PD/LGD, IFRS 9 approval or a production service.\n\n"
        "[Explorer](https://prasanna-k-123.github.io/credit-risk-model-validation/) · "
        f"[Reproduction guide](https://github.com/{REPOSITORY}/blob/{sha}/docs/REPRODUCE.md)"
    )
    return title, body


def publish(api, sha, tag):
    verify_refs(api, sha, tag)
    title, body = release_text(sha, tag)
    release = api("/releases/tags/" + urllib.parse.quote(tag, safe=""), missing_ok=True)
    if release is None:
        # External writers are outside this workflow's concurrency lock.
        verify_refs(api, sha, tag)
        release = api("/releases", payload={"tag_name": tag, "target_commitish": sha,
                      "name": title, "body": body, "draft": False,
                      "prerelease": False, "make_latest": "false"})
    require(release["tag_name"] == tag and release["name"] == title, "Existing release identity differs")
    require(release["body"].replace("\r\n", "\n").strip() == body.strip(), "Existing release notes differ; no overwrite")
    require(not release["draft"] and not release["prerelease"], "Release is not final")
    verify_refs(api, sha, tag)
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sha, tag = validate_request(os.environ, checkout)
    headers = {"Authorization": "Bearer " + os.environ["GH_TOKEN"],
               "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10",
               "User-Agent": "bank-risk-reviewed-release"}

    def api(path, payload=None, missing_ok=False):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
                                         data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if missing_ok and error.code == 404:
                return None
            raise RuntimeError(f"GitHub request failed: {path} (HTTP {error.code})") from None

    verify_refs(api, sha, tag)
    result = {"reviewed_commit": sha, "tag": tag, "existing_tag_verified": True}
    if args.publish:
        result["release_url"] = publish(api, sha, tag)["html_url"]
    print(json.dumps(result))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as handle:
            handle.write("\n```json\n" + json.dumps(result, indent=2) + "\n```\n")


if __name__ == "__main__":
    main()
