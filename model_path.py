import sys
import os

def get_model_path():
    if getattr(sys, 'frozen', False):
        # Running inside PyInstaller bundle
        base = sys._MEIPASS
        return os.path.join(base, "local_models", "all-MiniLM-L6-v2")
    else:
        # Running normally
        return "local_models/all-MiniLM-L6-v2"