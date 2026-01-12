"""Menu and orchestration functions."""

# standard
import json

# internal
from ..paths import CREDENTIALS_DIR, TOKENS_DIR
from .system_checks import _check_existing_and_valid_credentials, _get_missing_mandatory, _check_containers_running, _is_first_time_setup
from .credentials import (
    setup_frost_credentials,
    _setup_postgres_credentials,
    _setup_mqtt_credentials,
    _setup_tomcat_users,
    _setup_application_credentials,
)
from .tokens import _setup_token_file, _manage_tokens
from .applications import _get_application_status, _show_application_status, _add_application_to_config


def _manage_credentials_and_tokens(existing):
    """Unified menu for managing all credentials and tokens."""
    while True:
        try:
            # Get application status for display
            app_status = _get_application_status()
            app_status_text = ""
            if app_status:
                total = len(app_status)
                configured = sum(1 for s in app_status.values() if s["configured"])
                app_status_text = f" ({configured} of {total} configured)"
            
            # Get token count
            token_count = len(existing['tokens']) if existing.get('tokens') else 0
            token_text = f" ({token_count} existing)" if token_count > 0 else ""
            
            print("\n" + "=" * 50)
            print("Manage Credentials and Tokens")
            print("=" * 50)
            print("[1] FROST credentials" + (" ✓" if existing.get('frost') else ""))
            print("[2] PostgreSQL credentials" + (" ✓" if existing.get('postgres') else ""))
            print("[3] MQTT credentials" + (" ✓" if existing.get('mqtt') else ""))
            print("[4] Tomcat users" + (" ✓" if existing.get('tomcat') else ""))
            print("[5] Application credentials" + app_status_text)
            if token_count > 0:
                print(f"[6] Manage token files{token_text}")
            else:
                print("[6] Add new token file")
            print("[7] Back to main menu")
            
            choice = input("\nSelect an option [7]: ").strip() or "7"
            
            if choice == "1":
                try:
                    setup_frost_credentials()
                    # Re-validate after update
                    existing = _check_existing_and_valid_credentials()
                    validation_results = existing.pop('_validation_results', {})
                    if validation_results.get('frost', (False, []))[0]:
                        existing['frost'] = True
                    else:
                        print("⚠️  Warning: File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    print("\n\nReturning to credentials menu...")
            elif choice == "2":
                try:
                    if _setup_postgres_credentials():
                        # Re-validate after update
                        existing = _check_existing_and_valid_credentials()
                        validation_results = existing.pop('_validation_results', {})
                        if validation_results.get('postgres', (False, []))[0]:
                            existing['postgres'] = True
                        else:
                            print("⚠️  Warning: File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    print("\n\nReturning to credentials menu...")
            elif choice == "3":
                try:
                    if _setup_mqtt_credentials():
                        # Re-validate after update
                        existing = _check_existing_and_valid_credentials()
                        validation_results = existing.pop('_validation_results', {})
                        if validation_results.get('mqtt', (False, []))[0]:
                            existing['mqtt'] = True
                        else:
                            print("⚠️  Warning: File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    print("\n\nReturning to credentials menu...")
            elif choice == "4":
                try:
                    if _setup_tomcat_users():
                        # Re-validate after update
                        existing = _check_existing_and_valid_credentials()
                        validation_results = existing.pop('_validation_results', {})
                        if validation_results.get('tomcat', (False, []))[0]:
                            existing['tomcat'] = True
                        else:
                            print("⚠️  Warning: File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    print("\n\nReturning to credentials menu...")
            elif choice == "5":
                try:
                    if _setup_application_credentials():
                        # Re-validate after update
                        existing = _check_existing_and_valid_credentials()
                        validation_results = existing.pop('_validation_results', {})
                        if validation_results.get('application', (False, []))[0]:
                            existing['application'] = True
                        else:
                            print("⚠️  Warning: File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    print("\n\nReturning to credentials menu...")
            elif choice == "6":
                try:
                    if token_count > 0:
                        _manage_tokens(existing['tokens'])
                        existing = _check_existing_and_valid_credentials()  # Refresh token list
                        existing.pop('_validation_results', None)  # Remove validation results
                    else:
                        if _setup_token_file():
                            existing = _check_existing_and_valid_credentials()  # Refresh token list
                            existing.pop('_validation_results', None)  # Remove validation results
                except KeyboardInterrupt:
                    print("\n\nReturning to credentials menu...")
            elif choice == "7":
                break
            else:
                print("Invalid option. Please try again.")
        except KeyboardInterrupt:
            print("\n\nReturning to main menu...")
            break


def _show_main_menu(existing):
    """Show main menu and handle selections."""
    while True:
        try:
            # Get application status for summary
            app_status = _get_application_status()
            app_summary = ""
            if app_status:
                total = len(app_status)
                configured = sum(1 for s in app_status.values() if s["configured"])
                app_summary = f" ({configured}/{total} configured)"
            
            print("\n" + "=" * 50)
            print("Main Menu")
            print("=" * 50)
            print("[1] Add application to config")
            print("[2] Manage existing credentials and tokens")
            print(f"[3] Show configured applications{app_summary}")
            print("[4] Exit")
            
            choice = input("\nSelect an option [4]: ").strip() or "4"
            
            if choice == "1":
                try:
                    success, app_name, auth_type = _add_application_to_config()
                    if success and app_name and auth_type:
                        print(f"\nApplication '{app_name}' added successfully!")
                        print("Setting up credentials/tokens for this application...\n")
                        if auth_type == "credentials":
                            _setup_application_credentials(app_name=app_name)
                        elif auth_type == "tokens":
                            _setup_token_file(token_name=app_name)
                        # Refresh existing state after setup
                        existing = _check_existing_and_valid_credentials()
                        existing.pop('_validation_results', None)
                except KeyboardInterrupt:
                    print("\n\nReturning to main menu...")
            elif choice == "2":
                try:
                    _manage_credentials_and_tokens(existing)
                    # Refresh existing state after returning from management
                    existing = _check_existing_and_valid_credentials()
                    existing.pop('_validation_results', None)
                except KeyboardInterrupt:
                    print("\n\nReturning to main menu...")
            elif choice == "3":
                try:
                    _show_application_status()
                    input("\nPress Enter to continue...")
                except KeyboardInterrupt:
                    print("\n\nReturning to main menu...")
            elif choice == "4":
                print("\nExiting setup.")
                break
            else:
                print("Invalid option. Please try again.")
        except KeyboardInterrupt:
            print("\n\nReturning to main menu...")
            continue


def _setup_credentials(args):
    """Interactive setup for credential files with menu system."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create empty application_credentials.json if it doesn't exist
    # This is required for docker-compose file mounts
    app_creds_file = CREDENTIALS_DIR / "application_credentials.json"
    if not app_creds_file.exists():
        with open(app_creds_file, "w") as f:
            json.dump({}, f, indent=4)
    
    print("SensorThings Utils Credential Setup")
    print("=" * 50)
    
    # Check if containers are running and warn
    containers_running = _check_containers_running()
    if containers_running:
        print("\n⚠️  WARNING: Containers are currently running!")
        print("   Credential changes will NOT take effect until containers are restarted.")
        print("   After setup, run: docker compose restart")
        print()
    
    # Check existing credentials and validate them
    existing = _check_existing_and_valid_credentials()
    validation_results = existing.pop('_validation_results', {})
    
    # Check if this is first-time setup
    is_first_time = _is_first_time_setup(existing)
    if is_first_time:
        print("\n🎉 Welcome to SensorThings Utils!")
        print("=" * 50)
        print("This appears to be your first time setting up st-utils.")
        print("We'll guide you through the initial configuration.")
        print("=" * 50)
        print()
    
    # Check for invalid credential files and prompt user to fix them
    invalid_files = []
    for cred_type, (is_valid, errors) in validation_results.items():
        file_exists = {
            'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists(),
            'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists(),
            'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists(),
            'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists(),
            'application': (CREDENTIALS_DIR / "application_credentials.json").exists(),
        }.get(cred_type, False)
        
        if file_exists and not is_valid:
            invalid_files.append((cred_type, errors))
    
    if invalid_files:
        print("\n⚠️  WARNING: Some credential files have validation errors!")
        print("=" * 50)
        for cred_type, errors in invalid_files:
            print(f"\n❌ Invalid {cred_type.upper()} credentials:")
            for error in errors:
                print(f"   {error}")
        
        print("\n" + "=" * 50)
        try:
            response = input("\nWould you like to fix these files now? (yes/no) [yes]: ").strip().lower()
        except KeyboardInterrupt:
            print("\n\nCancelled. Starting main menu...")
            response = 'no'
        if response != 'no':
            print("\nFixing invalid credential files...\n")
            for cred_type, _ in invalid_files:
                try:
                    if cred_type == 'frost':
                        setup_frost_credentials()
                        existing['frost'] = True
                    elif cred_type == 'postgres':
                        if _setup_postgres_credentials():
                            existing['postgres'] = True
                    elif cred_type == 'mqtt':
                        if _setup_mqtt_credentials():
                            existing['mqtt'] = True
                    elif cred_type == 'tomcat':
                        if _setup_tomcat_users():
                            existing['tomcat'] = True
                    elif cred_type == 'application':
                        if _setup_application_credentials():
                            existing['application'] = True
                except KeyboardInterrupt:
                    print("\n\nCancelled fixing invalid files. Starting main menu...")
                    break
            
            # Re-validate after fixing
            existing = _check_existing_and_valid_credentials()
            validation_results = existing.pop('_validation_results', {})
            print("\n✓ Validation complete. Re-checking files...")
            
            # Check if any files are still invalid
            still_invalid = [
                cred_type for cred_type, (is_valid, _) in validation_results.items()
                if not is_valid and {
                    'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists(),
                    'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists(),
                    'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists(),
                    'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists(),
                    'application': (CREDENTIALS_DIR / "application_credentials.json").exists(),
                }.get(cred_type, False)
            ]
            
            if still_invalid:
                print(f"⚠️  Warning: Some files are still invalid: {', '.join(still_invalid)}")
                print("   You may need to fix them manually or try again.")
        else:
            print("Skipping validation fixes. You can fix them later from the main menu.")
    
    # Handle legacy command-line flags (for backward compatibility)
    if any([args.all, args.frost, args.postgres, args.mqtt, args.tomcat, args.token]):
        # Legacy mode: use flags
        if args.frost or args.all:
            setup_frost_credentials()
        if args.postgres or args.all:
            _setup_postgres_credentials()
        if args.mqtt or args.all:
            _setup_mqtt_credentials()
        if args.tomcat or args.all:
            _setup_tomcat_users()
        if args.token or args.all:
            _setup_token_file()
        
        # Validate all created/updated files
        print("\n" + "=" * 50)
        print("Validating credential files...")
        from ..preflight.validation import validate_all_credentials
        validation_results = validate_all_credentials(CREDENTIALS_DIR)
        
        all_valid = True
        for cred_type, (is_valid, errors) in validation_results.items():
            file_exists = {
                'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists(),
                'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists(),
                'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists(),
                'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists(),
                'application': (CREDENTIALS_DIR / "application_credentials.json").exists(),
            }.get(cred_type, False)
            
            if file_exists:
                if is_valid:
                    print(f"✓ {cred_type.upper()} credentials: Valid")
                else:
                    all_valid = False
                    print(f"❌ {cred_type.upper()} credentials: Invalid")
                    for error in errors:
                        print(f"   {error}")
        
        print("\n" + "=" * 50)
        if all_valid:
            print("Setup complete! All credential files are valid.")
        else:
            print("Setup complete, but some files have validation errors.")
            print("Please fix the errors above or run 'stu setup' again to fix them.")
        return
    
    # New interactive menu mode
    # Step 1: Handle missing mandatory credentials
    missing = _get_missing_mandatory(existing)
    
    if missing:
        print(f"\n⚠️  Missing mandatory credentials: {', '.join(missing)}")
        print("Setting up missing mandatory credentials first...\n")
        
        try:
            for cred_type in missing:
                if cred_type == 'frost':
                    setup_frost_credentials()
                elif cred_type == 'postgres':
                    _setup_postgres_credentials()
                elif cred_type == 'mqtt':
                    _setup_mqtt_credentials()
                elif cred_type == 'tomcat':
                    _setup_tomcat_users()
        except KeyboardInterrupt:
            print("\n\nCancelled setup. Starting main menu...")
        
        # Re-validate after creating missing credentials
        existing = _check_existing_and_valid_credentials()
        validation_results = existing.pop('_validation_results', {})
        
        # Check if any created files are invalid
        invalid_created = []
        for cred_type in missing:
            if cred_type in validation_results:
                is_valid, errors = validation_results[cred_type]
                file_exists = {
                    'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists(),
                    'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists(),
                    'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists(),
                    'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists(),
                }.get(cred_type, False)
                
                if file_exists:
                    if is_valid:
                        existing[cred_type] = True
                    else:
                        invalid_created.append((cred_type, errors))
        
        if invalid_created:
            print("\n⚠️  Warning: Some credential files were created but have validation errors:")
            for cred_type, errors in invalid_created:
                print(f"\n❌ {cred_type.upper()} credentials:")
                for error in errors:
                    print(f"   {error}")
            print("\nYou can fix these from the main menu.")
    
    # Step 2: Show main menu
    _show_main_menu(existing)
