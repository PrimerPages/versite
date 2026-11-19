# versite

Use versite to publish multiple versions of a static site from a Git branch.
You can give versions aliases such as `latest`, choose a default version, and
keep older versions available at their existing URLs.

Build your site with MkDocs, Jekyll, or another static site generator before you
run versite. Versite copies the built files into a deployment branch, updates
`versions.json`, and commits the result.

## Install versite

You need Python 3.10 or later and Git. Install versite from this repository:

```bash
python -m pip install "git+https://github.com/PrimerPages/versite.git"
versite --help
```

## Deploy a version

Run these commands from your site's Git repository, with an `origin` remote
configured for the repository where you publish your site.

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
version preserves the existing versions.

If you want to inspect the result before publishing, omit `--push` to update
only the local deployment branch. Run `versite serve` to preview that branch at
`http://127.0.0.1:8000`.

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
publish those changes.

| Task | Command |
| --- | --- |
| List versions and aliases. | `versite list` |
| Get version metadata as JSON. | `versite list 1.0 --json` |
| Assign an alias to a version. | `versite alias 1.0 stable --push` |
| Change a version's display title. | `versite retitle 1.0 "Version 1.0" --push` |
| Read a version's properties. | `versite props 1.0 --json` |
| Change the default version. | `versite set-default stable --push` |
| Delete a version or alias. | `versite delete 1.0 --push` |

For all available options, run `versite --help` or `versite COMMAND --help`.

## Use the GitHub action

Build your site before calling the action. The following Jekyll workflow
builds a version and pushes it to `gh-pages`:

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
`latest` alias. See the [action inputs](action.yml) for configuration options.

## Advanced

### Build for versioned URLs

Configure generated links for the location where you publish each version.
Versite preserves the URLs in your built files.

For MkDocs, set `site_url` to the version's published URL in your build
configuration. If your configuration uses version environment variables, pass
them when you build:

```bash
VERSION=1.0
VERSITE_VERSION="$VERSION" MIKE_DOCS_VERSION="$VERSION" \
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

### Choose an alias mode

Set `alias_type` in `versite.yml` to choose how aliases work:

| Mode | Behavior |
| --- | --- |
| `redirect` | Creates HTML redirects to the version. This is the default and works with GitHub Pages. |
| `copy` | Copies the version's files into each alias directory. |
| `symlink` | Creates symbolic links. Use this mode only if your host supports them. |

### Version ordering

Version selectors that read `versions.json` use the same order as `versite list`:

- Development names such as `dev`, `devel`, and `nightly` appear above numbered versions.
- Each group uses mike's loose version ordering, from newest to oldest.
- Comparisons use the version identifier as written, including any `v` prefix.
  Use a consistent prefix to keep numbered versions in the order you expect.

Changing a display title or alias doesn't change the sort order. Existing
entries are sorted the next time you deploy or update version metadata.

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

## Contribute

For development setup, tests, and theme integration details, see
[Contribute to versite](CONTRIBUTING.md).
