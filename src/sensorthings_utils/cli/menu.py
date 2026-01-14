"""Menu and orchestration functions."""

# standard
import json

# external
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import print as rprint

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
from .config_generator import generate_config_from_template
from ..transformers.types import SupportedSensors

console = Console()


def _get_sensors_by_brand():
    """Organize supported sensors by brand.
    
    Returns:
        dict: Mapping of brand names to lists of (model_name, SupportedSensors enum) tuples
    """
    sensors_by_brand = {
        "Milesight": [
            ("AM103L", SupportedSensors.MILESIGHT_AM103L),
            ("AM308L", SupportedSensors.MILESIGHT_AM308L),
        ],
        "Netatmo": [
            ("NWS03", SupportedSensors.NETATMO_NWS03),
        ],
    }
    return sensors_by_brand


def _setup_sensor_configuration():
    """Interactive setup for sensor configuration generation."""
    try:
        console.print(Panel.fit(
            "[bold blue]Setup Sensor Configuration[/bold blue]",
            border_style="blue"
        ))
        
        # Step 1: Select brand
        sensors_by_brand = _get_sensors_by_brand()
        brands = list(sensors_by_brand.keys())
        
        console.print("\n[bold]Select sensor brand:[/bold]")
        for i, brand in enumerate(brands, 1):
            console.print(f"  [cyan][{i}][/cyan] {brand}")
        console.print(f"  [cyan][{len(brands) + 1}][/cyan] Back to main menu")
        
        brand_choice = IntPrompt.ask(
            f"\nSelect a brand",
            default=len(brands) + 1
        )
        
        if brand_choice == len(brands) + 1:
            console.print("\n[yellow]Returning to main menu...[/yellow]")
            return
        
        try:
            brand_index = brand_choice - 1
            if brand_index < 0 or brand_index >= len(brands):
                console.print("[red]Invalid selection. Returning to main menu...[/red]")
                return
            selected_brand = brands[brand_index]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection. Returning to main menu...[/red]")
            return
        
        # Step 2: Select model within brand
        models = sensors_by_brand[selected_brand]
        console.print(f"\n[bold]Select {selected_brand} sensor model:[/bold]")
        for i, (model_name, _) in enumerate(models, 1):
            console.print(f"  [cyan][{i}][/cyan] {model_name}")
        console.print(f"  [cyan][{len(models) + 1}][/cyan] Back to main menu")
        
        model_choice = IntPrompt.ask(
            f"\nSelect a model",
            default=len(models) + 1
        )
        
        if model_choice == len(models) + 1:
            console.print("\n[yellow]Returning to main menu...[/yellow]")
            return
        
        try:
            model_index = model_choice - 1
            if model_index < 0 or model_index >= len(models):
                console.print("[red]Invalid selection. Returning to main menu...[/red]")
                return
            model_name, sensor_model = models[model_index]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection. Returning to main menu...[/red]")
            return
        
        # Step 3: Collect configuration details
        console.print(Panel.fit(
            f"[bold]Generating configuration for {selected_brand} {model_name}[/bold]",
            border_style="green"
        ))
        
        sensor_id = Prompt.ask("Sensor ID/Name (typically MAC address)", default="").strip()
        if not sensor_id:
            console.print("[bold red]Error:[/bold red] Sensor ID is required")
            return
        
        console.print("\n[bold]Thing Configuration:[/bold]")
        thing_name = Prompt.ask("Thing name", default="").strip()
        if not thing_name:
            console.print("[bold red]Error:[/bold red] Thing name is required")
            return
        
        thing_description = Prompt.ask("Thing description", default="").strip()
        if not thing_description:
            console.print("[bold red]Error:[/bold red] Thing description is required")
            return
        
        console.print("\n[bold]Location Configuration:[/bold]")
        location_name = Prompt.ask("Location name", default="").strip()
        if not location_name:
            console.print("[bold red]Error:[/bold red] Location name is required")
            return
        
        location_description = Prompt.ask("Location description", default="").strip()
        if not location_description:
            console.print("[bold red]Error:[/bold red] Location description is required")
            return
        
        try:
            longitude = float(Prompt.ask("Longitude", default="").strip())
            latitude = float(Prompt.ask("Latitude", default="").strip())
        except ValueError:
            console.print("[bold red]Error:[/bold red] Longitude and latitude must be valid numbers")
            return
        
        # Step 4: Generate configuration
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
            )
            console.print(f"\n[bold green]✓ Configuration generated successfully:[/bold green] {output_path}")
            console.print("\n[bold]Next steps:[/bold]")
            console.print(f"  1. Review the configuration file")
            console.print(f"  2. Validate it using: [cyan]stu validate {output_path}[/cyan]")
            Prompt.ask("\nPress Enter to continue", default="")
        except Exception as e:
            console.print(f"\n[bold red]Error generating configuration:[/bold red] {e}")
            import traceback
            console.print_exception()
            Prompt.ask("\nPress Enter to continue", default="")
    
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Returning to main menu...[/yellow]")
        return


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
                app_status_text = f" [dim]({configured} of {total} configured)[/dim]"
            
            # Get token count
            token_count = len(existing['tokens']) if existing.get('tokens') else 0
            token_text = f" [dim]({token_count} existing)[/dim]" if token_count > 0 else ""
            
            # Create menu table
            menu_table = Table(show_header=False, box=None, padding=(0, 2))
            menu_table.add_row("[cyan][1][/cyan]", f"FROST credentials{' [green]✓[/green]' if existing.get('frost') else ''}")
            menu_table.add_row("[cyan][2][/cyan]", f"PostgreSQL credentials{' [green]✓[/green]' if existing.get('postgres') else ''}")
            menu_table.add_row("[cyan][3][/cyan]", f"MQTT credentials{' [green]✓[/green]' if existing.get('mqtt') else ''}")
            menu_table.add_row("[cyan][4][/cyan]", f"Tomcat users{' [green]✓[/green]' if existing.get('tomcat') else ''}")
            menu_table.add_row("[cyan][5][/cyan]", f"Application credentials{app_status_text}")
            if token_count > 0:
                menu_table.add_row("[cyan][6][/cyan]", f"Manage token files{token_text}")
            else:
                menu_table.add_row("[cyan][6][/cyan]", "Add new token file")
            menu_table.add_row("[cyan][7][/cyan]", "Back to main menu")
            
            console.print(Panel.fit(
                menu_table,
                title="[bold]Manage Credentials and Tokens[/bold]",
                border_style="blue"
            ))
            
            choice = Prompt.ask("\nSelect an option", default="7", choices=["1", "2", "3", "4", "5", "6", "7"])
            
            if choice == "1":
                try:
                    setup_frost_credentials()
                    # Re-validate after update
                    existing = _check_existing_and_valid_credentials()
                    validation_results = existing.pop('_validation_results', {})
                    if validation_results.get('frost', (False, []))[0]:
                        existing['frost'] = True
                    else:
                        console.print("[yellow]⚠️  Warning:[/yellow] File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Returning to credentials menu...[/yellow]")
            elif choice == "2":
                try:
                    if _setup_postgres_credentials():
                        # Re-validate after update
                        existing = _check_existing_and_valid_credentials()
                        validation_results = existing.pop('_validation_results', {})
                        if validation_results.get('postgres', (False, []))[0]:
                            existing['postgres'] = True
                        else:
                            console.print("[yellow]⚠️  Warning:[/yellow] File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Returning to credentials menu...[/yellow]")
            elif choice == "3":
                try:
                    if _setup_mqtt_credentials():
                        # Re-validate after update
                        existing = _check_existing_and_valid_credentials()
                        validation_results = existing.pop('_validation_results', {})
                        if validation_results.get('mqtt', (False, []))[0]:
                            existing['mqtt'] = True
                        else:
                            console.print("[yellow]⚠️  Warning:[/yellow] File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Returning to credentials menu...[/yellow]")
            elif choice == "4":
                try:
                    if _setup_tomcat_users():
                        # Re-validate after update
                        existing = _check_existing_and_valid_credentials()
                        validation_results = existing.pop('_validation_results', {})
                        if validation_results.get('tomcat', (False, []))[0]:
                            existing['tomcat'] = True
                        else:
                            console.print("[yellow]⚠️  Warning:[/yellow] File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Returning to credentials menu...[/yellow]")
            elif choice == "5":
                try:
                    if _setup_application_credentials():
                        # Re-validate after update
                        existing = _check_existing_and_valid_credentials()
                        validation_results = existing.pop('_validation_results', {})
                        if validation_results.get('application', (False, []))[0]:
                            existing['application'] = True
                        else:
                            console.print("[yellow]⚠️  Warning:[/yellow] File created but validation failed. Please check the file structure.")
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Returning to credentials menu...[/yellow]")
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
                    console.print("\n\n[yellow]Returning to credentials menu...[/yellow]")
            elif choice == "7":
                break
            else:
                console.print("[red]Invalid option. Please try again.[/red]")
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Returning to main menu...[/yellow]")
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
                app_summary = f" [dim]({configured}/{total} configured)[/dim]"
            
            # Create menu table
            menu_table = Table(show_header=False, box=None, padding=(0, 2))
            menu_table.add_row("[cyan][1][/cyan]", "Add sensor application")
            menu_table.add_row("[cyan][2][/cyan]", "Manage existing credentials and tokens")
            menu_table.add_row("[cyan][3][/cyan]", f"Manage configured applications{app_summary}")
            menu_table.add_row("[cyan][4][/cyan]", "Setup a sensor configuration")
            menu_table.add_row("[cyan][5][/cyan]", "Exit")
            
            console.print(Panel.fit(
                menu_table,
                title="[bold]Main Menu[/bold]",
                border_style="green"
            ))
            
            choice = Prompt.ask("\nSelect an option", default="5", choices=["1", "2", "3", "4", "5"])
            
            if choice == "1":
                try:
                    success, app_name, auth_type = _add_application_to_config()
                    if success and app_name and auth_type:
                        console.print(f"\n[bold green]Application '{app_name}' added successfully![/bold green]")
                        console.print("[dim]Setting up credentials/tokens for this application...[/dim]\n")
                        if auth_type == "credentials":
                            _setup_application_credentials(app_name=app_name)
                        elif auth_type == "tokens":
                            _setup_token_file(token_name=app_name)
                        # Refresh existing state after setup
                        existing = _check_existing_and_valid_credentials()
                        existing.pop('_validation_results', None)
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Returning to main menu...[/yellow]")
            elif choice == "2":
                try:
                    _manage_credentials_and_tokens(existing)
                    # Refresh existing state after returning from management
                    existing = _check_existing_and_valid_credentials()
                    existing.pop('_validation_results', None)
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Returning to main menu...[/yellow]")
            elif choice == "3":
                try:
                    _show_application_status()
                    Prompt.ask("\nPress Enter to continue", default="")
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Returning to main menu...[/yellow]")
            elif choice == "4":
                try:
                    _setup_sensor_configuration()
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Returning to main menu...[/yellow]")
            elif choice == "5":
                console.print("\n[yellow]Exiting setup.[/yellow]")
                break
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Returning to main menu...[/yellow]")
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
    
    console.print(Panel.fit(
        "[bold]SensorThings Utils Credential Setup[/bold]",
        border_style="blue"
    ))
    
    # Check if containers are running and warn
    containers_running = _check_containers_running()
    if containers_running:
        console.print(Panel(
            "[bold yellow]⚠️  WARNING: Containers are currently running![/bold yellow]\n"
            "Credential changes will NOT take effect until containers are restarted.\n"
            "After setup, run: [cyan]docker compose restart[/cyan]",
            border_style="yellow"
        ))
    
    # Check existing credentials and validate them
    existing = _check_existing_and_valid_credentials()
    validation_results = existing.pop('_validation_results', {})
    
    # Check if this is first-time setup
    is_first_time = _is_first_time_setup(existing)
    if is_first_time:
        console.print(Panel.fit(
            "[bold green]🎉 Welcome to SensorThings Utils![/bold green]\n\n"
            "This appears to be your first time setting up st-utils.\n"
            "We'll guide you through the initial configuration.",
            border_style="green"
        ))
    
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
        error_text = "[bold red]WARNING: Some credential files have validation errors![/bold red]\n\n"
        for cred_type, errors in invalid_files:
            error_text += f"[red]❌ Invalid {cred_type.upper()} credentials:[/red]\n"
            for error in errors:
                error_text += f"   {error}\n"
        
        console.print(Panel(error_text, border_style="red"))
        
        try:
            response = Confirm.ask("\nWould you like to fix these files now?", default=True)
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Cancelled. Starting main menu...[/yellow]")
            response = False
        
        if response:
            console.print("\n[bold]Fixing invalid credential files...[/bold]\n")
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
                    console.print("\n\n[yellow]Cancelled fixing invalid files. Starting main menu...[/yellow]")
                    break
            
            # Re-validate after fixing
            existing = _check_existing_and_valid_credentials()
            validation_results = existing.pop('_validation_results', {})
            console.print("\n[green]✓ Validation complete. Re-checking files...[/green]")
            
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
                console.print(f"[yellow]⚠️  Warning:[/yellow] Some files are still invalid: {', '.join(still_invalid)}")
                console.print("   You may need to fix them manually or try again.")
        else:
            console.print("[yellow]Skipping validation fixes. You can fix them later from the main menu.[/yellow]")
    
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
        console.print("\n[bold]Validating credential files...[/bold]\n")
        from ..preflight.validation import validate_all_credentials
        validation_results = validate_all_credentials(CREDENTIALS_DIR)
        
        all_valid = True
        validation_table = Table(title="Validation Results", show_header=True, header_style="bold")
        validation_table.add_column("Credential Type", style="cyan")
        validation_table.add_column("Status", style="magenta")
        validation_table.add_column("Errors", style="red")
        
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
                    validation_table.add_row(cred_type.upper(), "[green]Valid[/green]", "")
                else:
                    all_valid = False
                    error_text = "\n".join(errors) if errors else "Unknown error"
                    validation_table.add_row(cred_type.upper(), "[red]Invalid[/red]", error_text)
        
        console.print(validation_table)
        
        if all_valid:
            console.print("\n[bold green]Setup complete! All credential files are valid.[/bold green]")
        else:
            console.print("\n[bold yellow]Setup complete, but some files have validation errors.[/bold yellow]")
            console.print("Please fix the errors above or run 'stu setup' again to fix them.")
        return
    
    # New interactive menu mode
    # Step 1: Handle missing mandatory credentials
    missing = _get_missing_mandatory(existing)
    
    if missing:
        console.print(f"\n[yellow]⚠️  Missing mandatory credentials:[/yellow] {', '.join(missing)}")
        console.print("[dim]Setting up missing mandatory credentials first...[/dim]\n")
        
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
            console.print("\n\n[yellow]Cancelled setup. Starting main menu...[/yellow]")
        
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
            error_text = "[bold yellow]Warning: Some credential files were created but have validation errors:[/bold yellow]\n\n"
            for cred_type, errors in invalid_created:
                error_text += f"[red]❌ {cred_type.upper()} credentials:[/red]\n"
                for error in errors:
                    error_text += f"   {error}\n"
            console.print(Panel(error_text, border_style="yellow"))
            console.print("\nYou can fix these from the main menu.")
    
    # Step 2: Show main menu
    _show_main_menu(existing)
