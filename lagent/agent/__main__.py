"""Agent process entry point."""

import argparse
import logging

from lagent.agent.profile import load_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Start a LAgent agent")
    parser.add_argument(
        "--class",
        dest="profile_class",
        default="warlord",
        choices=("warlord", "prophet"),
    )
    args = parser.parse_args()

    profile = load_profile(args.profile_class)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info("Profile loaded: %s", profile.name)


if __name__ == "__main__":
    main()
