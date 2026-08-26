"""cloudseed CLI: interactive menu + batch JSON mode."""

from __future__ import annotations

import argparse
import sys
from typing import List

from . import __version__
from .model import collect_interactive, load_json, TemplateConfig
from .generate import generate_all, build_user_data, build_meta_data


def _print_generated(written: List[str]) -> None:
    print("\nGenerated files:")
    for p in written:
        print(f"  {p}")
    print()


def run_batch(json_path: str, out_dir: str, plaintext: bool = False) -> int:
    cfg = load_json(json_path)
    cfg.plaintext_password = plaintext
    written = generate_all(cfg, out_dir)
    _print_generated(written)
    return 0


def run_interactive(out_dir: str, plaintext: bool = False) -> int:
    print("cloudseed — cloud-init VM template generator")
    print("=" * 48)
    cfg = collect_interactive()
    cfg.plaintext_password = plaintext

    if not out_dir:
        out_dir = input("\nOutput directory [./out]: ").strip() or "./out"

    written = generate_all(cfg, out_dir)
    _print_generated(written)

    print("--- user-data preview ---")
    print(build_user_data(cfg))
    print("--- meta-data preview ---")
    print(build_meta_data(cfg))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cloudseed",
        description="Generate cloud-init / Cloudbase-Init VM templates "
                    "for vSphere and KVM (Linux + Windows). Config-only (no ISO).",
    )
    p.add_argument("--version", action="version", version=f"CloudSeed {__version__}")
    p.add_argument("--json", metavar="FILE",
                   help="Apply a saved config (JSON) and generate files (batch mode).")
    p.add_argument("--out", metavar="DIR", default="",
                   help="Output directory (default ./out in interactive mode).")
    p.add_argument("--plaintext-password", action="store_true",
                   help="Emit the password in plaintext instead of a $6$ SHA-512 hash (discouraged).")
    p.add_argument("--print", action="store_true",
                   help="(batch) also print generated contents to stdout.")
    return p


def main(argv: List[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(argv)

    if args.json:
        return run_batch(args.json, args.out or "./out", args.plaintext_password)

    return run_interactive(args.out, args.plaintext_password)


if __name__ == "__main__":
    raise SystemExit(main())
