"""DOOM-Tools entry point. The application now lives in the app/ package.

This file is intentionally thin; see app/foundation.py and app/mixins/.
"""
from app.foundation import *
from app.core import App


if __name__ =="__main__":
    try:
        _gil = os.environ.get('PYTHON_GIL', '1')
        if _gil !='0':
            try:
                import tkinter as _tk
                from tkinter import messagebox as _mb
                _root = _tk.Tk()
                _root.withdraw()
                _mb.showinfo("DOOM Tools", "Python GIL was detected as enabled.For best performance, please disable the GIL by setting the environment variable PYTHON_GIL=0 or using runwithoutgil.bat.Disabling the GIL will allow the program to run with more than one thread.")
                _root.destroy()
            except Exception:
                try:
                    print('Warning: running with GIL enabled.Running with GIL disabled may improve performance.')
                except Exception:
                    pass
    except Exception:
        pass

    try:
        show_table_selection_dialog()
    except Exception:
        logging.exception("Table selection dialog failed")

    app = App()
