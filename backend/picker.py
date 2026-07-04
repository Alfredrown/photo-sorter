"""
picker.py — cross-platform native folder chooser using tkinter.
Called as a subprocess by app.py. Prints the selected path to stdout.
Works on macOS, Windows, and Linux.
"""
import tkinter as tk
from tkinter import filedialog
import sys

root = tk.Tk()
root.withdraw()
try:
    root.wm_attributes("-topmost", True)   # bring dialog to front
except Exception:
    pass

folder = filedialog.askdirectory(title="Select photo folder")
if folder:
    print(folder)
    sys.exit(0)
else:
    sys.exit(1)   # user cancelled
