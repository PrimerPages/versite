# Contribute to versite

## Set up a development environment

You need Python 3.10 or later and Git.

1. Clone the repository:

   ```bash
   git clone https://github.com/PrimerPages/versite.git
   cd versite
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install versite in editable mode and install the test dependencies:

   ```bash
   python -m pip install -e . pytest
   ```

## Run tests

From the repository root, run:

```bash
python -m pytest -q
```

The tests use temporary Git repositories to check branch updates, aliases,
redirects, metadata, and version ordering. Add regression coverage when you
change those behaviors.

CI runs the Python tests on Python 3.10, 3.11, and 3.12. It also exercises the
GitHub action against a local deployment branch without pushing.

## Update documentation

Keep [README.md](README.md) focused on installing and using versite. Put
implementation details and contributor instructions in this file. Use the
[Google developer documentation style guide](https://developers.google.com/style),
including sentence-case headings, active voice, and task-oriented instructions.

## Integrate a version selector

Themes can read `versions.json` from the root of the deployment directory to
build a version selector. Each entry includes a version identifier, display
title, aliases, and properties:

```json
[
  {
    "version": "1.0",
    "title": "Version 1.0",
    "aliases": ["latest"],
    "properties": {}
  }
]
```

Preserve the array order when you display versions. Versite uses
`inversion.loose.Version` and mike's development-versus-release grouping to
produce that order. A title or alias can change independently of the version
identifier.

## Maintain the GitHub action

The composite action in [action.yml](action.yml) installs versite from
`github.action_path`, configures a Git author, and calls the versite commands.
Consumers need to check out their site repository before using the action;
they don't need to check out the versite repository separately.
