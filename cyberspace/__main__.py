"""Allow `python -m cyberspace` to run the CLI.

This is needed by the cyberspace dashboard's 'open a platform' action and lets
users run the platform without the installed console script:
    python -m cyberspace --help
    python -m cyberspace modules
"""
from .cli import app

if __name__ == "__main__":
    app()
