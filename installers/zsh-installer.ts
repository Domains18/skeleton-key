import commandExists from "../lib";
import chalk from 'chalk'
import { $ } from 'bun'



function installZsh(os: string) {
    if (commandExists("zsh")) {
        console.log(chalk.blue("skipping zsh installation"))
        return;
    } else {
        switch (os) {
            case 'darwin':
                //check if brew is installed
                if (!commandExists('brew')) {
                    console.log('brew not installed, installing it')
                }
        }
    }
}