#!/bin/bash

ENV_NAME="JFC-Embodied-Carbon-App"

# ==========================================================
# Locate and load conda
# ==========================================================

CONDA_BASE=$(conda info --base 2>/dev/null)

if [ -z "$CONDA_BASE" ]; then
    echo "ERROR: Conda was not found on this machine."
    echo "Please install Miniconda/Anaconda, or check your PATH."
    read -p "Press Enter to close..."
    exit 1
fi

source "$CONDA_BASE/etc/profile.d/conda.sh"

# ==========================================================
# Check the environment exists
# ==========================================================

if ! conda env list | grep -q "$ENV_NAME"; then
    echo "ERROR: Conda environment '$ENV_NAME' was not found."
    echo ""
    echo "Create it first with:"
    echo "  conda create -n $ENV_NAME python=3.11"
    echo "  conda activate $ENV_NAME"
    echo "  pip install -r requirements.txt"
    read -p "Press Enter to close..."
    exit 1
fi

conda activate "$ENV_NAME"

# Move to the script's own directory so relative paths (data/, utils/) resolve correctly
cd "$(dirname "$0")"

# ==========================================================
# Sync requirements.txt against what's installed
# ==========================================================
if [ "$CURRENT_HASH" != "$STORED_HASH" ]; then
    echo "requirements.txt has changed since last run — syncing packages..."

    # Install/upgrade everything listed in requirements.txt
    pip install -r requirements.txt

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install requirements. Check your internet connection"
        echo "or the requirements.txt file for errors."
        read -p "Press Enter to close..."
        exit 1
    fi

    # Remove pip-installed packages that are no longer in requirements.txt
    REQUIRED_PACKAGES=$(grep -oE '^[a-zA-Z0-9_\-]+' requirements.txt | tr 'A-Z' 'a-z')

    INSTALLED_PACKAGES=$(pip freeze | grep -oE '^[a-zA-Z0-9_\-]+' | tr 'A-Z' 'a-z')

    TO_REMOVE=""
    for pkg in $INSTALLED_PACKAGES; do
        if ! echo "$REQUIRED_PACKAGES" | grep -qx "$pkg"; then
            TO_REMOVE="$TO_REMOVE $pkg"
        fi
    done

    if [ -n "$TO_REMOVE" ]; then
        echo "Removing packages no longer in requirements.txt:$TO_REMOVE"
        pip uninstall -y $TO_REMOVE
    fi

    echo "$CURRENT_HASH" > "$REQUIREMENTS_HASH_FILE"
    echo "Packages synced successfully."
else
    echo "Requirements already up to date — skipping install."
fi

# ==========================================================
# Final sanity check
# ==========================================================

if ! python -c "import streamlit" 2>/dev/null; then
    echo "ERROR: Streamlit still not found after sync. Something went wrong."
    read -p "Press Enter to close..."
    exit 1
fi

echo "Environment '$ENV_NAME' verified. Launching app..."

# ==========================================================
# Launch
# ==========================================================

streamlit run Home.py --server.address=0.0.0.0 --server.port=8501
