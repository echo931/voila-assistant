#!/bin/bash
# Wrapper for voila CLI with telegram format by default
# Usage: voila-telegram.sh <command> [args...]

VOILA_DIR=~/projects/voila-assistant
cd "$VOILA_DIR"
source venv/bin/activate

case "$1" in
    search)
        shift
        python -m src.cli search "$@" -f telegram
        ;;
    cart)
        python -m src.cli cart -f telegram
        ;;
    add)
        shift
        python -m src.cli add "$@" -f telegram
        ;;
    clear)
        python -m src.cli clear
        ;;
    *)
        echo "Usage: voila-telegram.sh {search|cart|add|clear} [args...]"
        exit 1
        ;;
esac
