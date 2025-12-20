"""SensorThings Utils CLI."""

# standard
import argparse
import logging
import os

# external
# internal
from sensorthings_utils.sensor_things.extensions import SensorConfig
from sensorthings_utils.main import push_available

logger = logging.getLogger("st-utils")
logger.setLevel(logging.INFO)


def _validate(args):
    if args.file:
        validation_files = [args.file]
    else:
        validation_files = [
            os.path.join(root, f)
            for root, _, files in os.walk(".")
            for f in files
            if (f.endswith((".yaml", "yml")) and not f.startswith("template"))
        ]

    for f in validation_files:
        result, errors = SensorConfig(f).check_validity()
        if errors:
            for e in errors:
                print(e)


def _push_available(args):
    push_available(exclude=args.exclude, frost_endpoint=args.frost_endpoint)


def main():
    parser = argparse.ArgumentParser(description="st-utils CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # subcommand: push
    push_parser = subparsers.add_parser("push", help="Start the stream.")
    push_parser.add_argument(
        "--frost-endpoint",
        help="Change default FROST server URL.",
    )
    push_parser.add_argument(
        "--exclude",
        help="Pass a list of sensor MAC addresses to exclude from the stream.",
    )
    push_parser.set_defaults(func=_push_available)

    # subcommand: validate
    validate_parser = subparsers.add_parser(
        "validate", help="Validate all yaml files in the working directory."
    )
    validate_parser.add_argument(
        "file", nargs="?", default=None, help="Config file to validate."
    )

    validate_parser.set_defaults(func=_validate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
