import typer
from bootstrap import core

app = typer.Typer(help="Multi-Platform CLI Tool for Bootstrapping New Machine Environments, works for Linux and MacOS.")

@app.command()
def dirs():
    """
    Create the default directories for the user.
    """
    core.bootstrap_directories()
    
@app.command()
def tools():
    """
    Install the default tools for the user.
    """
    core.bootstrap_packages()
    

@app.command()
def dotfiles():
    """
    Bootstrap the dotfiles for the user.
    """
    core.boostrap_dotfiles()
    
    
@app.command()
def all():
    """
    Run all bootstrapping commands.
    """
    core.bootstrap_directories()
    core.bootstrap_packages()
    core.boostrap_dotfiles()
    typer.secho("Bootstrapping complete!", fg=typer.colors.GREEN)