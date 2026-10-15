# Test Case: Package a Python CLI for nixpkgs

I want to add `pdf-tidy` to nixpkgs. It's a Python 3.12 command line tool published on PyPI and
GitHub (tag format `v1.3.0`). It builds with hatchling, depends on `click` and `pypdf`, ships a
pytest suite, and exposes a `pdf-tidy` executable. Show me how you'd write it and which checks
you'd run before opening the PR. Assume I have a nixpkgs checkout and an x86_64-linux machine only.
