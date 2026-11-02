import argparse

PROGRAM_NAME = "fare-reshop"


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Compare booked flights with fares on sale now.",
    )


def main() -> None:
    parser = build_parser()
    parser.parse_args()
    parser.print_help()
