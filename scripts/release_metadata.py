from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SEMVER_RE = re.compile(r"(\d+\.\d+\.\d+)")


def read_version_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def extract_semver(*candidates: str) -> str:
    for candidate in candidates:
        match = SEMVER_RE.search(str(candidate or ""))
        if match:
            return match.group(1)
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve shared release metadata for workflows.")
    parser.add_argument("--event-name", default="")
    parser.add_argument("--ref-type", default="")
    parser.add_argument("--ref-name", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--release-tag", default="")
    parser.add_argument("--upload-to-release", default="false")
    parser.add_argument("--version-file", default="VERSION")
    parser.add_argument("--tag-prefix", default="v")
    return parser.parse_args()


def normalize_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_metadata(args: argparse.Namespace) -> dict[str, object]:
    version = str(args.version or "").strip()
    release_tag = str(args.release_tag or "").strip()
    event_name = str(args.event_name or "").strip()
    ref_type = str(args.ref_type or "").strip()
    ref_name = str(args.ref_name or "").strip()
    tag_prefix = str(args.tag_prefix or "v").strip() or "v"
    should_upload = False

    if event_name == "workflow_dispatch":
        should_upload = normalize_bool(args.upload_to_release)
    elif ref_type == "tag":
        should_upload = True
        release_tag = release_tag or ref_name

    if not version and ref_type == "tag":
        version = extract_semver(release_tag, ref_name)

    if not version:
        version = read_version_file(Path(args.version_file))

    if not release_tag and should_upload and version:
        release_tag = f"{tag_prefix}{version}"

    if not version:
        version = extract_semver(release_tag, ref_name)

    if not version:
        raise SystemExit("Missing version. Provide --version, a VERSION file, or a ref/tag containing x.y.z.")

    if should_upload and not release_tag:
        raise SystemExit("Missing release tag while upload is enabled.")

    return {
        "version": version,
        "release_tag": release_tag,
        "should_upload": should_upload,
    }


def main() -> int:
    payload = resolve_metadata(parse_args())
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
