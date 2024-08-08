mkdir -p ~/.config/profile_setup
sudo apt install -y curl git-core gcc make zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libssl-dev

sudo apt upgrade -y && sudo apt update
sudo apt-get upgrade -y && sudo apt-get update
sudo apt install snapd

sudo apt install git -y


# INFO: zsh and oh-my-zsh setup
sudo apt install zsh -y
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

# zsh configuration and extentions
git clone https://github.com/zsh-users/zsh-autosuggestions.git ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ~/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting

# INFO configure git
function setupGitUserConfig() {
    read -p "Enter your GitHub username: " github_username
    read -p "Enter your email address: " email_address

    git config --global user.name "$github_username"
    git config --global user.email "$email_address"
    git config --global core.editor nvim
    
    if command -v gh &> /dev/null; then
        ssh-keygen -t ed25519 -C "$email_address"
        eval "$(ssh-agent -s)"
        ssh-add ~/.ssh/id_ed25519
        gh auth login
        gh ssh-key add ~/.ssh/id_ed25519.pub
    else
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
        sudo apt update
        sudo apt install gh -y
        
        setupGitUserConfig
    fi 
}

# git setup func 
setupGitUserConfig

function nvimSetup() {
    # ---- seting up kickstart nvim ----
    clear
    figlet "NVIM | GIT SETUP"
    echo "---  Setting up your git and nvim"
    echo "I hope you have already edited the user name and email | there were no prompts for those"
    rm -rf ~/.config/nvim

    git clone https://github.com/nvim-lua/kickstart.nvim.git $HOME/.config/nvim
    # -- opeing nvim to install needed dependencies --
}

# INFO: FUNCTION TO ADD GO TO PATH AFTER INSTALLATION
add_to_path() {
    case "$SHELL" in
        */zsh)
            echo 'export PATH="$PATH:/usr/local/go/bin"' >> ~/.zshrc
            echo 'export GOROOT="/usr/local/go"' >> ~/.zshrc
            echo 'export GOPATH="$HOME/go"' >> ~/.zshrc
            ;;
        */bash)
            echo 'export PATH="$PATH:/usr/local/go/bin"' >> ~/.bashrc
            echo 'export GOROOT="/usr/local/go"' >> ~/.bashrc
            echo 'export GOPATH="$HOME/go"' >> ~/.bashrc
            ;;
        *)
            echo "Unsupported shell. Please manually add these configurations to your shell configuration file."
            return
            ;;
    esac
}

#!/bin/bash

# Function to install the latest version of Go
install_go() {
    echo "Fetching the latest Go version..."

    # Fetch the latest version number from the Go website
    LATEST_VERSION=$(curl -s https://go.dev/VERSION?m=text)

    if [ -z "$LATEST_VERSION" ]; then
        echo "Failed to fetch the latest version of Go."
        # INFO: writing to a log file to know what failed
        echo "[TOOL] >>> go did not install" >> ~/.config/profile_setup/profile_setup.los
        exit 1
    fi

    echo "Latest version of Go is: $LATEST_VERSION"

    # Define the download URL
    GO_URL="https://golang.org/dl/${LATEST_VERSION}.linux-amd64.tar.gz"

    echo "Downloading Go from: $GO_URL"
    
    # Download the Go tarball
    wget $GO_URL -O /tmp/go.tar.gz

    if [ $? -ne 0 ]; then
        echo "Failed to download Go."
        exit 1
    fi

    echo "Extracting Go tarball..."
    
    # Remove any previous Go installation
    sudo rm -rf /usr/local/go

    # Extract the tarball to /usr/local
    sudo tar -C /usr/local -xzf /tmp/go.tar.gz

    # Remove the downloaded tarball
    rm /tmp/go.tar.gz
    add_to_path
}


# INFO: programming specific tools
# these are proramming specific essentials like the lang it's self
# and its pkm ie -> python, node, nvm , bun , go etc....
function devTools() {


    # INFO: python tooling
    # ------------------- PYENV ----------------------------------
    #setting up pyenv for python version manager
    sudo apt install curl git-core gcc make zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libssl-dev
    git clone https://github.com/pyenv/pyenv.git $HOME/.pyenv

    # trial setup
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"

    if command -v pyenv 1>/dev/null 2>&1; then
        eval "$(pyenv init -)"
    fi

    # trial setup for pyenv
    export PYENV_ROOT="$HOME/.pyenv"
    command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
    # ----------------------------------------------------------------
    
    
    # INFO: node tooling
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.37.2/install.sh | bash
    #setting up nvim and adding it to path
    export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
        [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion


    # I will be installing the currently fully supported LTS node version and yarn
    # Check if Node.js is already installed
    echo "Checking if Node.js is already installed..."
    if command -v node &> /dev/null; then
        echo "Node.js is already installed. Skipping installation."
    else
        echo "Node.js is not installed."
        # Install Node.js (replace this with your installation method)
        curl -fsSL https://deb.nodesource.com/setup_18.1.7 | sudo -E bash -
        sudo apt-get install -y nodejs
        echo "Node.js has been installed."
    fi

    echo "Installing pnpm .............."
    curl -fsSL https://get.pnpm.io/install.sh | sh -
    echo "Installing bun .............."
    curl -fsSL https://bun.sh/install | bash

    # INFO: golang tooling
    install_go
    echo "Go $LATEST_VERSION has been installed successfully."

}

function install_vscode() {
    echo "Fetching the latest version of Visual Studio Code..."

    # Define the URL for the latest .deb package
    VSCODE_URL="https://code.visualstudio.com/sha/download?build=stable&os=linux-deb-x64"

    echo "Downloading Visual Studio Code from: $VSCODE_URL"
    
    # Download the .deb package
    wget -O /tmp/vscode.deb $VSCODE_URL

    if [ $? -ne 0 ]; then
        echo "Failed to download Visual Studio Code."
        exit 1
    fi

    echo "Installing Visual Studio Code..."
    
    # Install the .deb package using dpkg
    sudo dpkg -i /tmp/vscode.deb

    if [ $? -ne 0 ]; then
        echo "Failed to install Visual Studio Code. Trying to fix dependencies..."
        sudo apt-get install -f -y
    fi
    sudo apt-get install -y

    # Cleanup
    rm /tmp/vscode.deb

    echo "Visual Studio Code has been installed successfully."
}

function flatpakApps() {
    flatpak install flathub com.brave.Browser -y
    flatpak install flathub io.dbeaver.DBeaverCommunity -y
}

# Function to install OpenSSL and OpenSSL server
function install_openssl() {
    echo "Installing OpenSSL and OpenSSL server..."
    sudo apt update
    sudo apt install -y openssl openssl-server
    echo "OpenSSL and OpenSSL server have been installed successfully."
}

# INFO: append to the bashrc a start up script to enforce the changes
function startupCleanUp() {
    echo "chsh -s /usr/bin/zsh" | cat - ~/.bashrc > temp && mv temp ~/.bashrc
}

# INFO: terminal utilities and prefered terminal
sudo apt install tmux -y
sudo apt install kitty
setupGitUserConfig || true
nvimSetup || true
devTools || true
install_vscode || true
flatpakApps || true
install_openssl || true



# restart te shell for setting up
startupCleanUp || true
source ~/.zshrc
source ~/.bashrc
exec "$SHELL"