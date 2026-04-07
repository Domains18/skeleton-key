#!/usr/bin/env node

import child_process from 'node:child_process';


const commandExists = (command: string) => {
    try {
        child_process.execSync(`which ${command}`);
        return true;
    } catch (_error) {
        return false;
    }
}


export default commandExists;