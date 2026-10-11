from pathlib import Path


TARGET_DIRECTORIES = [
    Path.home() / "Documents" / "github",
    Path.home() / "Documents" / "work"
]


PACKAGES = {
    "macos": ["git", "node", "python3", "docker", "docker-compose", "awscli", "terraform", "kubectl"],
    "linux": ["git", "nodejs", "python3", "docker", "docker-compose", "awscli", "terraform", "kubectl"],
}


MACOS_CASKS = [
    "google-chrome",
    "visual-studio-code",
    "iterm2",
    "slack",
    "postman",
    "docker",
]



DOTFILES_DIR = Path(__file__).parent.parent / "dotfiles"

DOTFILES_MAPPING = {
    ".zshrc": DOTFILES_DIR / "zsh" / ".zshrc",
    ".gitconfig": DOTFILES_DIR / "git" / ".gitconfig",
    ".gitignore_global": DOTFILES_DIR / "git" / ".gitignore_global",
    ".vimrc": DOTFILES_DIR / "vim" / ".vimrc",
}