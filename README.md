# versite

`versite` is a versioned static-site deployment tool for prebuilt static site directories. It manages a deployment branch containing multiple published site versions, aliases, redirects, and per-version metadata.

## Why it exists

`versite` focuses on deployment branch management only. It copies a prebuilt static site into a versioned path, updates `versions.json`, manages aliases and redirects, and commits the result to the deployment branch.

It does not:

- build MkDocs sites
- build Jekyll sites
- run custom build commands
- rewrite generated asset URLs after a site is built

## Installation

```bash
pip install -e .
versite --help
```

## Configuration

`versite` reads `versite.yml` if present. The config loader only uses lightweight YAML parsing.

```yaml
remote: origin
branch: gh-pages
deploy_prefix: ""
alias_type: redirect
redirect_template: null
push: false
```

CLI flags override config values.

## Prebuilt Site Deployment

Deploy expects a prebuilt static site directory:

```bash
versite deploy 1.0 latest --site-dir path/to/site
```

`versite` publishes the contents of `--site-dir` into the deployment branch under the version path, updates `versions.json`, manages aliases, and writes redirects when needed.

If the generated site needs a versioned base path, that must be handled during the build step before `versite` sees the output. `versite` does not rewrite generated HTML, CSS, JavaScript, or asset URLs after the fact.

## Migration Examples

MkDocs:

```bash
VERSION=1.0
VERSITE_VERSION="$VERSION" MIKE_DOCS_VERSION="$VERSION" mkdocs build --clean --site-dir dist/site
versite deploy "$VERSION" latest --site-dir dist/site
```

Jekyll:

```bash
VERSION=1.0
bundle exec jekyll build --destination dist/site --baseurl "/$VERSION"
versite deploy "$VERSION" latest --site-dir dist/site
```

For Jekyll and other generators that emit root-based asset or page URLs, build with the correct base path for the versioned deployment location.

## Command Reference

```bash
versite deploy VERSION [ALIAS...] --site-dir path/to/site
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
- `-r, --remote REMOTE`
- `-b, --branch BRANCH`
- `-m, --message MESSAGE`
- `-p, --push`
- `--allow-empty`
- `--deploy-prefix PATH`
- `--alias-type {redirect,copy,symlink}`
- `-T, --template FILE`
- `--ignore-remote-status`
- `--site-dir DIR`
- `--json`

## Alias Modes

- `redirect`: writes static HTML redirects. This is the default and works well on GitHub Pages.
- `copy`: copies the deployed version directory into each alias directory.
- `symlink`: creates symlink aliases in the target branch for compatibility-focused setups.

## GitHub Pages

`versite` is designed for branch-based static hosting. A common setup is `gh-pages` with redirect aliases and a root `index.html` redirect created by `set-default`.

Example:

```yaml
branch: gh-pages
alias_type: redirect
push: false
```

## GitHub Action

The repository includes a reusable composite action at [`action.yml`](/home/athackst/Code/primerpages/versite/action.yml).

Example usage:

```yaml
- uses: owner/repo@main
  with:
    version: 1.0
    aliases: latest
    site-dir: dist/site
    branch: gh-pages
    push: true
```

The action installs `versite` from the checked-out repository, then runs `versite deploy` with the inputs you provide. It is meant for prebuilt site output, so your workflow should build the site before invoking it.
Internally it uses `github.action_path`, so consumers do not need to check out the action repository manually.

## Migration From mike

- `mike deploy` roughly maps to building the site first and then running `versite deploy --site-dir ...`.
- `mike list`, `delete`, `alias`, `retitle`, `props`, and `set-default` roughly map to the same `versite` subcommands.
- Unlike `mike`, `versite` does not run MkDocs builds.
- Shared deployment settings should move into `versite.yml`.
