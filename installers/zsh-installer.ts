import commandExists from "../lib";
import chalk from 'chalk'
import { $ } from 'bun'

//things like brew are to be assumed installed as it will be handled before callable
export class ZshInstaller {
    constructor(private os: string) { }
    public async callable() {
        if (commandExists("zsh")) {
            console.log(chalk.blue("skipping zsh installation"))
            return;
        } else {
            switch (this.os) {
                case 'darwin':
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
