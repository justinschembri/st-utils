"""CLI command handlers."""

# standard
import os

# internal
from .menu import _setup_credentials


def _validate(args):
    """Validate sensor configuration files."""
    from sensorthings_utils.sensor_things.extensions import SensorConfig
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
    """Push available sensor data to FROST server."""
    from sensorthings_utils.main import push_available
    push_available(exclude=args.exclude, frost_endpoint=args.frost_endpoint)


def _generate_config(args):
    """Generate sensor configuration from template."""
    from .config_generator import generate_config_from_template
    from sensorthings_utils.transformers.types import SupportedSensors
    
    try:
        sensor_model = SupportedSensors(args.sensor_model)
    except ValueError:
        print(f"Error: Unsupported sensor model: {args.sensor_model}")
        return
    
    # Collect user inputs
    print(f"\nGenerating configuration for {sensor_model.value}")
    print("=" * 50)
    
    sensor_id = input("Sensor ID/Name (typically MAC address): ").strip()
    if not sensor_id:
        print("Error: Sensor ID is required")
        return
    
    print("\nThing Configuration:")
    thing_name = input("Thing name: ").strip()
    if not thing_name:
        print("Error: Thing name is required")
        return
    
    thing_description = input("Thing description: ").strip()
    if not thing_description:
        print("Error: Thing description is required")
        return
    
    print("\nLocation Configuration:")
    location_name = input("Location name: ").strip()
    if not location_name:
        print("Error: Location name is required")
        return
    
    location_description = input("Location description: ").strip()
    if not location_description:
        print("Error: Location description is required")
        return
    
    try:
        longitude = float(input("Longitude: ").strip())
        latitude = float(input("Latitude: ").strip())
    except ValueError:
        print("Error: Longitude and latitude must be valid numbers")
        return
    
    # Generate config
    try:
        output_path = generate_config_from_template(
            sensor_model=sensor_model,
            sensor_id=sensor_id,
            thing_name=thing_name,
            thing_description=thing_description,
            location_name=location_name,
            location_description=location_description,
            longitude=longitude,
            latitude=latitude,
            output_path=args.output,
        )
        print(f"\n✓ Configuration generated successfully: {output_path}")
        print(f"\nNext steps:")
        print(f"  1. Review the configuration file")
        print(f"  2. Validate it using: stu validate {output_path}")
    except Exception as e:
        print(f"\nError generating configuration: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main CLI entry point."""
    import argparse
    
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

    # subcommand: setup
    setup_parser = subparsers.add_parser(
        "setup", help="Interactive setup for credential files."
    )
    setup_parser.add_argument(
        "--all", action="store_true", help="Setup all credential types."
    )
    setup_parser.add_argument(
        "--frost", action="store_true", help="Setup FROST credentials."
    )
    setup_parser.add_argument(
        "--postgres", action="store_true", help="Setup PostgreSQL credentials."
    )
    setup_parser.add_argument(
        "--mqtt", action="store_true", help="Setup MQTT credentials."
    )
    setup_parser.add_argument(
        "--tomcat", action="store_true", help="Setup Tomcat users (webapp authentication)."
    )
    setup_parser.add_argument(
        "--token", action="store_true", help="Setup a token file (freeform JSON)."
    )
    setup_parser.set_defaults(func=_setup_credentials)

    # subcommand: generate-config
    gen_config_parser = subparsers.add_parser(
        "generate-config", help="Generate sensor configuration file from template."
    )
    gen_config_parser.add_argument(
        "sensor_model",
        choices=["milesight.am103l", "milesight.am308l", "netatmo.nws03"],
        help="Sensor model to generate config for."
    )
    gen_config_parser.add_argument(
        "--output",
        help="Output file path (defaults to sensor_configs/{sensor_id}.yaml)"
    )
    gen_config_parser.set_defaults(func=_generate_config)

    args = parser.parse_args()
    args.func(args)
