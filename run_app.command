#!/bin/bash

ENV_NAME="JFC-Embodied-Carbon-App"

# Locate conda and load its shell functions (needed for `conda activate`
# to work inside a script, not just an interactive terminal)
CONDA_BASE=$(conda info --base 2>/dev/null)

if [ -z "$CONDA_BASE" ]; then
    echo "ERROR: Conda was not found on this machine."
    echo "Please install Miniconda/Anaconda, or check your PATH."
    read -p "Press Enter to close..."
    exit 1
fi

source "$CONDA_BASE/etc/profile.d/conda.sh"

# Check the environment exists
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

# Verify Streamlit is actually installed in this environment
if ! python -c "import streamlit" 2>/dev/null; then
    echo "ERROR: Streamlit is not installed in '$ENV_NAME'."
    echo "Run: pip install -r requirements.txt"
    read -p "Press Enter to close..."
    exit 1
fi

echo "Environment '$ENV_NAME' verified. Launching app..."

# Move to the script's own directory so relative paths (data/, utils/) resolve correctly
cd "$(dirname "$0")"

streamlit run app.py --server.address=0.0.0.0 --server.port=8501