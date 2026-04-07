#!/usr/bin/env node


const os = require('os');

//detect OS
const platform = os.platform();


async function commandExists(command){
    try {
        await $`which ${command}`;
        return true;
    } catch (error) {
        console.log(error)
        return false;
    }
}

console.log('intitializing skeleton key...');

if (platform === 'win32') {
    throw new Error('Windows is not supported');
}

