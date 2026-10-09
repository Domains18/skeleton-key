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



DOTFILES = Path(__file__).parent.parent / "dotfiles"

DOTFILES_MAPPINGS = {
    ".zshrc": DOTFILES / "zsh" / ".zshrc",
    ".gitconfig": DOTFILES / "git" / ".gitconfig",
    ".gitignore_global": DOTFILES / "git" / ".gitignore_global",
    ".vimrc": DOTFILES / "vim" / ".vimrc",
}