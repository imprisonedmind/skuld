__all__ = [
    "main",
]

def main():
    from .cli import main as cli_main
    cli_main()
