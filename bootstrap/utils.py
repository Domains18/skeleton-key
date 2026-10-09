import platform
import subprocess
import shutil
from pathlib import Path
import typer

def detect_os() -> str:
    os_type = platform.system().lower()
    if os_type == "darwin":
        return "macos"
    elif os_type == "linux":
        return "linux"
    else:
        typer.secho(f"Unsupported operating system: {os_type}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)
    
    
def run_command(command: list[str], description: str, use_shell: bool = False) -> None:
    typer.echo(f"Running: {description}...")
    
    try:
        subprocess.run(command if not use_shell else " ".join(command), shell=use_shell, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        typer.secho(f"Success: {description}", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode().strip() if e.stderr else "No error message available."
        typer.secho(f"Error: {description} failed with error: {error_msg}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)
    

def copy_file(source: Path, destination: Path) -> None:
    """"""
    if not source.exists():
        typer.secho(f"Source file {source} does not exist.", fg=typer.colors.RED, bold=True)
        return
    
    if destination.exists():
        """essentially should backup to a remote location like github or a coud storage"""
        #TODO: Implement backup logic here, to google drive or github
        backup = destination.with_suffix(destination.suffix + ".backup")
        shutil.copy2(destination, backup)
        typer.secho(f"Backed up {destination} to {backup}", fg=typer.colors.YELLOW)
        
    shutil.copy2(source, destination)
    typer.secho(f"Copied {source} to {destination}", fg=typer.colors.GREEN)