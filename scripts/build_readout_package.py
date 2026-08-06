from __future__ import annotations

import argparse

from acoustic_encoder.offline_readout_cli import build_readout_package_from_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one immutable P9-D readout package")
    parser.add_argument("--config", required=True)
    parser.add_argument("--training-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    build_readout_package_from_manifest(args.config, args.training_manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
