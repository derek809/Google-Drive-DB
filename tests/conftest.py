"""Shared test configuration — adds project directories to sys.path."""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for subdir in [
    "brain",
    "core",
    "core/Infrastructure",
    "core/InputOutput",
    "core/State&Memory",
    "Bot_actions",
    "LLM",
]:
    path = os.path.join(_root, subdir)
    if path not in sys.path:
        sys.path.insert(0, path)
