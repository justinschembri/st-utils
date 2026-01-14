"""Token file management functions."""

# standard
import json

# external
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.table import Table

# internal
from ..paths import TOKENS_DIR

console = Console()


def _setup_token_file(token_name: str = None):
    """Setup a new token file.
    
    Args:
        token_name: Optional token file name to pre-fill (without .json extension).
    """
    console.print(Panel.fit(
        "[bold]Token Files (Freeform JSON)[/bold]",
        border_style="blue"
    ))
    
    if token_name:
        console.print(f"Setting up token file for: [cyan]{token_name}[/cyan]")
    else:
        token_name = Prompt.ask("Token file name (without .json extension)", default="").strip()
        if not token_name:
            return False
    
    console.print("[dim]Enter JSON key-value pairs (press Enter with empty key to finish)[/dim]")
    token_data = {}
    
    while True:
        key = Prompt.ask("  Key", default="").strip()
        if not key:
            break
        value = Prompt.ask(f"  Value for {key}", default="").strip()
        token_data[key] = value
    
    if token_data:
        token_file = TOKENS_DIR / f"{token_name}.json"
        with open(token_file, "w") as f:
            json.dump(token_data, f, indent=4)
        console.print(f"[green]✓ Created/Updated {token_file}[/green]")
        return True
    return False


def _manage_tokens(existing_tokens):
    """Manage existing token files."""
    if not existing_tokens:
        console.print("\n[yellow]No existing token files found.[/yellow]")
        return
    
    console.print(Panel.fit(
        "[bold]Manage Token Files[/bold]",
        border_style="blue"
    ))
    
    # Create token list table
    token_table = Table(show_header=True, header_style="bold")
    token_table.add_column("#", style="cyan", width=4)
    token_table.add_column("Token File", style="magenta")
    
    for i, token in enumerate(existing_tokens, 1):
        token_table.add_row(str(i), f"{token}.json")
    token_table.add_row(str(len(existing_tokens) + 1), "[dim]Back to main menu[/dim]")
    
    console.print(token_table)
    
    choice = IntPrompt.ask(
        f"\nSelect token to overwrite",
        default=len(existing_tokens) + 1
    )
    
    try:
        idx = choice - 1
        if 0 <= idx < len(existing_tokens):
            token_name = existing_tokens[idx]
            console.print(f"\n[bold]Overwriting {token_name}.json[/bold]")
            console.print("[dim]Enter JSON key-value pairs (press Enter with empty key to finish)[/dim]")
            token_data = {}
            
            while True:
                key = Prompt.ask("  Key", default="").strip()
                if not key:
                    break
                value = Prompt.ask(f"  Value for {key}", default="").strip()
                token_data[key] = value
            
            if token_data:
                token_file = TOKENS_DIR / f"{token_name}.json"
                with open(token_file, "w") as f:
                    json.dump(token_data, f, indent=4)
                console.print(f"[green]✓ Updated {token_file}[/green]")
        elif idx == len(existing_tokens):
            return  # Back to main menu
        else:
            console.print("[red]Invalid selection.[/red]")
    except (ValueError, IndexError):
        console.print("[red]Invalid input. Please enter a number.[/red]")
