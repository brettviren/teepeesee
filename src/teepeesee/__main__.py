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


@cli.command("mdisplay")
@click.argument('paths', type=click.Path(exists=True), nargs=-1)
def mdisplay(paths):
    from .mio import Data
    data = Data(paths)
    from .mdisplay import launch
    launch(data)

    

@cli.command()
@click.option("-t", "--tag", default="",
              help="Explicitly select one trace set tag")
@click.argument('npz_path', type=click.Path(exists=True))
def display(npz_path, tag):
    """
    Display the first frame from the specified NPZ file interactively, 
    split by detector plane.
    """
    import matplotlib.pyplot as plt
    from .io import Data
    try:
        data_source = Data(npz_path, tag)
        if len(data_source) == 0:
            click.echo(f"Error: No complete event trios found in {npz_path}", err=True)
            sys.exit(1)
            
        frame = data_source[0]
        
        # Use TrioDisplay for plane separation
        from .trio import TrioDisplay
        display_app = TrioDisplay()
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
