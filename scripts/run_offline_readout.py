from __future__ import annotations

import argparse

from acoustic_encoder.offline_readout_cli import execute_offline_readout_from_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one frozen-package offline direction readout")
    parser.add_argument("--package", required=True)
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    execute_offline_readout_from_manifest(args.package, args.input_manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
