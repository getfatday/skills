"""Status command — show cache info and record counts."""

from __future__ import annotations

import click

from gfd_copilot_money_cli.output import detect_format, render_single, error


@click.command()
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default=None)
def status(fmt: str | None) -> None:
    """Show cache info: path, size, record counts per collection."""
    fmt = detect_format(fmt)
    try:
        from gfd_copilot_money_cli.core.store import get_stats

        stats = get_stats()
    except FileNotFoundError as e:
        error(str(e))

    if stats.get("error"):
        error(stats["error"])

    collections = stats.get("collections", {})
    data: dict[str, object] = {
        "cache_path": stats.get("cache_path", ""),
        "cache_size": f"{stats.get('cache_size_mb', 0)} MB",
        "total_documents": stats.get("total_documents", 0),
    }
    for name, count in collections.items():
        data[f"  {name}"] = count

    render_single(data, fmt)
