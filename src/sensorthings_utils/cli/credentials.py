"""Credential setup functions."""

# standard
import json
import subprocess
from getpass import getpass
# internal
from ..paths import CREDENTIALS_DIR
from .system_checks import _check_postgres_persistent_volume


def setup_frost_credentials():
    """Setup FROST credentials."""
    print("\n--- FROST Credentials ---")
    frost_username = input("FROST username [sta-admin]: ").strip() or "sta-admin"
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
    print(f"✓ Created/Updated {frost_file}")
    return True


def _setup_postgres_credentials():
    """Setup PostgreSQL credentials."""
    print("\n--- PostgreSQL Credentials ---")
    
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
        print(
            f"\n🚨 CRITICAL WARNING: PostgreSQL production persistent volume created at {created_at} detected!\n"
            "   Changing the password here will LOCK YOU OUT of the database!\n"
            "   The database still has the old password stored in the persistent volume.\n"
            "\n"
            "   To safely change the password:\n"
            "   1. Connect to the running database:\n"
            "      docker compose exec database psql -U <current_user> -d sensorthings\n"
            "   2. Run: ALTER USER <username> WITH PASSWORD '<new_password>';\n"
            "   3. Then update postgres_credentials.json with the new password\n"
            "   4. Restart containers: docker compose restart\n"
            "\n"
            "   Or, if you want to start fresh (⚠️  DATA LOSS):\n"
            "   docker compose down -v  # Removes volumes\n"
            "   # Then run setup again"
        )
        
        response = input("\n   Continue anyway? This may lock you out! (yes/no) [no]: ").strip().lower()
        if response != 'yes':
            print("   Skipping PostgreSQL credentials setup.")
            return False
    
    postgres_user = input("PostgreSQL user [sta-manager]: ").strip() or "sta-manager"
    postgres_password = getpass("PostgreSQL password: ")
    
    postgres_creds = {
        "postgres_user": postgres_user,
        "postgres_password": postgres_password
    }
    
    postgres_file = CREDENTIALS_DIR / "postgres_credentials.json"
    with open(postgres_file, "w") as f:
        json.dump(postgres_creds, f, indent=4)
    print(f"✓ Created/Updated {postgres_file}")
    
    if has_persistent_volume:
        print("\n⚠️  REMINDER: You must update the password in the database!")
        print("   The file has been updated, but the database still has the old password.")
        print("   See instructions above to safely change it.")
    
    return True


def _setup_mqtt_credentials():
    """Setup MQTT credentials."""
    print("\n--- MQTT Credentials ---")
    mqtt_users = {}
    
    while True:
        user_key = input("\nMQTT user key (e.g., mqtt_user_1) [press Enter to finish]: ").strip()
        if not user_key:
            break
        
        username = input(f"  Username for {user_key}: ").strip()
        password = getpass(f"  Password for {user_key}: ")
        
        topics = []
        print("  Topics (press Enter with empty name to finish):")
        while True:
            topic_name = input("    Topic name: ").strip()
            if not topic_name:
                break
            topic_perm = input(f"    Permission (read/readwrite) [read]: ").strip() or "read"
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
        print(f"✓ Created/Updated {mqtt_file}")
        return True
    return False


def _setup_tomcat_users():
    """Setup Tomcat users."""
    print("\n--- Tomcat Users (Webapp Authentication) ---")
    users = []
    
    while True:
        username = input("\nTomcat username [press Enter to finish]: ").strip()
        if not username:
            break
        
        password = getpass(f"  Password for {username}: ")
        roles = input(f"  Roles (comma-separated) [webapp-users]: ").strip() or "webapp-users"
        
        users.append({
            "username": username,
            "password": password,
            "roles": roles
        })
    
    if users:
        tomcat_file = CREDENTIALS_DIR / "tomcat-users.xml"
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
        print(f"✓ Created/Updated {tomcat_file}")
        return True
    return False


def _setup_application_credentials(app_name: str = None):
    """Setup application credentials.
    
    Args:
        app_name: Optional application name to pre-fill. If provided, only sets up this app.
    """
    print("\n--- Application Credentials ---")
    
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
        print(f"Setting up credentials for: {app_name}")
        api_key = getpass("  API key: ").strip()
        
        if api_key:
            app_creds[app_name] = {"api_key": api_key}
            with open(app_file, "w") as f:
                json.dump(app_creds, f, indent=4)
            print(f"✓ Created/Updated {app_file}")
            return True
        return False
    else:
        # Multi-app mode - ask for application name and api_key
        print("Enter application credentials.")
        print("For each application, provide the application name and API key.")
        print("(press Enter with empty application name to finish):")
        
        new_creds = {}
        while True:
            app_name_input = input("  Application name: ").strip()
            if not app_name_input:
                break
            
            api_key = getpass(f"  API key for {app_name_input}: ").strip()
            if api_key:
                new_creds[app_name_input] = {"api_key": api_key}
        
        if new_creds:
            app_creds.update(new_creds)
            with open(app_file, "w") as f:
                json.dump(app_creds, f, indent=4)
            print(f"✓ Created/Updated {app_file}")
            return True
        return False
