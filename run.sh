#!/bin/bash
# Quick run — generate one episode on Deepnote
# Usage: bash run.sh

cd "$(dirname "$0")/.."
echo "Running episode generator..."
python automation/generate_episode.py
echo "Done!"
