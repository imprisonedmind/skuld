__all__ = [
    "main",
    "__version__",
]

# NOTE: This version is kept in sync with package.json by release.sh
__version__ = "0.1.19"

def main():
    from .cli import main as cli_main
    cli_main()
