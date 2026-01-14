"""Credential setup functions."""

# standard
import json
import subprocess

# external
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich import print as rprint
from getpass import getpass

# internal
from ..paths import CREDENTIALS_DIR
from .system_checks import _check_postgres_persistent_volume

console = Console()


def setup_frost_credentials():
    """Setup FROST credentials."""
    console.print(Panel.fit(
        "[bold]FROST Credentials[/bold]",
        border_style="blue"
    ))
    
    frost_username = Prompt.ask("FROST username", default="sta-admin")
    frost_password = getpass("FROST password: ")
    
    frost_creds = {
        "frost_username": frost_username,
        "frost_password": frost_password
    }
    
    frost_file = CREDENTIALS_DIR / "frost_credentials.json"
    if not frost_file.exists():
        frost_file.touch()

    with open(frost_file, "w") as f:
        json.dump(frost_creds, f, indent=4)
    console.print(f"[green]✓ Created/Updated {frost_file}[/green]")
    return True


def _setup_postgres_credentials():
    """Setup PostgreSQL credentials."""
    console.print(Panel.fit(
        "[bold]PostgreSQL Credentials[/bold]",
        border_style="blue"
    ))
    
    # Check if persistent volume exists - CRITICAL WARNING
    has_persistent_volume = _check_postgres_persistent_volume()
    if has_persistent_volume:
        created_at = subprocess.run(
            [
                "docker", 
                "volume", 
                "inspect", 
                "st-utils-production_postgis_volume", 
                "--format", 
                "{{.CreatedAt}}"
                ],
            capture_output=True,
            text=True,
            timeout=5
        ).stdout.strip()
        
        warning_text = (
            f"[bold red]🚨 CRITICAL WARNING:[/bold red] PostgreSQL production persistent volume "
            f"created at {created_at} detected!\n\n"
            "Changing the password here will LOCK YOU OUT of the database!\n"
            "The database still has the old password stored in the persistent volume.\n\n"
            "[bold]To safely change the password:[/bold]\n"
            "1. Connect to the running database:\n"
            "   [cyan]docker compose exec database psql -U <current_user> -d sensorthings[/cyan]\n"
            "2. Run: [cyan]ALTER USER <username> WITH PASSWORD '<new_password>';[/cyan]\n"
            "3. Then update postgres_credentials.json with the new password\n"
            "4. Restart containers: [cyan]docker compose restart[/cyan]\n\n"
            "[bold]Or, if you want to start fresh (⚠️  DATA LOSS):[/bold]\n"
            "[cyan]docker compose down -v[/cyan]  # Removes volumes\n"
            "# Then run setup again"
        )
        
        console.print(Panel(warning_text, border_style="red"))
        
        from rich.prompt import Confirm
        response = Confirm.ask("\nContinue anyway? This may lock you out!", default=False)
        if not response:
            console.print("[yellow]Skipping PostgreSQL credentials setup.[/yellow]")
            return False
    
    postgres_user = Prompt.ask("PostgreSQL user", default="sta-admin")
    postgres_password = getpass("PostgreSQL password: ")
    
    postgres_creds = {
        "postgres_user": postgres_user,
        "postgres_password": postgres_password
    }
    
    postgres_file = CREDENTIALS_DIR / "postgres_credentials.json"
    with open(postgres_file, "w") as f:
        json.dump(postgres_creds, f, indent=4)
    console.print(f"[green]✓ Created/Updated {postgres_file}[/green]")
    
    if has_persistent_volume:
        console.print("\n[yellow]⚠️  REMINDER:[/yellow] You must update the password in the database!")
        console.print("   The file has been updated, but the database still has the old password.")
        console.print("   See instructions above to safely change it.")
    
    return True


