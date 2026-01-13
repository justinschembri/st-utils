"""Application management functions."""

# standard
import inspect
import json
import logging
from pathlib import Path

# external
import yaml

# internal
from ..paths import CREDENTIALS_DIR, TOKENS_DIR, APPLICATION_CONFIG_FILE
from ..connections import HTTPSensorApplicationConnection, MQTTSensorApplicationConnection

logger = logging.getLogger("st-utils")


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
    if not APPLICATION_CONFIG_FILE.exists() or not APPLICATION_CONFIG_FILE.is_file():
        return app_status
    
    try:
        with open(APPLICATION_CONFIG_FILE, "r") as f:
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
            print("\nNo applications configured in application-configs.yml")
            return
        
        print("\n" + "=" * 50)
        print("Configured Applications")
        print("=" * 50)
        
        apps_by_auth = {"credentials": [], "tokens": []}
        unconfigured_apps = []
        
        for app_name, status in app_status.items():
            apps_by_auth[status["auth_type"]].append((app_name, status))
            if not status["configured"]:
                unconfigured_apps.append((app_name, status))
        
        # Show credentials-based apps
        if apps_by_auth["credentials"]:
            print("\n📋 Applications using Credentials:")
            for app_name, status in apps_by_auth["credentials"]:
                status_icon = "✓" if status["configured"] else "✗"
                print(f"  {status_icon} {app_name}")
                print(f"      Connection: {status['connection_class']}")
                if not status["configured"]:
                    print(f"      ⚠️  Missing in application_credentials.json")
        
        # Show token-based apps
        if apps_by_auth["tokens"]:
            print("\n🔑 Applications using Tokens:")
            for app_name, status in apps_by_auth["tokens"]:
                status_icon = "✓" if status["configured"] else "✗"
                print(f"  {status_icon} {app_name}")
                print(f"      Connection: {status['connection_class']}")
                if not status["configured"]:
                    print(f"      ⚠️  Missing token file: {app_name}.json")
        
        # Summary
        total = len(app_status)
        configured = sum(1 for s in app_status.values() if s["configured"])
        print(f"\nSummary: {configured}/{total} applications configured")
        
        # Interactive setup for unconfigured apps
        if unconfigured_apps:
            print("\n" + "=" * 50)
            print("Unconfigured Applications - Quick Setup")
            print("=" * 50)
            print("Select an application to set up (or press Enter to skip):")
            
            for i, (app_name, status) in enumerate(unconfigured_apps, 1):
                auth_type_label = "Credentials" if status["auth_type"] == "credentials" else "Token file"
                print(f"  [{i}] {app_name} ({auth_type_label})")
            print(f"  [{len(unconfigured_apps) + 1}] Skip / Manage applications")
            
            choice = input(f"\nSelect option [1-{len(unconfigured_apps) + 1}]: ").strip()
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(unconfigured_apps):
                    app_name, status = unconfigured_apps[idx]
                    
                    if status["auth_type"] == "credentials":
                        # Set up using credentials
                        if _setup_application_credentials(app_name=app_name):
                            print(f"\n✓ Successfully set up credentials for {app_name}")
                        else:
                            print(f"\n⚠️  Setup cancelled or incomplete for {app_name}")
                    else:
                        # Set up using token file
                        if _setup_token_file(token_name=app_name):
                            print(f"\n✓ Successfully set up token file for {app_name}")
                        else:
                            print(f"\n⚠️  Setup cancelled or incomplete for {app_name}")
                    
                    # Continue loop to refresh status and show remaining apps
                    continue
                elif idx == len(unconfigured_apps):
                    # Skip/Manage - proceed to management menu
                    pass
                else:
                    print("Invalid selection.")
                    continue
            except ValueError:
                # User pressed Enter or entered non-numeric - proceed to management menu
                pass
        
        # Management menu
        print("\n" + "=" * 50)
        print("Application Management")
        print("=" * 50)
        print("Select an application to manage:")
        
        app_list = list(app_status.items())
        for i, (app_name, status) in enumerate(app_list, 1):
            status_icon = "✓" if status["configured"] else "✗"
            auth_label = "Credentials" if status["auth_type"] == "credentials" else "Tokens"
            print(f"  [{i}] {status_icon} {app_name} ({auth_label})")
        print(f"  [{len(app_list) + 1}] Back to main menu")
        
        choice = input(f"\nSelect option [1-{len(app_list) + 1}]: ").strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(app_list):
                app_name, status = app_list[idx]
                _manage_application(app_name)
                # Continue loop to refresh status
                continue
            elif idx == len(app_list):
                # Back to main menu - exit the loop
                break
            else:
                print("Invalid selection.")
                continue
        except ValueError:
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
        print("\n" + "=" * 50)
        print(f"Manage Application: {app_name}")
        print("=" * 50)
        print("[1] Modify configuration")
        print("[2] Remove application")
        print("[3] Back to application list")
        
        choice = input("\nSelect an option [3]: ").strip() or "3"
        
        if choice == "1":
            try:
                if _modify_application_config(app_name):
                    print(f"\n✓ Successfully modified {app_name}")
                    input("\nPress Enter to continue...")
                    break  # Exit to refresh the list
            except KeyboardInterrupt:
                print("\n\nCancelled modification.")
        elif choice == "2":
            try:
                if _remove_application(app_name):
                    print(f"\n✓ Successfully removed {app_name}")
                    input("\nPress Enter to continue...")
                    break  # Exit to refresh the list
            except KeyboardInterrupt:
                print("\n\nCancelled removal.")
        elif choice == "3":
            break
        else:
            print("Invalid option. Please try again.")


