import click
import sys
from .io import Data
from .display import Display
import matplotlib.pyplot as plt

# The version should ideally be read from package metadata.
# For now, we'll use a placeholder.
__version__ = "0.1.0"


@click.group()
def cli():
    """teepeesee: A Python package that provides modules and a Click based
    command line interface."""
    pass


@cli.command()
@click.argument('npz_path', type=click.Path(exists=True))
def display(npz_path):
    """
    Display the first frame from the specified NPZ file interactively.
    """
    try:
        data_source = Data(npz_path)
        if len(data_source) == 0:
            click.echo(f"Error: No complete event trios found in {npz_path}", err=True)
            sys.exit(1)
            
        frame = data_source[0]
        
        display_app = Display()
        display_app.show(frame)
        
        # Keep the matplotlib window open and interactive
        plt.show() 

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except IOError as e:
        click.echo(f"Error loading data: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"An unexpected error occurred during display: {e}", err=True)
        sys.exit(1)


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
