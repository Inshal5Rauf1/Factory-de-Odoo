"""Prevent pytest from collecting Odoo module fixture files.

The fixtures/docker_test_module/ and fixtures/auto_fix_module/ directories
contain real Odoo modules that require the Odoo runtime to import. These
files are NOT pytest test modules — they are test fixtures for integration tests.
"""

collect_ignore_glob = ["docker_test_module/**/*.py", "auto_fix_module/**/*.py"]