def _modify_application_config(app_name: str) -> bool:
    """Modify an existing application configuration."""
    # Load existing config
    if not APPLICATION_CONFIG_FILE.exists() or not APPLICATION_CONFIG_FILE.is_file():
        print("Error: Application config file not found")
        return False
    
    try:
        with open(APPLICATION_CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error reading config file: {e}")
        return False
    
    if "applications" not in config or app_name not in config["applications"]:
        print(f"Error: Application '{app_name}' not found in config")
        return False
    
    current_config = config["applications"][app_name].copy()
    connection_type = _get_connection_type_from_config(current_config)
    
    print(f"\n--- Modify Application: {app_name} ---")
    print("(Press Enter to keep current value)")
    
    # Show current values and allow modification
    new_config = {}
    
    # Authentication type
    current_auth = current_config.get("authentication_type", "credentials")
    print(f"\nCurrent authentication type: {current_auth}")
    while True:
        print("  [1] tokens")
        print("  [2] credentials")
        choice = input(f"Select authentication type [Enter to keep '{current_auth}']: ").strip()
        if not choice:
            new_config["authentication_type"] = current_auth
            break
        elif choice == "1":
            new_config["authentication_type"] = "tokens"
            break
        elif choice == "2":
            new_config["authentication_type"] = "credentials"
            break
        else:
            print("Invalid selection. Please enter 1 or 2, or press Enter to keep current.")
    
    # Connection class
    current_class = current_config.get("connection_class", "")
    available_classes = _get_available_connection_classes(connection_type)
    if not available_classes:
        print(f"\nNo {connection_type.upper()} connection classes found")
        return False
    
    print(f"\nCurrent connection class: {current_class}")
    print(f"Available {connection_type.upper()} connection classes:")
    for i, class_name in enumerate(available_classes, 1):
        marker = " <-- current" if class_name == current_class else ""
        print(f"  [{i}] {class_name}{marker}")
    
    while True:
        choice = input(f"Select connection class [Enter to keep '{current_class}']: ").strip()
        if not choice:
            new_config["connection_class"] = current_class
            break
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available_classes):
                new_config["connection_class"] = available_classes[idx]
                break
            else:
                print(f"Invalid selection. Please enter 1-{len(available_classes)} or press Enter.")
        except ValueError:
            print("Invalid input. Please enter a number or press Enter.")
    
    # HTTP-specific fields
    if connection_type == "http":
        current_interval = current_config.get("interval", "")
        new_interval = input(f"\nRequest Interval (seconds) [Current: {current_interval}, Enter to keep]: ").strip()
        if new_interval:
            try:
                new_config["interval"] = int(new_interval)
            except ValueError:
                print("Invalid interval value. Keeping current value.")
                new_config["interval"] = current_interval
        else:
            if current_interval:
                new_config["interval"] = current_interval
        
        current_max_retries = current_config.get("max_retries", "")
        new_max_retries = input(f"Max retries [Current: {current_max_retries}, Enter to keep]: ").strip()
        if new_max_retries:
            try:
                new_config["max_retries"] = int(new_max_retries)
            except ValueError:
                print("Invalid max_retries value. Keeping current value.")
                new_config["max_retries"] = current_max_retries if current_max_retries else None
        else:
            if current_max_retries:
                new_config["max_retries"] = current_max_retries
        
        current_expected_sensors = current_config.get("expected_sensors", "")
        new_expected_sensors = input(f"Expected sensors [Current: {current_expected_sensors}, Enter to keep]: ").strip()
        if new_expected_sensors:
            try:
                new_config["expected_sensors"] = int(new_expected_sensors)
            except ValueError:
                print("Invalid expected_sensors value. Keeping current value.")
                new_config["expected_sensors"] = current_expected_sensors if current_expected_sensors else None
        else:
            if current_expected_sensors:
                new_config["expected_sensors"] = current_expected_sensors
    
    # MQTT-specific fields
    else:
        current_max_retries = current_config.get("max_retries", "")
        new_max_retries = input(f"\nMax retries [Current: {current_max_retries}, Enter to keep]: ").strip()
        if new_max_retries:
            try:
                new_config["max_retries"] = int(new_max_retries)
            except ValueError:
                print("Invalid max_retries value. Keeping current value.")
                new_config["max_retries"] = current_max_retries if current_max_retries else None
        else:
            if current_max_retries:
                new_config["max_retries"] = current_max_retries
        
        current_host = current_config.get("host", "")
        new_host = input(f"Host [Current: {current_host}]: ").strip()
        if new_host:
            new_config["host"] = new_host
        else:
            new_config["host"] = current_host
        
        current_port = current_config.get("port", 8883)
        new_port = input(f"Port [Current: {current_port}]: ").strip()
        if new_port:
            try:
                new_config["port"] = int(new_port)
            except ValueError:
                print("Invalid port value. Keeping current value.")
                new_config["port"] = current_port
        else:
            new_config["port"] = current_port
        
        current_topic = current_config.get("topic", "")
        new_topic = input(f"Topic [Current: {current_topic}]: ").strip()
        if new_topic:
            new_config["topic"] = new_topic
        else:
            new_config["topic"] = current_topic
        
        current_expected_sensors = current_config.get("expected_sensors", "")
        new_expected_sensors = input(f"Expected sensors [Current: {current_expected_sensors}, Enter to keep]: ").strip()
        if new_expected_sensors:
            try:
                new_config["expected_sensors"] = int(new_expected_sensors)
            except ValueError:
                print("Invalid expected_sensors value. Keeping current value.")
                new_config["expected_sensors"] = current_expected_sensors if current_expected_sensors else None
        else:
            if current_expected_sensors:
                new_config["expected_sensors"] = current_expected_sensors
    
    # Update config
    config["applications"][app_name] = new_config
    
    # Save config
    try:
        with open(APPLICATION_CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config file: {e}")
        return False


def _remove_application(app_name: str) -> bool:
    """Remove an application from config and optionally remove credentials/tokens."""
    # Load existing config
    if not APPLICATION_CONFIG_FILE.exists() or not APPLICATION_CONFIG_FILE.is_file():
        print("Error: Application config file not found")
        return False
    
    try:
        with open(APPLICATION_CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error reading config file: {e}")
        return False
    
    if "applications" not in config or app_name not in config["applications"]:
        print(f"Error: Application '{app_name}' not found in config")
        return False
    
    app_config = config["applications"][app_name]
    auth_type = app_config.get("authentication_type", "credentials")
    
    # Confirm removal
    print(f"\n⚠️  WARNING: This will remove '{app_name}' from the configuration.")
    if auth_type == "credentials":
        print(f"   The application credentials in application_credentials.json will NOT be removed automatically.")
    else:
        token_file = TOKENS_DIR / f"{app_name}.json"
        if token_file.exists():
            print(f"   Token file: {token_file} exists and will NOT be removed automatically.")
    
    confirm = input("\nAre you sure you want to remove this application? (yes/no) [no]: ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
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
                    remove_auth_choice = input(f"\nAlso remove credentials from application_credentials.json? (yes/no) [no]: ").strip().lower()
                    if remove_auth_choice == "yes":
                        remove_auth = True
            except Exception:
                pass
    else:  # tokens
        token_file = TOKENS_DIR / f"{app_name}.json"
        if token_file.exists():
            remove_auth_choice = input(f"\nAlso delete token file {token_file.name}? (yes/no) [no]: ").strip().lower()
            if remove_auth_choice == "yes":
                remove_auth = True
    
    # Remove from config
    del config["applications"][app_name]
    
    # Save config
    try:
        with open(APPLICATION_CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
    except Exception as e:
        print(f"Error saving config file: {e}")
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
                    print(f"✓ Removed credentials for {app_name}")
            except Exception as e:
                print(f"Warning: Could not remove credentials: {e}")
        else:  # tokens
            try:
                if token_file.exists():
                    token_file.unlink()
                    print(f"✓ Deleted token file {token_file.name}")
            except Exception as e:
                print(f"Warning: Could not delete token file: {e}")
    
    return True


def _add_application_to_config():
    """Add a new application to application-configs.yml.
    
    Returns:
        Tuple of (success: bool, app_name: str | None, auth_type: str | None)
        On success, returns (True, app_name, auth_type)
        On failure, returns (False, None, None)
    """
    print("\n--- Add Application to Config ---")
    
    # Step 1: Ask for connection type with numeric selection
    while True:
        print("\nConnection type:")
        print("  [1] HTTP")
        print("  [2] MQTT")
        choice = input("Select connection type [1-2]: ").strip()
        if choice == "1":
            connection_type = "http"
            break
        elif choice == "2":
            connection_type = "mqtt"
            break
        else:
            print("Invalid selection. Please enter 1 or 2.")
    
    # Step 2: Ask for application name
    while True:
        app_name = input("\nApplication name: ").strip()
        if app_name:
            break
        print("Application name cannot be empty. Please try again.")
    
    # Load existing config
    config = {}
    if APPLICATION_CONFIG_FILE.exists() and APPLICATION_CONFIG_FILE.is_file():
        try:
            with open(APPLICATION_CONFIG_FILE, "r") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error reading config file: {e}")
            return (False, None, None)
    else:
        # File doesn't exist, create new structure
        config = {"applications": {}}
    
    # Check if application already exists
    if "applications" in config and app_name in config["applications"]:
        overwrite = input(f"\nApplication '{app_name}' already exists. Overwrite? (yes/no) [no]: ").strip().lower()
        if overwrite != "yes":
            print("Cancelled.")
            return (False, None, None)
    
    # Initialize applications dict if needed
    if "applications" not in config:
        config["applications"] = {}
    
    # Build application config
    app_config = {}
    
    # Common fields - Authentication type with numeric selection
    while True:
        print("\nAuthentication type:")
        print("  [1] tokens")
        print("  [2] credentials")
        choice = input("Select authentication type [1-2]: ").strip()
        if choice == "1":
            app_config["authentication_type"] = "tokens"
            break
        elif choice == "2":
            app_config["authentication_type"] = "credentials"
            break
        else:
            print("Invalid selection. Please enter 1 or 2.")
    
    # Connection class - show available options
    available_classes = _get_available_connection_classes(connection_type)
    if not available_classes:
        print(f"\nNo {connection_type.upper()} connection classes found in connections.py")
        return (False, None, None)
    
    while True:
        print(f"\nAvailable {connection_type.upper()} connection classes:")
        for i, class_name in enumerate(available_classes, 1):
            print(f"  [{i}] {class_name}")
        choice = input(f"Select connection class [1-{len(available_classes)}]: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available_classes):
                app_config["connection_class"] = available_classes[idx]
                break
            else:
                print(f"Invalid selection. Please enter a number between 1 and {len(available_classes)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    if connection_type == "http":
        # HTTP-specific fields
        interval = input("\nRequest Interval (seconds) (optional, press Enter to skip): ").strip()
        if interval:
            while True:
                try:
                    app_config["interval"] = int(interval)
                    break
                except ValueError:
                    interval = input("Invalid interval value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not interval:
                        break
        
        max_retries = input("Max retries (optional, press Enter to skip): ").strip()
        if max_retries:
            while True:
                try:
                    app_config["max_retries"] = int(max_retries)
                    break
                except ValueError:
                    max_retries = input("Invalid max_retries value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not max_retries:
                        break
        
        expected_sensors = input("Expected sensors (optional, press Enter to skip): ").strip()
        if expected_sensors:
            while True:
                try:
                    app_config["expected_sensors"] = int(expected_sensors)
                    break
                except ValueError:
                    expected_sensors = input("Invalid expected_sensors value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not expected_sensors:
                        break
    
    else:  # mqtt
        # MQTT-specific fields
        max_retries = input("\nMax retries (optional, press Enter to skip): ").strip()
        if max_retries:
            while True:
                try:
                    app_config["max_retries"] = int(max_retries)
                    break
                except ValueError:
                    max_retries = input("Invalid max_retries value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not max_retries:
                        break
        
        while True:
            host = input("Host: ").strip()
            if host:
                app_config["host"] = host
                break
            print("Host is required for MQTT applications. Please try again.")
        
        port = input("Port [8883]: ").strip()
        if port:
            while True:
                try:
                    app_config["port"] = int(port)
                    break
                except ValueError:
                    port = input("Invalid port value. Must be a number. Try again: ").strip()
        else:
            app_config["port"] = 8883
        
        while True:
            topic = input("Topic: ").strip()
            if topic:
                app_config["topic"] = topic
                break
            print("Topic is required for MQTT applications. Please try again.")
        
        expected_sensors = input("Expected sensors (optional, press Enter to skip): ").strip()
        if expected_sensors:
            while True:
                try:
                    app_config["expected_sensors"] = int(expected_sensors)
                    break
                except ValueError:
                    expected_sensors = input("Invalid expected_sensors value. Must be a number. Try again (or press Enter to skip): ").strip()
                    if not expected_sensors:
                        break
    
    # Add application to config
    config["applications"][app_name] = app_config
    
    # Save config
    try:
        with open(APPLICATION_CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
        print(f"\n✓ Added '{app_name}' to {APPLICATION_CONFIG_FILE.name}")
        auth_type = app_config.get("authentication_type", "credentials")
        return (True, app_name, auth_type)
    except Exception as e:
        print(f"Error saving config file: {e}")
        return (False, None, None)
