#!/bin/bash
# Move to the directory where this script is located
cd "$(dirname "$0")"

echo "----------------------------------------"
echo "Initializing Anaconda Environment..."
echo "----------------------------------------"

# 1. Source conda setup so the shell understands the 'conda' command
# This safely loads the conda configuration for Mac users
if [ -f "$HOME/opt/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/opt/anaconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
fi

echo "Launching Streamlit App..."
echo "Share your Local IP with people on your Wi-Fi!"
echo "----------------------------------------"

# 2. Use 'conda run' to execute streamlit directly inside your environment
conda run -n JFC-Embodied-Carbon-App --no-capture-output streamlit run app.py --server.address=0.0.0.0 --server.port=8501

# 3. If it crashes, keep the window open so you can see why
echo ""
echo "Streamlit has stopped."
echo "Press any key to close this window..."
read -n 1
