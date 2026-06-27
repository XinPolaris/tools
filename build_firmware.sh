#!/bin/bash
# Script name: build_firmware.sh
# Function: Automatically execute make clean -> update code -> make SDK
# Project number is hard-coded inside the script for convenience

# ==== Configuration ====
PROJECT_NUMBER=19   # Modify this to the project number you want to build
CCACHE_FLAG="y"     # Default ccache
LUNCHENV_FLAG="n"   # Default lunchenv

# ==== Main script ====
FOTILE_MAKE="./fotile_make.sh"  # Path to the original build script
if [ ! -f "$FOTILE_MAKE" ]; then
    echo "Error: $FOTILE_MAKE not found. Please check the path."
    exit 1
fi

echo "============================"
echo "Firmware build process start: Project number $PROJECT_NUMBER"
echo "============================"

echo "Step 1: Clean build directory (make clean)"
"$FOTILE_MAKE" lunch_project="$PROJECT_NUMBER" lunch_compile_type=6

echo "Step 2: Update project code (update code)"
"$FOTILE_MAKE" lunch_project="$PROJECT_NUMBER" lunch_compile_type=1

echo "Step 3: Build SDK firmware package (make SDK)"
"$FOTILE_MAKE" lunch_project="$PROJECT_NUMBER" lunch_compile_type=2

echo "============================"
echo "Firmware build process completed!"
echo "============================"