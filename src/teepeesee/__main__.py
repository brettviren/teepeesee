import click
import sys

# The version should ideally be read from package metadata.
# For now, we'll use a placeholder.
__version__ = "0.1.0"


@click.group()
def cli():
    """teepeesee: A Python package that provides modules and a Click based
    command line interface."""
    pass


@cli.command()
def version():
    """Print the version of the application."""
    click.echo(__version__)


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        sys.exit(1)
