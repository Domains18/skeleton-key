import commandExists from "../lib";
import chalk from 'chalk'
import { $ } from 'bun'


export class ZshInstaller {
    constructor(private os: string) {}
    public async callable() {
        if (commandExists("zsh")) {
            console.log(chalk.blue("skipping zsh installation"))
            return;
        } else {
            switch (this.os) {
                case 'darwin':
                    //check if brew is installed
                    if (!commandExists('brew')) {
                        console.log('brew not installed, installing it')
                        await this.installBrewOnMacAndAddToPath()
                    }
                    await this.installZsh(this.os)
                    break;
                case 'linux':
                    await this.installZsh(this.os)
                    break;
                default:
                    console.log(chalk.red("unsupported operating system"))
                    break;
            }
        }
    }



    private async installBrewOnMacAndAddToPath() {
        try {
            await $`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
        } catch (error) {
            console.log(chalk.red("failed to install brew"))
            console.log(error)
        }

        //add brew to path
        try {
            await $`eval "$(/opt/homebrew/bin/brew shellenv)"`
        } catch (error) {
            console.log(chalk.red("failed to add brew to path"))
            console.log(error)
        }
    }



    private async installZsh(os: string) {
        switch (os) {
            case 'darwin':
                try {
                    await $`brew install zsh`
                } catch (error) {
                    console.log(chalk.red("failed to install zsh"))
                    console.log(error)
                }
                break;
            case 'linux':
                try {
                    await $`sudo apt-get install zsh`
                } catch (error) {
                    console.log(chalk.red("failed to install zsh"))
                    console.log(error)
                }
                break;
            default:
                console.log(chalk.red("unsupported operating system"))
                break;
        }
    }

}
