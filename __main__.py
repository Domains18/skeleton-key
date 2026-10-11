from bootstrap.config import DOTFILES_DIR

# Auto-create empty dotfile samples for demonstration if missing
DOTFILES_DIR.mkdir(exist_ok=True)
(DOTFILES_DIR / ".zshrc").touch()
(DOTFILES_DIR / ".gitconfig").touch()

from bootstrap.cli import app
app()
 