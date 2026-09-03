from __future__ import annotations

import os
from urllib.request import urlopen

import yaml

from district_context.config import PROJECT_ROOT
from district_context.utils import sha256_file


def main() -> None:
    config_path = PROJECT_ROOT / "config" / "illinois_sources.yml"
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    raw_dir = PROJECT_ROOT / "data" / "raw" / "illinois_report_card"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for group in ("report_card", "growth_reference"):
        for year, source in sorted(config[group].items()):
            destination = raw_dir / source["filename"]
            if destination.is_file() and sha256_file(destination) == source["sha256"]:
                print(f"PASS {year} {group}: existing file matches pinned SHA-256")
                continue

            partial = destination.with_suffix(destination.suffix + ".part")
            try:
                with urlopen(source["url"]) as response, partial.open("wb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                if partial.stat().st_size < int(source["expected_min_bytes"]):
                    raise ValueError(f"Downloaded file is unexpectedly small: {source['filename']}")
                observed_hash = sha256_file(partial)
                if observed_hash != source["sha256"]:
                    raise ValueError(f"SHA-256 mismatch for {source['filename']}")
                os.replace(partial, destination)
            finally:
                if partial.exists():
                    partial.unlink()
            print(f"PASS {year} {group}: downloaded and verified {source['filename']}")


if __name__ == "__main__":
    main()
