"""System state checking functions."""

# standard
import subprocess
from pathlib import Path

# internal
from ..paths import CREDENTIALS_DIR, TOKENS_DIR
from ..preflight.validation import validate_all_credentials


def _check_containers_running():
    """Check if any containers are currently running."""
    try:
        result = subprocess.run(
            ['docker', 'compose', 'ps', '-q'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def _check_postgres_persistent_volume():
    """Check if PostgreSQL persistent volume exists."""
    try:
        result = subprocess.run(
            ['docker', 'volume', 'ls', '--format', '{{.Name}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        volumes = result.stdout.strip().split('\n')
        # Check for common volume names
        postgis_volumes = [
            v for v in volumes
            if 'postgis' in v.lower() or 'postgres' in v.lower()
        ]
        return len(postgis_volumes) > 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def _check_existing_and_valid_credentials():
    """Check which credentials already exist and validate their structure."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Validate all credential files
    validation_results = validate_all_credentials(CREDENTIALS_DIR)
    
    existing = {
        'frost': (CREDENTIALS_DIR / "frost_credentials.json").exists() and validation_results['frost'][0],
        'postgres': (CREDENTIALS_DIR / "postgres_credentials.json").exists() and validation_results['postgres'][0],
        'mqtt': (CREDENTIALS_DIR / "mqtt_credentials.json").exists() and validation_results['mqtt'][0],
        'tomcat': (CREDENTIALS_DIR / "tomcat-users.xml").exists() and validation_results['tomcat'][0],
        'application': (CREDENTIALS_DIR / "application_credentials.json").exists() and validation_results['application'][0],
    }
    
    # Store validation results for later use
    existing['_validation_results'] = validation_results
    
    # List existing token files
    existing['tokens'] = [
        f.stem for f in TOKENS_DIR.glob("*.json")
    ] if TOKENS_DIR.exists() else []
    
    return existing


def _check_valid_credentials(credential_file: Path) -> bool:
    """Check that mandatory credentials include the right keys."""
    EXPECTED_KEYS = {
        "frost": ["frost_username", "frost_password"],
        "postgres": ["postgres_user", "postgres_password"],
        "mqtt": ["username", "password", "topics"],
    }
    # This function is defined but not fully implemented
    return True


def _get_missing_mandatory(existing):
    """Get list of missing mandatory credentials."""
    mandatory = ['frost', 'postgres', 'mqtt', 'tomcat']
    return [cred for cred in mandatory if not existing.get(cred, False)]


def _is_first_time_setup(existing):
    """Check if this is a first-time setup (no credentials exist)."""
    mandatory = ['frost', 'postgres', 'mqtt', 'tomcat']
    return not any(existing.get(cred, False) for cred in mandatory)
