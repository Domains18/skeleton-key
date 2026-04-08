import {$} from 'bun'
import chalk from 'chalk'


/**
 * runs once to check things like brew, git, etc are installed
 * check will be based on environment
 */
class RequiredToolsInstaller {
    constructor(private os: string) { }

    public async callable(os: string) {
        switch (os) {
            case 'darwin':
                this.installBrewOnMacAndAddToPath()
                break;
            case 'linux':
                break;
            default:
                break;
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
        
}