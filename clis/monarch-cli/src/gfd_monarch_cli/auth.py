"""Auth commands: login, logout, status. Session token stored in keyring."""

from __future__ import annotations

import asyncio
import getpass

import click
import keyring
from monarchmoney import MonarchMoney, RequireMFAException, LoginFailedException

# Patch the domain: Monarch migrated from monarchmoney.com to monarch.com (Feb 2026)
# The upstream libraries haven't all caught up yet.
from monarchmoney.monarchmoney import MonarchMoneyEndpoints
MonarchMoneyEndpoints.BASE_URL = "https://api.monarch.com"

SERVICE_NAME = "gfd-monarch"
ACCOUNT_NAME = "session-token"


def get_token() -> str | None:
    return keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)


def store_token(token: str) -> None:
    keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, token)


def clear_token() -> None:
    try:
        keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
    except keyring.errors.PasswordDeleteError:
        pass


def get_client() -> MonarchMoney:
    token = get_token()
    if not token:
        click.echo("Not logged in. Run: gfd-monarch auth login", err=True)
        raise SystemExit(3)
    return _patch_client(MonarchMoney(token=token))


def _patch_client(mm: MonarchMoney) -> MonarchMoney:
    """Patch MonarchMoney instance to use the correct domain."""
    if hasattr(mm, '_headers') and isinstance(mm._headers, dict):
        mm._headers["Origin"] = "https://app.monarch.com"
    return mm


async def _do_login(email: str, password: str, mfa_secret_key: str | None) -> str:
    mm = _patch_client(MonarchMoney())
    try:
        await mm.login(
            email=email,
            password=password,
            use_saved_session=False,
            save_session=False,
            mfa_secret_key=mfa_secret_key,
        )
    except RequireMFAException:
        code = click.prompt("MFA code")
        await mm.multi_factor_authenticate(email, password, code)

    if not mm.token:
        raise LoginFailedException("Login succeeded but no token was returned.")
    return mm.token


@click.group("auth")
def auth() -> None:
    """Manage Monarch Money authentication."""


@auth.command()
@click.option("--email", prompt="Email", help="Monarch Money email address")
@click.option("--mfa-secret", default=None, help="TOTP secret for automatic MFA")
def login(email: str, mfa_secret: str | None) -> None:
    """Log in to Monarch Money (email/password + MFA)."""
    password = getpass.getpass("Password: ")
    try:
        token = asyncio.run(_do_login(email, password, mfa_secret))
    except LoginFailedException as exc:
        click.echo(f"Login failed: {exc}", err=True)
        raise SystemExit(1)
    store_token(token)
    click.echo("Logged in. Session saved to keyring.")


@auth.command()
def logout() -> None:
    """Clear stored session."""
    clear_token()
    click.echo("Logged out. Session removed from keyring.")


@auth.command()
def status() -> None:
    """Check if a session token is stored and valid."""
    token = get_token()
    if not token:
        click.echo("Not logged in.")
        raise SystemExit(1)

    mm = MonarchMoney(token=token)
    try:
        result = asyncio.run(mm.get_subscription_details())
        sub = result.get("subscription", {})
        click.echo("Authenticated.")
        click.echo(f"  Premium: {sub.get('hasPremiumEntitlement', 'unknown')}")
    except Exception as exc:
        click.echo(f"Token stored but may be invalid: {exc}", err=True)
        raise SystemExit(1)
