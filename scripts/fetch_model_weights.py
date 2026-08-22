"""Download model weights from a GitHub Release without committing binaries."""

import argparse
import os
from pathlib import Path
from urllib.request import Request, urlopen


def release_asset_url(repository: str, tag: str, asset_name: str) -> str:
    release_path = "latest" if tag == "latest" else tag
    prefix = "releases/latest/download" if tag == "latest" else f"releases/download/{release_path}"
    return (
        f"https://github.com/{repository}/{prefix}/{asset_name}"
    )


def download_asset(repository: str, tag: str, asset_name: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        release_asset_url(repository, tag, asset_name),
        headers={"User-Agent": "road-defect-model-setup"},
    )
    with urlopen(request) as response, destination.open("wb") as output:
        output.write(response.read())
    print(f"Downloaded {asset_name} -> {destination}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=os.getenv("MODEL_RELEASE_TAG", "latest"))
    parser.add_argument(
        "--repository",
        default=os.getenv("GITHUB_REPOSITORY", "s44nvi/Road-Defect"),
    )
    parser.add_argument(
        "--asset",
        action="append",
        required=True,
        metavar="MODEL=ASSET",
        help="Release asset mapping, for example pothole_crack=production.pt",
    )
    args = parser.parse_args()

    repository_root = Path(__file__).resolve().parents[1]
    for mapping in args.asset:
        model_name, separator, asset_name = mapping.partition("=")
        if not separator or not model_name or not asset_name:
            parser.error(f"Invalid asset mapping: {mapping!r}")
        destination = repository_root / "ml" / "models" / model_name / "weights" / asset_name
        download_asset(args.repository, args.tag, asset_name, destination)


if __name__ == "__main__":
    main()