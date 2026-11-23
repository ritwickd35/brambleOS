#!/bin/sh
# Font choice for the Berry UI: Nunito (rounded) for labels, Fira Sans Condensed for the preset name (size 16), no extra spacing there.
cd "$(dirname "$0")/.." && UI_FONT=ui/fonts/Nunito.ttf UI_WGHT=650 UI_FONT16=ui/fonts/FiraSansCondensed-Medium.ttf UI_TRACK16=0 UI_FONT14=ui/fonts/FiraSansCondensed-Regular.ttf UI_TRACK14=0 UI_FONT12=ui/fonts/FiraSansCondensed-Medium.ttf UI_TRACK12=0 UI_FONT11=ui/fonts/FiraSansCondensed-Regular.ttf UI_TRACK11=0 UI_FONT8=ui/fonts/FiraSansCondensed-Medium.ttf UI_TRACK8=0 tools/.venv/bin/python tools/ui_font.py
