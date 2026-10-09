"""Cache immutable, hash-checked Tools for Assist source for contract tests."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

COMMIT = "100e740b93a2a1a6d304329883937193a4571ac0"
REPOSITORY = "skye-harris/llm_intents"
DESTINATION = Path(__file__).resolve().parents[1] / ".cache/upstream/llm_intents"
FILES = {
    "base_tool.py": "73e6d784d7908c4e7be1b48ef18cd85b4ae7f4c94caa5a2c3278ca9c4fa23639",
    "base_web_search.py": (
        "dd1c44eff11d723f4f112cd5f27ac1e8c80d55085e4fa33531f50b4e3c0117a5"
    ),
    "brave_llm_context_search.py": (
        "c1d592c757e6e76904ecf0bd4aaa144f7f0bc97fa57d233f8487c39f16c6d9cc"
    ),
    "brave_web_search.py": (
        "c678b12ce8da761850f59342ef860deb9ef43372ab363efcf5f6f430e75cb77a"
    ),
    "cache.py": "7c08d86a9f95224d144b004a92af4c192bd9b29be0783e550cf871f853598e84",
    "calculator.py": "c820eb05f0d7b406bfcc379223fe210774ddc0edbf0c20b120f979335f04e0f0",
    "const.py": "bb972390afe294fe56c1c671d68119b6c5b1c9689668805d1fbf2ee75ca43725",
    "date_info.py": "fdb657fd6b7b7d174b3c3b418890a662cc68835af4ec7012cd63162fde682a71",
    "entity_history.py": (
        "2cef031a24871e554c1a4b01326cb452b6975a66b3f19ae930ee878f7e2265ac"
    ),
    "google_places.py": (
        "84f176682d86cb354aa753d19de7693e3fe5bcbb0599f295e9aee9e14f86ac82"
    ),
    "google_routes.py": (
        "b1b4d2fac4a0fb9d408659d43c42a4aca20bb016bafe47846a8d8c7fe53eed77"
    ),
    "home_control.py": (
        "1472dd8bfdc687aa2aa135ce25e145445416ee1d267d69c518ab6a912477a750"
    ),
    "llm_functions.py": (
        "ac817af1deaa4f7382778eab1de25276cd83e335d581c1aedff11854c83eb314"
    ),
    "play_media.py": "2f7b3919fa9d91fcb285b5151c5397eb5dc14c40526891862b443d2367ca31d4",
    "searxng_search.py": (
        "6a2ebe7a6b9bc869b7b43b8577b8810e2744bc37ae5f7b9d109b0f8e12e6e89b"
    ),
    "unit_converter.py": (
        "594b4c5c1d31c24ae4ef593d45c957ccf41bac33f137b897bce37d4fecfd35eb"
    ),
    "utils.py": "8affb0aa4af68019b42daa98d285c026c61b84d55e38a4e99f72ac68f1a1bb32",
    "weather.py": "e7934418c3c451669c476ea2dfbd9d379d8843f925f2a884fd3b8df00e7aaf16",
    "wikipedia.py": "871998a2f4c44bd50bf33c9e649840576613c17203a5357d4486927c5872dd3d",
    "youtube.py": "c4578f94ba0ac1473f330c0f366b3a52a33afc44d31a03f7c2c0a80401e83417",
}


def main() -> None:
    """Fetch test copies only; never install or alter an upstream integration."""
    for name, expected in FILES.items():
        destination = DESTINATION / name
        if destination.exists():
            data = destination.read_bytes()
            if hashlib.sha256(data).hexdigest() == expected:
                print(f"Verified cached Tools for Assist {name}")
                continue
        url = (
            f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/"
            f"custom_components/llm_intents/{name}"
        )
        with urlopen(url, timeout=30) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(f"Tools for Assist source checksum mismatch: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        print(f"Fetched and verified Tools for Assist {name}")


if __name__ == "__main__":
    main()
