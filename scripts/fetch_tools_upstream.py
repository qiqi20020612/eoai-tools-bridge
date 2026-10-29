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

RELEASE_COMMIT = "198e37885fe06e6452d2d6e26bc5e532b1686acc"
RELEASE_DESTINATION = DESTINATION.with_name("llm_intents-1.11.0")
RELEASE_FILES = {
    **FILES,
    "const.py": "908380a403c7a20e34053592fc514c87fa983de73a17c00687dd19482753490f",
    "llm_functions.py": (
        "3566d90b1d8961aa60431fbd4913f945cdffe167a56d07e5a36fd8dfc1b678ba"
    ),
    "tavily_search.py": (
        "a7a0d233360139f54fcfda520120f592b755e03afed82831de6f4b31cb44a0f3"
    ),
    "manifest.json": "3dc624a46e0f36e377161c053c9a1ebf951966c0390638a1214678ee791c2559",
}

CURRENT_COMMIT = "5d2e76d72564fe378f32870bd311ca9460956281"
CURRENT_DESTINATION = DESTINATION.with_name("llm_intents-1.11.1")
CURRENT_FILES = {
    **RELEASE_FILES,
    "base_tool.py": "4c848a90ea5a8bde041a48e891c67c138c5b7367d48210ef7bd575fa990f0b39",
    "base_web_search.py": (
        "cfebffb4820455e4d5eaaace25e3ada22dc57b00e18e784917309606557a661f"
    ),
    "cache.py": "5cf20608e030f922ef1ee215ef0d3cc16d2e1c5eb7ee815e38e325c72c5e6995",
    "calculator.py": "ab655fb36b06f81a88322a9ec13cca462b16a395ec67e1cbd8d47f46f56905ae",
    "const.py": "361f5ba387bf438d5163c7c5f1bb9e64a45cc91b23b849029d75d9fade72efa8",
    "google_places.py": (
        "fd2861bdc43cf4cf7401c56eac78f93981ee3b6fafa94252a06f49adc4e2b0e5"
    ),
    "google_routes.py": (
        "18eafa69d6c28f70550ec5d96f4d8376fd537f68c10f6dbebd0c56dc2812ee77"
    ),
    "llm_functions.py": (
        "e0e714c8144a868aa3eee101134c475d2a6b2a813cd5ff7491dd5ad1ad7c33ea"
    ),
    "play_media.py": "deb10d28f3e4f7d609472eaec2d95c354abb8482eb60b6c4eadd1dd2056716ce",
    "searxng_search.py": (
        "40638aa59320c6a40c2b184e6ede5336a60f6700621eceb9b94b8b1020d1888b"
    ),
    "wikipedia.py": "54d26631a04bad3f0609980ad690af6fb40d75286cd2d56e54d460d1efb9c3b3",
    "youtube.py": "49410326f15576bb5949b342ca773707ab0b8183c581715f5331c079fff8861b",
    "manifest.json": "28134b2cf015f6f92d786747815dd341189a5b3524ce58a0a8e8953367f19770",
}


def fetch_snapshot(commit: str, files: dict[str, str], root: Path) -> None:
    """Preserve each snapshot and reuse only byte-identical, verified files."""
    for name, expected in files.items():
        destination = root / name
        if destination.exists():
            data = destination.read_bytes()
            if hashlib.sha256(data).hexdigest() == expected:
                print(f"Verified cached {root.name}/{name}")
                continue
        baseline = DESTINATION / name
        if root != DESTINATION and baseline.exists():
            data = baseline.read_bytes()
            if hashlib.sha256(data).hexdigest() == expected:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                print(f"Verified and reused {root.name}/{name}")
                continue
        url = (
            f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/"
            f"custom_components/llm_intents/{name}"
        )
        with urlopen(url, timeout=30) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(f"Tools for Assist source checksum mismatch: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        print(f"Fetched and verified Tools for Assist {name}")


def main() -> None:
    """Fetch test copies only; never install or alter an upstream integration."""
    fetch_snapshot(COMMIT, FILES, DESTINATION)
    fetch_snapshot(RELEASE_COMMIT, RELEASE_FILES, RELEASE_DESTINATION)
    fetch_snapshot(CURRENT_COMMIT, CURRENT_FILES, CURRENT_DESTINATION)


if __name__ == "__main__":
    main()
