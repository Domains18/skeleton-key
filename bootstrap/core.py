import subprocess
import typer
from bootstrap.config import TARGET_DIRECTORIES, PACKAGES, MACOS_CASKS, DOTFILES_MAPPINGS
from bootstrap.utils import detect_os, run_command, copy_file

def boostrap_directories() -> None:
    typer.secho("Bootstrapping directories...")
    for directory in TARGET_DIRECTORIES:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            typer.secho(f"Created directory: {directory}", fg=typer.colors.GREEN)
        else:
            typer.secho(f"Directory already exists: {directory}", fg=typer.colors.YELLOW)
            
            
def bootstrap_packages() -> None:
    typer.secho("Bootstrapping packages...")
    os_env = detect_os()
    
    if os_env == "macos":
        if subprocess.run(["which", "brew"], stdout=subprocess.DEVNULL).returncode != 0:
            typer.secho("Homebrew not found. Installing Homebrew...", fg=typer.colors.YELLOW)
            run_command(
                ["/bin/bash", "-c", "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"],
                "Installing Homebrew",
                use_shell=True
            )
        for package in PACKAGES[os_env]:
            run_command(["brew", "install", package], f"Installing {package}")

        #install GUI applications via cask
        typer.secho("Installing GUI applications via Homebrew Cask...", fg=typer.colors.CYAN)
        for cask in MACOS_CASKS:
            run_command(["brew", "install", "--cask", cask], f"Installing {cask} via Homebrew Cask")
    elif os_env == "linux":
        for package in PACKAGES[os_env]:
            run_command(["sudo", "apt-get", "install", "-y", package], f"Installing {package}")
            return
            
            
def boostrap_dotfiles() -> None:
    typer.secho("Bootstrapping dotfiles...")
    for source, destination in DOTFILES_MAPPINGS.items():
        copy_file(destination, destination)
        return