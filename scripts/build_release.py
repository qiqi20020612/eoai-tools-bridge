"""Build an installable ZIP from explicit integration and documentation paths."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components/eoai_tools_bridge"


def main() -> None:
    """Never include virtual environments, test source caches, or credentials."""
    version = json.loads((INTEGRATION / "manifest.json").read_text())["version"]
    output = ROOT / "dist" / f"eoai_tools_bridge-{version}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [
        path
        for path in INTEGRATION.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in {".py", ".json", ".yaml", ".png", ".svg"}
    ]
    files.extend([ROOT / "README.md", ROOT / "LICENSE", ROOT / "hacs.json"])
    files.extend(sorted((ROOT / "examples").glob("*.yaml")))
    files.extend(sorted((ROOT / "docs").glob("*.md")))
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
    print(f"Built {output.relative_to(ROOT)} ({output.stat().st_size} bytes)")
    print(f"SHA256 {digest}")


if __name__ == "__main__":
    main()
