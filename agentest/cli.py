import click
from agentest import __version__
from agentest.utils.config import load_config
from agentest.core import AgenTestEngine


@click.group()
@click.version_option(__version__)
def main():
    """AgenTest - Next-Generation Agentic Testing Platform."""


@main.command()
def run():
    """Run tests based on the active configuration."""
    settings = load_config()
    engine = AgenTestEngine(settings)
    engine.run()


@main.command()
def init():
    """Initialize AgenTest configuration in the current directory."""
    import yaml
    from agentest.utils.config import Settings

    config = Settings()
    path = "agentest.config.yaml"
    if Path(path).exists():
        click.echo(f"{path} already exists.")
        return

    with open(path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False)
    click.echo(f"Created {path}")


if __name__ == "__main__":
    main()
