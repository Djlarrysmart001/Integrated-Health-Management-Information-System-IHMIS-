# app/commands.py
#
# Flask CLI commands for database management.
# Run these from your terminal:
#   flask seed-roles
#   flask seed-admin

import click
from flask import Flask
from app.services.auth_service import AuthService


def register_commands(flask_app: Flask) -> None:
    """Registers all custom CLI commands with the Flask app."""

    @flask_app.cli.command("seed-roles")
    def seed_roles():
        """Creates the 5 default roles in the database."""
        AuthService.seed_roles()

    @flask_app.cli.command("seed-admin")
    @click.option("--username",   prompt="Username",   help="Admin username")
    @click.option("--email",      prompt="Email",      help="Admin email")
    @click.option("--password",   prompt="Password",   hide_input=True, help="Admin password")
    @click.option("--first-name", prompt="First name", help="Admin first name")
    @click.option("--last-name",  prompt="Last name",  help="Admin last name")
    def seed_admin(username, email, password, first_name, last_name):
        """Creates the first Admin user account."""
        AuthService.seed_admin(username, email, password, first_name, last_name)