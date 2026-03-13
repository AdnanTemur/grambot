"""CLI entry point for InstaBot.

Commands:
  analytics   — Parse Instagram export, compute non-followers, generate queue
  automate    — Run a single automation session
  schedule    — Run scheduler (daemon or cron mode)
  status      — Show rate limits, queue status, action history
"""

import asyncio
import click
from pathlib import Path


@click.group()
def cli():
    """InstaBot — Playwright-based Instagram Automation"""
    pass


# ── Analytics Commands ─────────────────────────────────


@cli.group()
def analytics():
    """Offline analytics — parse exports, compute non-followers."""
    pass


@analytics.command("non-followers")
@click.option(
    "--export-path", "-e", required=True, help="Path to Instagram data export folder"
)
@click.option(
    "--whitelist",
    "-w",
    default=None,
    help="Path to whitelist.txt (one username per line)",
)
@click.option(
    "--generate-queue/--no-queue", default=True, help="Generate unfollow task queue"
)
@click.option("--limit", "-l", default=None, type=int, help="Limit unfollow queue size")
@click.option("--csv", is_flag=True, help="Also export to CSV")
def non_followers_cmd(export_path, whitelist, generate_queue, limit, csv):
    """Compute non-followers from Instagram data export."""
    from analytics.non_followers import (
        compute_non_followers,
        print_report,
        generate_unfollow_queue,
        load_whitelist,
    )
    from analytics.reports import export_non_followers_csv

    wl = load_whitelist(whitelist) if whitelist else load_whitelist()
    if wl:
        click.echo(f"Loaded {len(wl)} whitelisted accounts")

    analysis = compute_non_followers(export_path, whitelist=wl)
    print_report(analysis)

    if generate_queue:
        generate_unfollow_queue(analysis, limit=limit)

    if csv:
        export_non_followers_csv(analysis)


@analytics.command("parse")
@click.option(
    "--export-path", "-e", required=True, help="Path to Instagram data export folder"
)
def parse_cmd(export_path):
    """Parse and display Instagram export data summary."""
    from analytics.extractor import load_export

    export = load_export(export_path)

    click.echo(f"\nFollowers: {len(export['followers'])}")
    click.echo(f"Following: {len(export['following'])}")
    click.echo(f"Files found: {export['files_found']}")


# ── Automation Commands ────────────────────────────────


@cli.command()
@click.option("--account", "-a", default=None, help="Instagram username (or use .env)")
@click.option("--password", "-p", default=None, help="Instagram password (or use .env)")
@click.option("--fresh", is_flag=True, help="Force fresh login (ignore saved session)")
def automate(account, password, fresh):
    """Run a single automation session."""
    from automation.runner import run_session

    asyncio.run(run_session(username=account, password=password, force_login=fresh))


@cli.command()
@click.option("--account", "-a", required=True, help="Instagram username")
@click.option("--password", "-p", default=None, help="Instagram password (or use .env)")
def login(account, password):
    """Login and save session (use to set up 2FA on VPS)."""
    from core.browser import create_browser_context, close_browser
    from core.session import login as do_login, save_session, get_session_path

    async def _login():
        _password = password or settings.IG_PASSWORD
        if not _password:
            click.echo("ERROR: No password. Use --password or set IG_PASSWORD in .env")
            return

        pw, browser, context, page = await create_browser_context()
        try:
            result = await do_login(page, account, _password)
            if result:
                await save_session(context, account)
                click.echo(f"Session saved to {get_session_path(account)}")
            else:
                click.echo("Login failed.")
        finally:
            await close_browser(pw, browser, context)

    asyncio.run(_login())


@cli.command()
@click.option("--account", "-a", required=True, help="Instagram username")
@click.option("--password", "-p", default=None, help="Instagram password (or use .env)")
@click.option("--daemon", is_flag=True, help="Run as persistent daemon")
def schedule(account, password, daemon):
    """Run the scheduler (daemon or single with jitter)."""
    from scheduler import run_daemon, run_once

    if daemon:
        asyncio.run(run_daemon(account, password))
    else:
        asyncio.run(run_once(account, password))


# ── Status Commands ────────────────────────────────────


@cli.command()
def status():
    """Show current rate limits, queue status, and action history."""
    from core.rate_limiter import RateLimiter
    from analytics.reports import print_action_report, queue_status_report

    click.echo("\n── Rate Limiter ──")
    rl = RateLimiter()
    for action, count in rl.status().items():
        click.echo(f"  {action:<15} {count}")

    queue_status_report()
    print_action_report()


# ── Utility Commands ───────────────────────────────────


@cli.command("init-whitelist")
def init_whitelist():
    """Create a template whitelist.txt file."""
    from config import settings

    wl_path = settings.DATA_DIR / "whitelist.txt"
    if wl_path.exists():
        click.echo(f"Whitelist already exists: {wl_path}")
        return

    template = """# InstaBot Whitelist
# Add usernames you NEVER want to unfollow (one per line).
# Lines starting with # are comments.
# Don't include the @ symbol.
#
# Examples:
# natgeo
# nasa
# your_best_friend
"""
    wl_path.write_text(template)
    click.echo(f"Created whitelist template: {wl_path}")
    click.echo("Edit this file to add accounts you want to protect from unfollowing.")


if __name__ == "__main__":
    cli()
