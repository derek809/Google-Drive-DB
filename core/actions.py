"""
Bridge file to expose Infrastructure/actions.py as core.actions
This fixes the 'ModuleNotFoundError: No module named core.actions' error.
"""
from core.Infrastructure.actions import *
