import { $ } from 'bun'
import commandExists from "../lib"
import chalk from 'chalk'


class NeovimInstaller { 
    constructor(private os: string) { }

    public async callable() {
        if (commandExists("nvim")) {
            console.log(chalk.blue("skipping neovim installation"))
            return;
        } else {
            switch (this.os) {
                case 'darwin':
                    await this.installNeovim(this.os)
                    break;
                case 'linux':
                    await this.installNeovim(this.os)
                    break;
                default:
                    console.log(chalk.red("unsupported operating system"))
                    break;
            }
        }
    }

    private async installNeovim(os: string) {
        switch (os) {
            case 'darwin':
                await this.installNeovimOnMac()
                break;
            case 'linux':
                await this.installNeovimOnLinux()
                break;
            default:
                console.log(chalk.red("unsupported operating system"))
                break;
        }
    }

    private async installNeovimOnMac() {
        try {
            await $`brew install neovim`
        } catch (error) {
            console.log(chalk.red("failed to install neovim"))
            console.log(error)
        }
    }

    private async installNeovimOnLinux() {
        try {
            await $`sudo apt-get install neovim`
        } catch (error) {
            console.log(chalk.red("failed to install neovim"))
            console.log(error)
        }
    }
}


export default NeovimInstaller