# versite

`versite` is a generic versioned static-site deployment tool inspired by `mike`, but it is not coupled to MkDocs. It manages a deployment branch containing multiple published site versions, aliases, redirects, and per-version metadata. Only `versite deploy` is allowed to invoke a site builder.

## Why it exists

`mike` is tightly centered on MkDocs. `versite` separates the problem into two layers:

1. A versioned static-site manager that edits `versions.json`, alias paths, redirects, and the target git branch.
2. A command-based builder runner that invokes builders as external subprocesses only during `deploy`.

That separation means non-build commands stay fast and reliable:

- `versite list`
- `versite delete`
- `versite alias`
- `versite retitle`
- `versite props`
- `versite set-default`
- `versite serve`

Those commands do not import MkDocs, load MkDocs config, run MkDocs plugin hooks, invoke Jekyll, or shell out to any builder.

## Installation

```bash
pip install -e .
versite --help
```

## Configuration

`versite` reads `versite.yml` if present. The config loader only uses lightweight YAML parsing.

```yaml
builder: mkdocs
remote: origin
branch: gh-pages
deploy_prefix: ""
alias_type: redirect
redirect_template: null
push: false

builders:
  mkdocs:
    command:
      - mkdocs
      - build
      - --clean
      - --config-file
      - "{config_file}"
      - --site-dir
      - "{output_dir}"
    config_file: mkdocs.yml

  jekyll:
    command:
      - bundle
      - exec
      - jekyll
      - build
      - --source
      - "{source}"
      - --destination
      - "{output_dir}"
    source: .
```

CLI flags override config values.

## MkDocs usage

MkDocs support is implemented only as a command template. `versite` never imports `mkdocs`.

```bash
versite deploy 1.0 latest --builder mkdocs
versite list
versite set-default latest
versite delete 0.9
```

During `deploy`, the MkDocs builder receives:

- `VERSITE_VERSION=<version>`
- `MIKE_DOCS_VERSION=<version>`

## Jekyll usage

Jekyll support is also command-template based.

```bash
versite deploy 1.0 latest --builder jekyll
versite list
versite alias 1.0 stable
versite set-default latest
```

`versite` does not import Jekyll-related Python libraries. It only runs the configured command during `deploy`.

## Custom builders

Custom builders can be added through `versite.yml` without changing Python code:

```yaml
builder: custom

builders:
  custom:
    command:
      - npm
      - run
      - build
      - --
      - --outDir
      - "{output_dir}"
```

Example:

```bash
versite deploy 1.0 latest --builder custom
```

## Command reference

```bash
versite deploy VERSION [ALIAS...]
versite list [IDENTIFIER]
versite delete [IDENTIFIER...] [--all]
versite alias IDENTIFIER [ALIAS...]
versite retitle IDENTIFIER TITLE
versite props IDENTIFIER [PROP]
versite set-default IDENTIFIER
versite serve
```

Important options:

- `--config-file FILE`
- `--builder NAME`
- `-r, --remote REMOTE`
- `-b, --branch BRANCH`
- `-m, --message MESSAGE`
- `-p, --push`
- `--allow-empty`
- `--deploy-prefix PATH`
- `--alias-type {redirect,copy,symlink}`
- `-T, --template FILE`
- `--ignore-remote-status`
- `--source DIR`
- `--output-dir DIR`
- `--build-command ...`
- `-q, --quiet`
- `--json`

## Alias modes

- `redirect`: writes static HTML redirects. This is the default and works well on GitHub Pages.
- `copy`: copies the deployed version directory into each alias directory.
- `symlink`: creates symlink aliases in the target branch for compatibility-focused setups.

## GitHub Pages

`versite` is designed for branch-based static hosting. A common setup is `gh-pages` with redirect aliases and a root `index.html` redirect created by `set-default`.

Example MkDocs config:

```yaml
builder: mkdocs
branch: gh-pages
alias_type: redirect

builders:
  mkdocs:
    command:
      - mkdocs
      - build
      - --clean
      - --config-file
      - "{config_file}"
      - --site-dir
      - "{output_dir}"
    config_file: mkdocs.yml
```

Example Jekyll config:

```yaml
builder: jekyll
branch: gh-pages
alias_type: redirect

builders:
  jekyll:
    command:
      - bundle
      - exec
      - jekyll
      - build
      - --source
      - "{source}"
      - --destination
      - "{output_dir}"
    source: .
```

## Migration from mike

- `mike deploy` roughly maps to `versite deploy --builder mkdocs`.
- `mike list`, `delete`, `alias`, `retitle`, `props`, and `set-default` roughly map to the same `versite` subcommands.
- Unlike `mike`, non-build commands do not load MkDocs config.
- Shared deployment settings should move into `versite.yml`.
- `VERSITE_VERSION` is the generic build env var. MkDocs builders also receive `MIKE_DOCS_VERSION` for compatibility.
