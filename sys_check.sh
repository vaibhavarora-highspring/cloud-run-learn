#!/bin/bash

# Write system info to log.txt
echo "Date & Time: $(date)" > log.txt
echo "Disk Usage:" >> log.txt
df -h >> log.txt
echo "Logged-in User: $(whoami)" >> log.txt

# Create deploy_app directory if it doesn't exist
if [ ! -d "deploy_app" ]; then
    mkdir deploy_app
fi

# Move log file into deploy_app
mv log.txt deploy_app/

