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
            print(f"  [{len(unconfigured_apps) + 1}] Skip / Back to menu")
            
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
                    # Skip/Back - exit the loop
                    break
                else:
                    print("Invalid selection.")
                    continue
            except ValueError:
                # User pressed Enter or entered non-numeric - exit the loop
                break
        else:
            print("\n✓ All applications are configured!")
            break


def _add_application_to_config():
    """Add a new application to application-configs.yml."""
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
            return False
    else:
        # File doesn't exist, create new structure
        config = {"applications": {}}
    
    # Check if application already exists
    if "applications" in config and app_name in config["applications"]:
        overwrite = input(f"\nApplication '{app_name}' already exists. Overwrite? (yes/no) [no]: ").strip().lower()
        if overwrite != "yes":
            print("Cancelled.")
            return False
    
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
        return False
    
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
        return True
    except Exception as e:
        print(f"Error saving config file: {e}")
        return False
