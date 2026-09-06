#!/usr/bin/env bash
set -e
python -m pytest -q
streamlit run streamlit_app.py
