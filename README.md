# versite

Versite brings [mike](https://github.com/jimporter/mike)-style versioned
documentation to any static site generator. Build your site with MkDocs,
Jekyll, or another tool, then use versite to publish versions, manage aliases,
and choose a default version.

Each version has its own directory in a Git deployment branch, so older
versions stay available at their existing URLs. Versite manages the built files,
redirects, and version metadata independently of your build tool.

## Install versite

You need Python 3.10 or later and Git. Install versite from this repository:

```bash
python -m pip install "git+https://github.com/PrimerPages/versite.git"
versite --help
```

## Deploy a version

Run these commands from your site's Git repository. The repository must have
at least one commit and an `origin` remote configured for your deployment
repository.

1. Build your site into a directory such as `dist/site`. Configure your site
   generator to use the version's URL path. For example, version `1.0` hosted at
   `https://example.com/project/1.0/` needs a base path of `/project/1.0`.
2. Deploy the built files and assign the `latest` alias:

   ```bash
   versite deploy 1.0 latest --site-dir dist/site --push
   ```

3. Set the root URL to redirect to `latest`:

   ```bash
   versite set-default latest --push
   ```

By default, versite stores the site in the `gh-pages` branch. Version `1.0` is
available under `1.0/`, and `latest/` redirects to that version. Deploying a new
version preserves the existing versions. Redeploying a version refreshes all
aliases attached to it, even if you omit those aliases from the command.

To preview a deployment locally, keep `push: false` in your configuration and
omit `--push`. Run `versite serve` to preview the local deployment branch at
`http://127.0.0.1:8000`.

These commands update the deployment branch. Your host serves the files from
that branch or from a deployment artifact. For GitHub Pages, see
[Publish with GitHub Pages](#publish-with-github-pages).

For build examples, see [Build for versioned URLs](#build-for-versioned-urls).

## Configure deployments

Create `versite.yml` in your site's repository to set deployment defaults:

```yaml
remote: origin
branch: gh-pages
push: false
alias_type: redirect
deploy_prefix: ""
redirect_template: null
```

Command-line options override these settings. For example, to deploy to a
branch named `docs`:

```bash
versite deploy 1.0 --site-dir dist/site --branch docs --push
```

Use `--config-file PATH` to read a different configuration file.

## Manage versions

Use a version identifier or one of its aliases to select a published version.
Add `--push` to commands that change the deployment branch when you want to
push those changes to your remote. If you assign an existing alias to another
version, versite moves that alias to the selected version.

| Task | Command |
| --- | --- |
| List versions and aliases. | `versite list` |
| Get version metadata as JSON. | `versite list 1.0 --json` |
| Assign an alias to a version. | `versite alias 1.0 stable --push` |
| Change a version's display title. | `versite retitle 1.0 "Version 1.0" --push` |
| Read a version's properties. | `versite props 1.0 --json` |
| Set a version property. | `versite props 1.0 hidden=true --push` |
| Delete a version property. | `versite props 1.0 hidden- --push` |
| Change the default version. | `versite set-default stable --push` |
| Delete a version or alias. | `versite delete 1.0 --push` |

For all available options, run `versite --help` or `versite COMMAND --help`.

## Use the GitHub action

Use the action after you build your site. This Jekyll workflow builds a version
and pushes the result to `gh-pages`. Configure your hosting service separately
to publish the branch contents.

```yaml
name: Site

on:
  workflow_dispatch:
    inputs:
      version:
        description: Version identifier to publish
        required: true
        type: string

permissions:
  contents: write

jobs:
  site:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - uses: ruby/setup-ruby@v1
        with:
          ruby-version: "3.3"
          bundler-cache: true

      - name: Build site
        env:
          VERSION: ${{ inputs.version }}
        run: |
          bundle exec jekyll build \
            --destination _site \
            --baseurl "/$VERSION"

      - uses: PrimerPages/versite@main
        with:
          version: ${{ inputs.version }}
          aliases: latest
          default-to: latest
          site-dir: _site
          branch: gh-pages
          push: true
```

The example assumes your site is hosted at the domain root. If you host it under
a repository path, include that path in `--baseurl`, such as
`"/my-project/$VERSION"`.

Use `default-to: latest` to make the site's root URL redirect to the current
`latest` alias. With `deploy-prefix: docs`, this redirects `docs/` to
`docs/latest/`. Omit `default-to` to preserve an existing default redirect.
See the [action inputs](action.yml) for configuration options.

## Advanced

### Build for versioned URLs

Configure generated links for the location where you publish each version.
Versite preserves the URLs in your built files.

For MkDocs, read the version's published URL from an
[environment variable](https://www.mkdocs.org/user-guide/configuration/#environment-variables)
in `mkdocs.yml`:

```yaml
site_url: !ENV VERSITE_SITE_URL
```

Set that variable when you build, then deploy the result:

```bash
VERSION=1.0
VERSITE_SITE_URL="https://example.com/project/$VERSION/" \
  mkdocs build --clean --site-dir dist/site
versite deploy "$VERSION" latest --site-dir dist/site --push
```

For Jekyll, set the base path when you build:

```bash
VERSION=1.0
bundle exec jekyll build --destination dist/site --baseurl "/$VERSION"
versite deploy "$VERSION" latest --site-dir dist/site --push
```

Include any repository or hosting prefix in the base path. The `deploy_prefix`
setting controls the directory inside the deployment branch; configure your
site generator's URLs separately.

With `deploy_prefix: docs`, the default redirect lives at `docs/index.html`.
Running `versite set-default latest` redirects `docs/` to `docs/latest/` and
leaves the branch's root `index.html` unchanged. Each deployment prefix has
its own version metadata and default redirect.

### Choose an alias mode

Set `alias_type` in `versite.yml` to choose how aliases work. Override it with
`--alias-type` on `deploy` or `alias`, or with the action's `alias-type` input.
Each deployment recreates all aliases attached to its version using this mode:

| Mode | Behavior |
| --- | --- |
| `redirect` | Creates HTML redirects to the version. This is the default and works with GitHub Pages. |
| `copy` | Copies the version's files into each alias directory. |
| `symlink` | Creates symbolic links. Use this mode only if your host supports them. |

### Version ordering

Version selectors that read `versions.json` use the same order as `versite list`:

- Development names such as `dev`, `devel`, and `nightly` appear above numbered versions.
- Numbered versions use mike's loose version comparison, from newest to oldest.
  Development names use the same comparator within their group.
- Comparisons use the version identifier as written, including any `v` prefix.
  Use a consistent prefix to keep numbered versions in the order you expect.

Changing a display title or alias doesn't change the sort order. Existing
entries are sorted the next time you deploy or update version metadata.

### Synchronize the deployment branch

Versite fetches the deployment branch before checking its local state. If the
local branch is behind the remote, versite advances it with a fast-forward.
Local commits are preserved. If the histories have diverged, resolve the
divergence before deploying again.

Use `--ignore-remote-status` to skip fetching and synchronization. This option
doesn't force a push or resolve diverged histories.

### Publish with GitHub Pages

Versite updates the deployment branch. Choose how GitHub Pages publishes its
contents:

- For branch publishing, select `gh-pages` as the source in your repository's
  Pages settings. Pushes authenticated with `GITHUB_TOKEN` don't trigger Pages
  builds; use a suitable personal access token or GitHub App token if you need
  the push to trigger publishing.
- For Actions publishing, package the complete updated deployment branch with
  `actions/upload-pages-artifact` and publish it with `actions/deploy-pages`.
  Include every version, the aliases, and `versions.json` in the artifact.

### Migrate from mike

Build your MkDocs site before running `versite deploy`. Move deployment settings
into `versite.yml`.

| mike command | versite equivalent |
| --- | --- |
| `mike deploy 1.0 latest` | Build the site, then run `versite deploy 1.0 latest --site-dir dist/site`. |
| `mike list`, `delete`, `alias`, `retitle`, `props`, or `set-default` | Use the corresponding versite command. |

The command names are familiar, but supported options and some behaviors differ:

- Versite moves an existing alias when you assign it to another version, without
  requiring `--update-aliases`.
- Use `versite props 1.0 hidden=true` to set a property and
  `versite props 1.0 hidden-` to delete it. The `props` command uses this syntax
  instead of mike's property-editing flags.

Run `versite COMMAND --help` to check the available options before adapting a
script that uses mike.

## Contribute

For development setup, tests, and theme integration details, see
[Contribute to versite](CONTRIBUTING.md).
