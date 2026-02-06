"""Application management functions."""

# standard
import inspect
import json
import logging
from pathlib import Path

# external
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import print as rprint

# internal
from ..paths import CREDENTIALS_DIR, TOKENS_DIR, VARIABLE_APPLICATION_CONFIG_FILE
from ..connections import HTTPSensorApplicationConnection, MQTTSensorApplicationConnection

logger = logging.getLogger("st-utils")
console = Console()


def _get_application_status():
    """
    Get status of all configured applications.
    
    Returns:
        Dictionary mapping app_name to dict with:
            - 'auth_type': 'credentials' or 'tokens'
            - 'configured': bool (whether auth is set up)
            - 'connection_class': str
    """
    app_status = {}
    
    # Read application config file
    if not VARIABLE_APPLICATION_CONFIG_FILE.exists() or not VARIABLE_APPLICATION_CONFIG_FILE.is_file():
        return app_status
    
    try:
        with open(VARIABLE_APPLICATION_CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Could not read application config: {e}")
        return app_status
    
    if not config or "applications" not in config:
        return app_status
    
    # Read application credentials if they exist
    app_creds = {}
    app_creds_file = CREDENTIALS_DIR / "application_credentials.json"
    if app_creds_file.exists():
        try:
            with open(app_creds_file, "r") as f:
                app_creds = json.load(f)
        except Exception:
            pass
    
    # Check each application
    for app_name, app_config in config["applications"].items():
        auth_type = app_config.get("authentication_type", "credentials")
        connection_class = app_config.get("connection_class", "Unknown")
        
        configured = False
        if auth_type == "credentials":
            # Check if app exists in application_credentials.json
            configured = app_name in app_creds
        elif auth_type == "tokens":
            # Check if token file exists
            token_file = TOKENS_DIR / f"{app_name}.json"
            configured = token_file.exists()
        
        app_status[app_name] = {
            "auth_type": auth_type,
            "configured": configured,
            "connection_class": connection_class,
        }
    
    return app_status


def _get_available_connection_classes(connection_type: str):
    """
    Get available connection classes for a given connection type.
    
    Args:
        connection_type: "http" or "mqtt"
        
    Returns:
        List of connection class names
    """
    import sensorthings_utils.connections as connections_module
    
    base_class = HTTPSensorApplicationConnection if connection_type == "http" else MQTTSensorApplicationConnection
    available_classes = []
    
    # Get all members of the connections module
    for name, obj in inspect.getmembers(connections_module):
        # Check if it's a class, ends with "Connection", and is a subclass of the base class
        if (inspect.isclass(obj) and 
            name.endswith("Connection") and 
            issubclass(obj, base_class) and 
            obj is not base_class):
            available_classes.append(name)
    
    return sorted(available_classes)


def _show_application_status():
    """Display status of all configured applications and allow setup of missing ones."""
    from .credentials import _setup_application_credentials
    from .tokens import _setup_token_file
    
    while True:
        app_status = _get_application_status()
        
        if not app_status:
            console.print(Panel(
                "[yellow]No applications configured in application-configs.yml[/yellow]",
                border_style="yellow"
            ))
            return
        
        # Create status tables
        apps_by_auth = {"credentials": [], "tokens": []}
        unconfigured_apps = []
        
        for app_name, status in app_status.items():
            apps_by_auth[status["auth_type"]].append((app_name, status))
            if not status["configured"]:
                unconfigured_apps.append((app_name, status))
        
        # Show credentials-based apps
        if apps_by_auth["credentials"]:
            creds_table = Table(title="📋 Applications using Credentials", show_header=True, header_style="bold")
            creds_table.add_column("Status", style="magenta", width=8)
            creds_table.add_column("Application", style="cyan")
            creds_table.add_column("Connection", style="blue")
            creds_table.add_column("Notes", style="yellow")
            
            for app_name, status in apps_by_auth["credentials"]:
                status_icon = "[green]✓[/green]" if status["configured"] else "[red]✗[/red]"
                notes = "" if status["configured"] else "[yellow]⚠️  Missing in application_credentials.json[/yellow]"
                creds_table.add_row(status_icon, app_name, status['connection_class'], notes)
            
            console.print(creds_table)
        
        # Show token-based apps
        if apps_by_auth["tokens"]:
            tokens_table = Table(title="🔑 Applications using Tokens", show_header=True, header_style="bold")
            tokens_table.add_column("Status", style="magenta", width=8)
            tokens_table.add_column("Application", style="cyan")
            tokens_table.add_column("Connection", style="blue")
            tokens_table.add_column("Notes", style="yellow")
            
            for app_name, status in apps_by_auth["tokens"]:
                status_icon = "[green]✓[/green]" if status["configured"] else "[red]✗[/red]"
                notes = "" if status["configured"] else f"[yellow]⚠️  Missing token file: {app_name}.json[/yellow]"
                tokens_table.add_row(status_icon, app_name, status['connection_class'], notes)
            
            console.print(tokens_table)
        
        # Summary
        total = len(app_status)
        configured = sum(1 for s in app_status.values() if s["configured"])
        console.print(f"\n[bold]Summary:[/bold] [green]{configured}[/green]/[cyan]{total}[/cyan] applications configured")
        
        # Interactive setup for unconfigured apps
        if unconfigured_apps:
            console.print(Panel.fit(
                "[bold]Unconfigured Applications - Quick Setup[/bold]",
                border_style="yellow"
            ))
            
            unconfig_table = Table(show_header=False, box=None, padding=(0, 2))
            for i, (app_name, status) in enumerate(unconfigured_apps, 1):
                auth_type_label = "Credentials" if status["auth_type"] == "credentials" else "Token file"
                unconfig_table.add_row(f"[cyan][{i}][/cyan]", f"{app_name} ([dim]{auth_type_label}[/dim])")
            unconfig_table.add_row(f"[cyan][{len(unconfigured_apps) + 1}][/cyan]", "[dim]Skip / Manage applications[/dim]")
            
            console.print(unconfig_table)
            
            choice = IntPrompt.ask(
                f"\nSelect option",
                default=len(unconfigured_apps) + 1
            )
            
            try:
                idx = choice - 1
                if 0 <= idx < len(unconfigured_apps):
                    app_name, status = unconfigured_apps[idx]
                    
                    if status["auth_type"] == "credentials":
                        # Set up using credentials
                        if _setup_application_credentials(app_name=app_name):
                            console.print(f"\n[bold green]✓ Successfully set up credentials for {app_name}[/bold green]")
                        else:
                            console.print(f"\n[yellow]⚠️  Setup cancelled or incomplete for {app_name}[/yellow]")
                    else:
                        # Set up using token file
                        if _setup_token_file(token_name=app_name):
                            console.print(f"\n[bold green]✓ Successfully set up token file for {app_name}[/bold green]")
                        else:
                            console.print(f"\n[yellow]⚠️  Setup cancelled or incomplete for {app_name}[/yellow]")
                    
                    # Continue loop to refresh status and show remaining apps
                    continue
                elif idx == len(unconfigured_apps):
                    # Skip/Manage - proceed to management menu
                    pass
                else:
                    console.print("[red]Invalid selection.[/red]")
                    continue
            except (ValueError, IndexError):
                # User pressed Enter or entered non-numeric - proceed to management menu
                pass
        
        # Management menu
        console.print(Panel.fit(
            "[bold]Application Management[/bold]",
            border_style="blue"
        ))
        
        app_list = list(app_status.items())
        manage_table = Table(show_header=False, box=None, padding=(0, 2))
        for i, (app_name, status) in enumerate(app_list, 1):
            status_icon = "[green]✓[/green]" if status["configured"] else "[red]✗[/red]"
            auth_label = "Credentials" if status["auth_type"] == "credentials" else "Tokens"
            manage_table.add_row(f"[cyan][{i}][/cyan]", f"{status_icon} {app_name} ([dim]{auth_label}[/dim])")
        manage_table.add_row(f"[cyan][{len(app_list) + 1}][/cyan]", "[dim]Back to main menu[/dim]")
        
        console.print(manage_table)
        
        choice = IntPrompt.ask(
            f"\nSelect option",
            default=len(app_list) + 1
        )
        
        try:
            idx = choice - 1
            if 0 <= idx < len(app_list):
                app_name, status = app_list[idx]
                _manage_application(app_name)
                # Continue loop to refresh status
                continue
            elif idx == len(app_list):
                # Back to main menu - exit the loop
                break
            else:
                console.print("[red]Invalid selection.[/red]")
                continue
        except (ValueError, IndexError):
            # User pressed Enter or entered non-numeric - exit the loop
            break


def _get_connection_type_from_config(app_config: dict) -> str:
    """Determine connection type (http/mqtt) from application config."""
    # MQTT connections typically have 'host', 'port', and 'topic'
    if "host" in app_config or "topic" in app_config:
        return "mqtt"
    # HTTP connections typically have 'interval'
    elif "interval" in app_config:
        return "http"
    # Default to http if unclear
    return "http"


def _manage_application(app_name: str):
    """Manage a specific application - modify or remove."""
    while True:
        menu_table = Table(show_header=False, box=None, padding=(0, 2))
        menu_table.add_row("[cyan][1][/cyan]", "Modify configuration")
        menu_table.add_row("[cyan][2][/cyan]", "Remove application")
        menu_table.add_row("[cyan][3][/cyan]", "Back to application list")
        
        console.print(Panel.fit(
            menu_table,
            title=f"[bold]Manage Application: {app_name}[/bold]",
            border_style="blue"
        ))
        
        choice = Prompt.ask("\nSelect an option", default="3", choices=["1", "2", "3"])
        
        if choice == "1":
            try:
                if _modify_application_config(app_name):
                    console.print(f"\n[bold green]✓ Successfully modified {app_name}[/bold green]")
                    Prompt.ask("\nPress Enter to continue", default="")
                    break  # Exit to refresh the list
            except KeyboardInterrupt:
                console.print("\n\n[yellow]Cancelled modification.[/yellow]")
        elif choice == "2":
            try:
                if _remove_application(app_name):
                    console.print(f"\n[bold green]✓ Successfully removed {app_name}[/bold green]")
                    Prompt.ask("\nPress Enter to continue", default="")
                    break  # Exit to refresh the list
            except KeyboardInterrupt:
                console.print("\n\n[yellow]Cancelled removal.[/yellow]")
        elif choice == "3":
            break
        else:
            console.print("[red]Invalid option. Please try again.[/red]")


def _modify_application_config(app_name: str) -> bool:
    """Modify an existing application configuration."""
    # Load existing config
    if not VARIABLE_APPLICATION_CONFIG_FILE.exists() or not VARIABLE_APPLICATION_CONFIG_FILE.is_file():
        console.print("[bold red]Error:[/bold red] Application config file not found")
        return False
    
    try:
        with open(VARIABLE_APPLICATION_CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        console.print(f"[bold red]Error reading config file:[/bold red] {e}")
        return False
    
    if "applications" not in config or app_name not in config["applications"]:
        console.print(f"[bold red]Error:[/bold red] Application '{app_name}' not found in config")
        return False
    
    current_config = config["applications"][app_name].copy()
    connection_type = _get_connection_type_from_config(current_config)
    
    console.print(Panel.fit(
        f"[bold]Modify Application: {app_name}[/bold]\n[dim](Press Enter to keep current value)[/dim]",
        border_style="blue"
    ))
    
    # Show current values and allow modification
    new_config = {}
    
    # Authentication type
    current_auth = current_config.get("authentication_type", "credentials")
    console.print(f"\n[bold]Current authentication type:[/bold] {current_auth}")
    auth_table = Table(show_header=False, box=None, padding=(0, 2))
    auth_table.add_row("[cyan][1][/cyan]", "tokens")
    auth_table.add_row("[cyan][2][/cyan]", "credentials")
    console.print(auth_table)
    
    choice = Prompt.ask(
        f"Select authentication type",
        default="",
        choices=["1", "2", ""]
    )
    if not choice:
        new_config["authentication_type"] = current_auth
    elif choice == "1":
        new_config["authentication_type"] = "tokens"
    elif choice == "2":
        new_config["authentication_type"] = "credentials"
    
    # Connection class
    current_class = current_config.get("connection_class", "")
    available_classes = _get_available_connection_classes(connection_type)
    if not available_classes:
        console.print(f"\n[bold red]No {connection_type.upper()} connection classes found[/bold red]")
        return False
    
    console.print(f"\n[bold]Current connection class:[/bold] {current_class}")
    console.print(f"[bold]Available {connection_type.upper()} connection classes:[/bold]")
    class_table = Table(show_header=False, box=None, padding=(0, 2))
    for i, class_name in enumerate(available_classes, 1):
        marker = " [dim]<-- current[/dim]" if class_name == current_class else ""
        class_table.add_row(f"[cyan][{i}][/cyan]", f"{class_name}{marker}")
    console.print(class_table)
    
    choice = Prompt.ask(
        f"Select connection class",
        default="",
        choices=[str(i) for i in range(1, len(available_classes) + 1)] + [""]
    )
    if not choice:
        new_config["connection_class"] = current_class
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available_classes):
                new_config["connection_class"] = available_classes[idx]
        except ValueError:
            console.print("[red]Invalid input.[/red]")
            return False
    
    # HTTP-specific fields
    if connection_type == "http":
        current_interval = current_config.get("interval", "")
        new_interval = Prompt.ask(
            f"\nRequest Interval (seconds)",
            default=str(current_interval) if current_interval else ""
        )
        if new_interval:
            try:
                new_config["interval"] = int(new_interval)
            except ValueError:
                console.print("[yellow]Invalid interval value. Keeping current value.[/yellow]")
                if current_interval:
                    new_config["interval"] = current_interval
        else:
            if current_interval:
                new_config["interval"] = current_interval
        
        current_max_retries = current_config.get("max_retries", "")
        new_max_retries = Prompt.ask(
            "Max retries",
            default=str(current_max_retries) if current_max_retries else ""
        )
        if new_max_retries:
            try:
                new_config["max_retries"] = int(new_max_retries)
            except ValueError:
                console.print("[yellow]Invalid max_retries value. Keeping current value.[/yellow]")
                new_config["max_retries"] = current_max_retries if current_max_retries else None
        else:
            if current_max_retries:
                new_config["max_retries"] = current_max_retries
        
        current_expected_sensors = current_config.get("expected_sensors", "")
        new_expected_sensors = Prompt.ask(
            "Expected sensors",
            default=str(current_expected_sensors) if current_expected_sensors else ""
        )
        if new_expected_sensors:
            try:
                new_config["expected_sensors"] = int(new_expected_sensors)
            except ValueError:
                console.print("[yellow]Invalid expected_sensors value. Keeping current value.[/yellow]")
                new_config["expected_sensors"] = current_expected_sensors if current_expected_sensors else None
        else:
            if current_expected_sensors:
                new_config["expected_sensors"] = current_expected_sensors
    
    # MQTT-specific fields
    else:
        current_max_retries = current_config.get("max_retries", "")
        new_max_retries = Prompt.ask(
            "\nMax retries",
            default=str(current_max_retries) if current_max_retries else ""
        )
        if new_max_retries:
            try:
                new_config["max_retries"] = int(new_max_retries)
            except ValueError:
                console.print("[yellow]Invalid max_retries value. Keeping current value.[/yellow]")
                new_config["max_retries"] = current_max_retries if current_max_retries else None
        else:
            if current_max_retries:
                new_config["max_retries"] = current_max_retries
        
        current_host = current_config.get("host", "")
        new_host = Prompt.ask("Host", default=current_host)
        new_config["host"] = new_host if new_host else current_host
        
        current_port = current_config.get("port", 8883)
        new_port = Prompt.ask("Port", default=str(current_port))
        if new_port:
            try:
                new_config["port"] = int(new_port)
            except ValueError:
                console.print("[yellow]Invalid port value. Keeping current value.[/yellow]")
                new_config["port"] = current_port
        else:
            new_config["port"] = current_port
        
        current_topic = current_config.get("topic", "")
        new_topic = Prompt.ask("Topic", default=current_topic)
        new_config["topic"] = new_topic if new_topic else current_topic
        
        current_expected_sensors = current_config.get("expected_sensors", "")
        new_expected_sensors = Prompt.ask(
            "Expected sensors",
            default=str(current_expected_sensors) if current_expected_sensors else ""
        )
        if new_expected_sensors:
            try:
                new_config["expected_sensors"] = int(new_expected_sensors)
            except ValueError:
                console.print("[yellow]Invalid expected_sensors value. Keeping current value.[/yellow]")
                new_config["expected_sensors"] = current_expected_sensors if current_expected_sensors else None
        else:
            if current_expected_sensors:
                new_config["expected_sensors"] = current_expected_sensors
    
    # Update config
    config["applications"][app_name] = new_config
    
    # Save config
    try:
        with open(VARIABLE_APPLICATION_CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
        return True
    except Exception as e:
        console.print(f"[bold red]Error saving config file:[/bold red] {e}")
        return False


def _remove_application(app_name: str) -> bool:
    """Remove an application from config and optionally remove credentials/tokens."""
    # Load existing config
    if not VARIABLE_APPLICATION_CONFIG_FILE.exists() or not VARIABLE_APPLICATION_CONFIG_FILE.is_file():
        console.print("[bold red]Error:[/bold red] Application config file not found")
        return False
    
    try:
        with open(VARIABLE_APPLICATION_CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        console.print(f"[bold red]Error reading config file:[/bold red] {e}")
        return False
    
    if "applications" not in config or app_name not in config["applications"]:
        console.print(f"[bold red]Error:[/bold red] Application '{app_name}' not found in config")
        return False
    
    app_config = config["applications"][app_name]
    auth_type = app_config.get("authentication_type", "credentials")
    
    # Confirm removal
    warning_text = f"[bold yellow]⚠️  WARNING:[/bold yellow] This will remove '{app_name}' from the configuration.\n"
    if auth_type == "credentials":
        warning_text += "The application credentials in application_credentials.json will NOT be removed automatically."
    else:
        token_file = TOKENS_DIR / f"{app_name}.json"
        if token_file.exists():
            warning_text += f"Token file: {token_file} exists and will NOT be removed automatically."
    
    console.print(Panel(warning_text, border_style="yellow"))
    
    confirm = Confirm.ask("\nAre you sure you want to remove this application?", default=False)
    if not confirm:
        console.print("[yellow]Cancelled.[/yellow]")
        return False
    
    # Optionally remove credentials/tokens
    remove_auth = False
    if auth_type == "credentials":
        app_creds_file = CREDENTIALS_DIR / "application_credentials.json"
        if app_creds_file.exists():
            try:
                with open(app_creds_file, "r") as f:
                    app_creds = json.load(f)
                if app_name in app_creds:
                    remove_auth = Confirm.ask(
                        "\nAlso remove credentials from application_credentials.json?",
                        default=False
                    )
            except Exception:
                pass
    else:  # tokens
        token_file = TOKENS_DIR / f"{app_name}.json"
        if token_file.exists():
            remove_auth = Confirm.ask(
                f"\nAlso delete token file {token_file.name}?",
                default=False
            )
    
    # Remove from config
    del config["applications"][app_name]
    
    # Save config
    try:
        with open(VARIABLE_APPLICATION_CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
    except Exception as e:
        console.print(f"[bold red]Error saving config file:[/bold red] {e}")
        return False
    
    # Remove credentials/tokens if requested
    if remove_auth:
        if auth_type == "credentials":
            try:
                with open(app_creds_file, "r") as f:
                    app_creds = json.load(f)
                if app_name in app_creds:
                    del app_creds[app_name]
                    with open(app_creds_file, "w") as f:
                        json.dump(app_creds, f, indent=4)
                    console.print(f"[green]✓ Removed credentials for {app_name}[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not remove credentials:[/yellow] {e}")
        else:  # tokens
            try:
                if token_file.exists():
                    token_file.unlink()
                    console.print(f"[green]✓ Deleted token file {token_file.name}[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not delete token file:[/yellow] {e}")
    
    return True


def _add_application_to_config():
    """Add a new application to application-configs.yml.
    
    Returns:
        Tuple of (success: bool, app_name: str | None, auth_type: str | None)
        On success, returns (True, app_name, auth_type)
        On failure, returns (False, None, None)
    """
    console.print(Panel.fit(
        "[bold]Add Application to Config[/bold]",
        border_style="blue"
    ))
    
    # Step 1: Ask for connection type with numeric selection
    conn_table = Table(show_header=False, box=None, padding=(0, 2))
    conn_table.add_row("[cyan][1][/cyan]", "HTTP")
    conn_table.add_row("[cyan][2][/cyan]", "MQTT")
    console.print("\n[bold]Connection type:[/bold]")
    console.print(conn_table)
    
    while True:
        choice = IntPrompt.ask("Select connection type", default=1)
        if choice in [1, 2]:
            break
        console.print("[red]Invalid selection. Please enter 1 or 2.[/red]")
    connection_type = "http" if choice == 1 else "mqtt"
    
    # Step 2: Ask for application name
    app_name = Prompt.ask("\nApplication name")
    if not app_name:
        console.print("[bold red]Application name cannot be empty.[/bold red]")
        return (False, None, None)
    
    # Load existing config
    config = {}
    if VARIABLE_APPLICATION_CONFIG_FILE.exists() and VARIABLE_APPLICATION_CONFIG_FILE.is_file():
        try:
            with open(VARIABLE_APPLICATION_CONFIG_FILE, "r") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            console.print(f"[bold red]Error reading config file:[/bold red] {e}")
            return (False, None, None)
    else:
        # File doesn't exist, create new structure
        config = {"applications": {}}
    
    # Check if application already exists
    if "applications" in config and app_name in config["applications"]:
        overwrite = Confirm.ask(f"\nApplication '{app_name}' already exists. Overwrite?", default=False)
        if not overwrite:
            console.print("[yellow]Cancelled.[/yellow]")
            return (False, None, None)
    
    # Initialize applications dict if needed
    if "applications" not in config:
        config["applications"] = {}
    
    # Build application config
    app_config = {}
    
    # Common fields - Authentication type with numeric selection
    auth_table = Table(show_header=False, box=None, padding=(0, 2))
    auth_table.add_row("[cyan][1][/cyan]", "tokens")
    auth_table.add_row("[cyan][2][/cyan]", "credentials")
    console.print("\n[bold]Authentication type:[/bold]")
    console.print(auth_table)
    
    while True:
        choice = IntPrompt.ask("Select authentication type", default=2)
        if choice in [1, 2]:
            break
        console.print("[red]Invalid selection. Please enter 1 or 2.[/red]")
    app_config["authentication_type"] = "tokens" if choice == 1 else "credentials"
    
    # Connection class - show available options
    available_classes = _get_available_connection_classes(connection_type)
    if not available_classes:
        console.print(f"\n[bold red]No {connection_type.upper()} connection classes found in connections.py[/bold red]")
        return (False, None, None)
    
    class_table = Table(show_header=False, box=None, padding=(0, 2))
    for i, class_name in enumerate(available_classes, 1):
        class_table.add_row(f"[cyan][{i}][/cyan]", class_name)
    console.print(f"\n[bold]Available {connection_type.upper()} connection classes:[/bold]")
    console.print(class_table)
    
    choice = IntPrompt.ask(
        f"Select connection class",
        default=1
    )
    app_config["connection_class"] = available_classes[choice - 1]
    
    if connection_type == "http":
        # HTTP-specific fields
        interval = Prompt.ask("\nRequest Interval (seconds)", default="")
        if interval:
            try:
                app_config["interval"] = int(interval)
            except ValueError:
                console.print("[yellow]Invalid interval value. Skipping.[/yellow]")
        
        max_retries = Prompt.ask("Max retries", default="")
        if max_retries:
            try:
                app_config["max_retries"] = int(max_retries)
            except ValueError:
                console.print("[yellow]Invalid max_retries value. Skipping.[/yellow]")
        
        expected_sensors = Prompt.ask("Expected sensors", default="")
        if expected_sensors:
            try:
                app_config["expected_sensors"] = int(expected_sensors)
            except ValueError:
                console.print("[yellow]Invalid expected_sensors value. Skipping.[/yellow]")
    
    else:  # mqtt
        # MQTT-specific fields
        max_retries = Prompt.ask("\nMax retries", default="")
        if max_retries:
            try:
                app_config["max_retries"] = int(max_retries)
            except ValueError:
                console.print("[yellow]Invalid max_retries value. Skipping.[/yellow]")
        
        host = Prompt.ask("Host")
        if not host:
            console.print("[bold red]Host is required for MQTT applications.[/bold red]")
            return (False, None, None)
        app_config["host"] = host
        
        port = Prompt.ask("Port", default="8883")
        try:
            app_config["port"] = int(port)
        except ValueError:
            console.print("[yellow]Invalid port value. Using default 8883.[/yellow]")
            app_config["port"] = 8883
        
        topic = Prompt.ask("Topic")
        if not topic:
            console.print("[bold red]Topic is required for MQTT applications.[/bold red]")
            return (False, None, None)
        app_config["topic"] = topic
        
        expected_sensors = Prompt.ask("Expected sensors", default="")
        if expected_sensors:
            try:
                app_config["expected_sensors"] = int(expected_sensors)
            except ValueError:
                console.print("[yellow]Invalid expected_sensors value. Skipping.[/yellow]")
    
    # Add application to config
    config["applications"][app_name] = app_config
    
    # Save config
    try:
        with open(VARIABLE_APPLICATION_CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
        console.print(f"\n[bold green]✓ Added '{app_name}' to {VARIABLE_APPLICATION_CONFIG_FILE.name}[/bold green]")
        auth_type = app_config.get("authentication_type", "credentials")
        return (True, app_name, auth_type)
    except Exception as e:
        console.print(f"[bold red]Error saving config file:[/bold red] {e}")
        return (False, None, None)
