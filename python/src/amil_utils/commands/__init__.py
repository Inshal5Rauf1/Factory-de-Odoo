"""Commands package -- extracted business logic from cli.py.

Each submodule exposes pure-Python ``execute_*`` functions that accept
structured arguments and return dicts/lists.  The Click wiring in
``cli.py`` calls these functions and translates the results into
user-facing output.
"""