def _setup_mqtt_credentials():
    """Setup MQTT credentials."""
    console.print(Panel.fit(
        "[bold]MQTT Credentials[/bold]",
        border_style="blue"
    ))
    
    mqtt_users = {}
    user_count = 0
    
    while True:
        user_count += 1
        if user_count == 1:
            # First user is required, use default username
            user_key = Prompt.ask(
                f"\nMQTT user key (e.g., mqtt_user_1)",
                default="mqtt_user_1"
            )
            username = Prompt.ask(
                f"  Username for {user_key}",
                default="sta-admin"
            )
        else:
            # Additional users are optional
            user_key = Prompt.ask(
                "\nMQTT user key (e.g., mqtt_user_2)",
                default=""
            )
            if not user_key:
                break
            username = Prompt.ask(
                f"  Username for {user_key}",
                default="sta-admin"
            )
        
        password = getpass(f"  Password for {username}: ")
        if not password:
            console.print("  [yellow]⚠️  Password is required. Please try again.[/yellow]")
            user_count -= 1
            continue
        
        topics = []
        console.print("  Topics (press Enter with empty name to finish):")
        while True:
            topic_name = Prompt.ask("    Topic name", default="").strip()
            if not topic_name:
                break
            topic_perm = Prompt.ask(
                f"    Permission (read/readwrite)",
                default="read",
                choices=["read", "readwrite"]
            )
            topics.append({"name": topic_name, "perm": topic_perm})
        
        mqtt_users[user_key] = {
            "username": username,
            "password": password,
            "topics": topics
        }
    
    if mqtt_users:
        mqtt_file = CREDENTIALS_DIR / "mqtt_credentials.json"
        with open(mqtt_file, "w") as f:
            json.dump(mqtt_users, f, indent=4)
        console.print(f"[green]✓ Created/Updated {mqtt_file}[/green]")
        return True
    return False


def _setup_tomcat_users():
    """Setup Tomcat users.
    
    If no users are provided, the file will be deleted to allow public access.
    """
    console.print(Panel.fit(
        "[bold]Tomcat Users (Webapp Authentication)[/bold]",
        border_style="blue"
    ))
    console.print("[dim]Leave empty to allow public access (no authentication required).[/dim]")
    
    users = []
    
    while True:
        username = Prompt.ask("\nTomcat username", default="").strip()
        if not username:
            break
        
        password = getpass(f"  Password for {username}: ")
        if not password:
            console.print("  [yellow]⚠️  Password is required. Please try again.[/yellow]")
            continue
        
        roles = Prompt.ask(f"  Roles (comma-separated)", default="webapp-users")
        
        users.append({
            "username": username,
            "password": password,
            "roles": roles
        })
    
    tomcat_file = CREDENTIALS_DIR / "tomcat-users.xml"
    
    if users:
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tomcat-users xmlns="http://tomcat.apache.org/xml"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
              xsi:schemaLocation="http://tomcat.apache.org/xml
              http://tomcat.apache.org/xml/tomcat-users.xsd"
              version="1.0">
'''
        for user in users:
            xml_content += f'  <user username="{user["username"]}" password="{user["password"]}" roles="{user["roles"]}"/>\n'
        xml_content += '</tomcat-users>\n'
        
        with open(tomcat_file, "w") as f:
            f.write(xml_content)
        console.print(f"[green]✓ Created/Updated {tomcat_file}[/green]")
    else:
        # No users provided - delete file to allow public access
        if tomcat_file.exists():
            tomcat_file.unlink()
            console.print(f"[green]✓ Removed {tomcat_file}[/green] - application will be publicly accessible")
        else:
            console.print("[green]✓ No authentication file[/green] - application will be publicly accessible")
    
    return True


def _setup_application_credentials(app_name: str = None):
    """Setup application credentials.
    
    Args:
        app_name: Optional application name to pre-fill. If provided, only sets up this app.
    """
    console.print(Panel.fit(
        "[bold]Application Credentials[/bold]",
        border_style="blue"
    ))
    
    # Load existing credentials if file exists
    app_file = CREDENTIALS_DIR / "application_credentials.json"
    app_creds = {}
    if app_file.exists():
        try:
            with open(app_file, "r") as f:
                app_creds = json.load(f)
        except Exception:
            pass
    
    if app_name:
        # Single app mode - pre-filled, just ask for api_key
        console.print(f"Setting up credentials for: [cyan]{app_name}[/cyan]")
        api_key = getpass("  API key: ").strip()
        
        if api_key:
            app_creds[app_name] = {"api_key": api_key}
            with open(app_file, "w") as f:
                json.dump(app_creds, f, indent=4)
            console.print(f"[green]✓ Created/Updated {app_file}[/green]")
            return True
        return False
    else:
        # Multi-app mode - ask for application name and api_key
        console.print("Enter application credentials.")
        console.print("For each application, provide the application name and API key.")
        console.print("[dim](press Enter with empty application name to finish)[/dim]")
        
        new_creds = {}
        while True:
            app_name_input = Prompt.ask("  Application name", default="").strip()
            if not app_name_input:
                break
            
            api_key = getpass(f"  API key for {app_name_input}: ").strip()
            if api_key:
                new_creds[app_name_input] = {"api_key": api_key}
        
        if new_creds:
            app_creds.update(new_creds)
            with open(app_file, "w") as f:
                json.dump(app_creds, f, indent=4)
            console.print(f"[green]✓ Created/Updated {app_file}[/green]")
            return True
        return False
