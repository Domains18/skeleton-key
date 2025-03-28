# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH

# Path to your oh-my-zsh installation.
export ZSH="$HOME/.oh-my-zsh"
export PATH="$PATH:/opt/nvim-linux64/bin"
# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="random"
plugins=(git zsh-autosuggestions zsh-syntax-highlighting fast-syntax-highlighting zsh-autocomplete)
source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH
#source ~/configurations/zsh-autocomplete/zsh-autocomplete.plugin.zsh
# Path to your oh-my-zsh installation.
export ZSH="$HOME/.oh-my-zsh"
export PATH=$PATH:/usr/local/go/bin
export PATH=$PATH:$GOPATH/bin
export PATH="$PATH:$HOME/.local/bin"
export PATH=~/.pnpm-global/bin:$PATH
export PATH="$PATH:$HOME/.local/bin:$(go env GOPATH)/bin"
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/tools
export PATH=$PATH:$ANDROID_HOME/tools/bin
export PATH=$PATH:$ANDROID_HOME/emulator
alias air='$(go env GOPATH)/bin/air'  
alias start:dev='pnpm run start:dev'
alias dev='pnpm run dev'
 zstyle ':omz:update' mode auto 

alias app-logs="gcloud app logs tail -s default"
alias deploy="gcloud app deploy"
alias cl="clear"
alias github="cd ~/Documents/github"
alias contracts="cd ~/Documents/github/contracts"
alias lml="cd ~/Documents/github/employments/lmldigitals/"
alias recess="cd ~/Documents/github/employments/recess/"
alias gradegenie="/home/alphauser/Documents/github/employments/gradegenie"
alias mtokaa="cd ~/Documents/github/contracts/mtokaaHero/"
alias nerds="cd ~/Documents/github/nerds"
alias generate="pnpx prisma generate"
alias db-push="pnpx prisma db push"
alias copy="xclip -selection c < "
#alias copy="pbcopy < "
alias gen="npx prisma generate"
alias dbpush="npx prisma db push"
alias gen-p="npx prisma generate && npx prisma db push"
alias codes="code-insiders"
alias ncim="nvim"
alias upgrade="sudo apt update && sudo apt upgrade -y"
[ -f "/Users/alphauser/.ghcup/env" ] && source "/Users/alphauser/.ghcup/env" # ghcup-env

# bun compleions
[ -s "/Users/alphauser/.bun/_bun" ] && source "/Users/alphauser/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
export PATH="/usr/local/sbin:$PATH"
alias ohmyzsh="mate ~/.oh-my-zsh"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

#THIS MUST BE AT THE END OF THE FILE FOR SDKMAN TO WORK!!!
export SDKMAN_DIR="$HOME/.sdkman"
[[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]] && source "$HOME/.sdkman/bin/sdkman-init.sh"


export PATH=/usr/local/nodejs/bin:$PATH


# The next line updates PATH for the Google Cloud SDK.
if [ -f '/home/kemboi/Downloads/google-cloud-sdk/path.zsh.inc' ]; then . '/home/kemboi/Downloads/google-cloud-sdk/path.zsh.inc'; fi

# The next line enables shell command completion for gcloud.
if [ -f '/home/kemboi/Downloads/google-cloud-sdk/completion.zsh.inc' ]; then . '/home/kemboi/Downloads/google-cloud-sdk/completion.zsh.inc'; fi

# bun completions
[ -s "/home/alphauser/.bun/_bun" ] && source "/home/alphauser/.bun/_bun"

# pnpm
export PNPM_HOME="/home/alphauser/.local/share/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac
# pnpm end
