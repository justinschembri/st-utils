"""CLI command handlers."""

# standard
import os
from pathlib import Path
from typing import Optional

# external
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint

# internal
from .menu import _setup_credentials

# Create typer app and console
app = typer.Typer(
    help="st-utils CLI - SensorThings Utilities",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


def _validate(
    file: Optional[Path] = typer.Argument(None, help="Config file to validate (optional).")
):
    """Validate sensor configuration files."""
    from sensorthings_utils.sensor_things.extensions import SensorConfig
    
    if file:
        validation_files = [str(file)]
    else:
        validation_files = [
            os.path.join(root, f)
            for root, _, files in os.walk(".")
            for f in files
            if (f.endswith((".yaml", "yml")) and not f.startswith("template"))
        ]

    if not validation_files:
        console.print("[yellow]No YAML files found to validate.[/yellow]")
        return

    console.print(f"\n[bold]Validating {len(validation_files)} file(s)...[/bold]\n")
    
    all_valid = True
    for f in validation_files:
        result, errors = SensorConfig(f).check_validity()
        if errors:
            all_valid = False
            console.print(f"[red]❌ {f}[/red]")
            for e in errors:
                console.print(f"  [red]{e}[/red]")
        else:
            console.print(f"[green]✓ {f}[/green]")
    
    if all_valid:
        console.print("\n[bold green]All files are valid![/bold green]")
    else:
        console.print("\n[bold red]Some files have validation errors.[/bold red]")


def _push_available(
    frost_endpoint: Optional[str] = typer.Option(
        None, "--frost-endpoint", help="Change default FROST server URL."
    ),
    exclude: Optional[str] = typer.Option(
        None, "--exclude", help="Pass a list of sensor MAC addresses to exclude from the stream."
    ),
):
    """Push available sensor data to FROST server."""
    from sensorthings_utils.main import push_available
    
    console.print("[bold]Starting data stream to FROST server...[/bold]")
    push_available(exclude=exclude, frost_endpoint=frost_endpoint)


def _generate_config(
    sensor_model: str = typer.Argument(
        ..., help="Sensor model: milesight.am103l, milesight.am308l, or netatmo.nws03"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (defaults to sensor_configs/{sensor_id}.yaml)"
    ),
):
    """Generate sensor configuration file from template."""
    from .config_generator import generate_config_from_template
    from sensorthings_utils.transformers.types import SupportedSensors
    
    try:
        sensor_model_enum = SupportedSensors(sensor_model)
    except ValueError:
        console.print(f"[bold red]Error:[/bold red] Unsupported sensor model: {sensor_model}")
        console.print("Supported models: milesight.am103l, milesight.am308l, netatmo.nws03")
        raise typer.Exit(1)
    
    # Collect user inputs with rich prompts
    console.print(Panel.fit(
        f"[bold]Generating configuration for {sensor_model_enum.value}[/bold]",
        border_style="blue"
    ))
    
    sensor_id = Prompt.ask("Sensor ID/Name", default="").strip()
    if not sensor_id:
        console.print("[bold red]Error:[/bold red] Sensor ID is required")
        raise typer.Exit(1)
    
    console.print("\n[bold]Thing Configuration:[/bold]")
    thing_name = Prompt.ask("Thing name", default="").strip()
    if not thing_name:
        console.print("[bold red]Error:[/bold red] Thing name is required")
        raise typer.Exit(1)
    
    thing_description = Prompt.ask("Thing description", default="").strip()
    if not thing_description:
        console.print("[bold red]Error:[/bold red] Thing description is required")
        raise typer.Exit(1)
    
    console.print("\n[bold]Location Configuration:[/bold]")
    location_name = Prompt.ask("Location name", default="").strip()
    if not location_name:
        console.print("[bold red]Error:[/bold red] Location name is required")
        raise typer.Exit(1)
    
    location_description = Prompt.ask("Location description", default="").strip()
    if not location_description:
        console.print("[bold red]Error:[/bold red] Location description is required")
        raise typer.Exit(1)
    
    try:
        longitude = float(Prompt.ask("Longitude", default="").strip())
        latitude = float(Prompt.ask("Latitude", default="").strip())
    except ValueError:
        console.print("[bold red]Error:[/bold red] Longitude and latitude must be valid numbers")
        raise typer.Exit(1)
    
    # Generate config
    try:
        output_path = generate_config_from_template(
            sensor_model=sensor_model_enum,
            sensor_id=sensor_id,
            thing_name=thing_name,
            thing_description=thing_description,
            location_name=location_name,
            location_description=location_description,
            longitude=longitude,
            latitude=latitude,
            output_path=output_path,
        )
        console.print(f"\n[bold green]✓ Configuration generated successfully:[/bold green] {output_path}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"  1. Review the configuration file")
        console.print(f"  2. Validate it using: [cyan]stu validate {output_path}[/cyan]")
    except Exception as e:
        console.print(f"\n[bold red]Error generating configuration:[/bold red] {e}")
        import traceback
        console.print_exception()
        raise typer.Exit(1)


def _setup(
    all: bool = typer.Option(False, "--all", help="Setup all credential types."),
    frost: bool = typer.Option(False, "--frost", help="Setup FROST credentials."),
    postgres: bool = typer.Option(False, "--postgres", help="Setup PostgreSQL credentials."),
    mqtt: bool = typer.Option(False, "--mqtt", help="Setup MQTT credentials."),
    tomcat: bool = typer.Option(False, "--tomcat", help="Setup Tomcat users (webapp authentication)."),
    token: bool = typer.Option(False, "--token", help="Setup a token file (freeform JSON)."),
):
    """Interactive setup for credential files."""
    # Create a simple args-like object for backward compatibility
    class Args:
        def __init__(self):
            self.all = all
            self.frost = frost
            self.postgres = postgres
            self.mqtt = mqtt
            self.tomcat = tomcat
            self.token = token
    
    args = Args()
    _setup_credentials(args)


# Register commands
app.command(name="validate")(_validate)
app.command(name="start")(_push_available)
app.command(name="generate-config")(_generate_config)
app.command(name="setup")(_setup)


def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
