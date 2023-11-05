#!/bin/bash
# figlet | check if figlet is installed

if ! command -v  &> /dev/null; then
    echo "installing some stuff"
    echo "running kernel update"
    alias kernel-update="sudo apt update -y"
    kernel-update
    echo "installing figlet -y"

else 
    echo "figlet is installed"
fi

figlet "Docker Installer"
echo "Starting Script"

# install docker
