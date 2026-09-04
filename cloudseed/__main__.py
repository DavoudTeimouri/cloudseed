"""CloudSeed entry point with version metadata for PyInstaller."""

from cloudseed.cli import main

# PyInstaller version info for Windows EXE
if __name__ == "__main__":
    import sys

    # Set version info for Windows executable
    if hasattr(sys, 'frozen'):
        # Running as compiled executable
        try:
            import ctypes
            # Set process DPI awareness for better rendering on Windows
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    main()
