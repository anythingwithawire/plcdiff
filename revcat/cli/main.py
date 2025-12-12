"""Main CLI entry point for RevCat."""

import json
import sys
from pathlib import Path

import click

from revcat import __version__
from revcat.core.parsers import ParserError, get_parser


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="revcat")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-error output")
@click.pass_context
def cli(ctx, verbose: bool, quiet: bool):
    """RevCat - PLC Version Control and Comparison Tool.

    Compare PLC project export files and generate detailed diff reports.

    Supported platforms:
      - Rockwell Studio 5000 (L5X export)
      - Schneider EcoStruxure Control Expert (XEF export)
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet

    if ctx.invoked_subcommand is None:
        # No subcommand - show help
        click.echo(ctx.get_help())


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
@click.pass_context
def info(ctx, file: Path, output_format: str):
    """Display information about a PLC project export file.

    FILE is the path to the PLC project export file to analyze.

    Example:
        revcat info Project.L5X
        revcat info --format json Controller.L5X
    """
    verbose = ctx.obj.get("verbose", False)

    try:
        if verbose:
            click.echo(f"Analyzing file: {file}", err=True)

        parser = get_parser(file)
        project = parser.parse(file)

        if output_format == "json":
            _output_json(project)
        else:
            _output_text(project, parser.get_platform_name())

    except ParserError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(4)  # Parse error exit code
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _output_text(project, platform_name: str):
    """Output project info in human-readable text format."""
    click.echo(f"  File: {project.source_file.name}")
    click.echo(f"  Platform: {platform_name}")
    click.echo(f"  Project Name: {project.name}")

    if project.controller_type:
        click.echo(f"  Controller: {project.controller_type}")

    if project.software_version:
        click.echo(f"  Version: {project.software_version}")

    if project.modified:
        click.echo(f"  Last Modified: {project.modified.strftime('%Y-%m-%d %H:%M:%S')}")

    click.echo(f"  Programs: {len(project.programs)}")
    click.echo(f"  Routines: {project.total_routines}")
    click.echo(f"  Tags: {project.total_tags}")

    if project.aoi_count > 0:
        aoi_label = "AOIs" if project.platform.value == "rockwell" else "DFBs"
        click.echo(f"  {aoi_label}: {project.aoi_count}")

    # Show routine breakdown by language if verbose output desired
    if project.programs:
        language_counts = {"LD": 0, "FBD": 0, "ST": 0, "Other": 0}
        for prog in project.programs:
            for routine in prog.routines:
                lang = routine.language.value
                if lang in language_counts:
                    language_counts[lang] += 1
                else:
                    language_counts["Other"] += 1

        # Only show if we have routines
        if any(language_counts.values()):
            breakdown = []
            if language_counts["LD"]:
                breakdown.append(f"{language_counts['LD']} Ladder")
            if language_counts["FBD"]:
                breakdown.append(f"{language_counts['FBD']} FBD")
            if language_counts["ST"]:
                breakdown.append(f"{language_counts['ST']} ST")
            if language_counts["Other"]:
                breakdown.append(f"{language_counts['Other']} Other")

            if breakdown:
                click.echo(f"  Routine Types: {', '.join(breakdown)}")


def _output_json(project):
    """Output project info in JSON format."""
    summary = project.get_summary()

    # Add routine type breakdown
    language_counts = {"LD": 0, "FBD": 0, "ST": 0}
    for prog in project.programs:
        for routine in prog.routines:
            lang = routine.language.value
            if lang in language_counts:
                language_counts[lang] += 1

    summary["routine_breakdown"] = language_counts

    click.echo(json.dumps(summary, indent=2))


@cli.command()
@click.option(
    "-s", "--source",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Source/baseline file",
)
@click.option(
    "-t", "--target",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Target/modified file",
)
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    help="Output PDF file",
)
@click.pass_context
def compare(ctx, source: Path, target: Path, output: Path | None):
    """Compare two PLC project export files.

    Example:
        revcat compare -s baseline.L5X -t modified.L5X -o changes.pdf
    """
    click.echo("Compare functionality not yet implemented.", err=True)
    click.echo(f"  Source: {source}")
    click.echo(f"  Target: {target}")
    click.echo(f"  Output: {output or 'comparison_<timestamp>.pdf'}")
    click.echo("\nThis feature will be available in a future release.")
    sys.exit(0)


@cli.command()
@click.option(
    "-i", "--input",
    "manifest",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Manifest file (JSON or YAML)",
)
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Output directory for reports",
)
@click.option(
    "-w", "--workers",
    type=int,
    default=4,
    help="Number of parallel workers (default: 4)",
)
@click.pass_context
def batch(ctx, manifest: Path, output: Path, workers: int):
    """Process multiple comparisons from a manifest file.

    Example:
        revcat batch -i comparisons.json -o ./reports/
    """
    click.echo("Batch processing not yet implemented.", err=True)
    click.echo(f"  Manifest: {manifest}")
    click.echo(f"  Output: {output}")
    click.echo(f"  Workers: {workers}")
    click.echo("\nThis feature will be available in a future release.")
    sys.exit(0)


if __name__ == "__main__":
    cli()
