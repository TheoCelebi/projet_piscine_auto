#!/bin/bash
# Double-clic dans le Finder : ouvre le menu de gestion du bot piscine.
cd "$(dirname "$0")" && .venv/bin/python -m piscine_bot.gerer
