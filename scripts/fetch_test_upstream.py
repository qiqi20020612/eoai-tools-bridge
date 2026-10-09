"""Cache hash-checked, unmodified EOAIC2 files solely for contract tests."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

COMMIT = "b0274f752fc01495875522db9281c335af8cf484"
REPOSITORY = "outsharked/extended-openai-conversation-2"
DESTINATION = Path(__file__).resolve().parents[1] / ".cache/upstream/eoaic2"
FILES = {
    "const.py": "ad72b9732f9a92f6ab99d49b9b672c620f17076cc84565c596a32b1c73f31d37",
    "exceptions.py": "f5f5652517514631b088eebbd039d46dcdb3c22f69318977e8e12e7bb30f287c",
    "functions/base.py": (
        "1f46d66d750f8edc2db66222386a3737a1e9580e101259c4a13ef6fc0c002c3d"
    ),
    "functions/script.py": (
        "a71cec18d361ffe726b105739f69710345212be6ac5031954f65755f9f2abd2e"
    ),
}


def main() -> None:
    """Use immutable source URLs; do not write into a HA installation."""
    for relative_path, expected in FILES.items():
        destination = DESTINATION / relative_path
        if destination.exists():
            data = destination.read_bytes()
            if hashlib.sha256(data).hexdigest() == expected:
                print(f"Verified cached {relative_path}")
                continue
        url = (
            f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/"
            f"custom_components/extended_openai_conversation/{relative_path}"
        )
        with urlopen(url, timeout=30) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(f"Upstream source checksum mismatch: {relative_path}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        print(f"Fetched and verified {relative_path}")


if __name__ == "__main__":
    main()
