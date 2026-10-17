# Contributing

Contributions to this community-maintained fork are welcome. The project is
derived from [skyme5/snapchat-dl](https://github.com/skyme5/snapchat-dl); the
original author and contributors remain credited in the repository.

This fork publishes the `snapchat-dl-community` distribution on PyPI while
keeping the `snapchat-dl` command and `snapchat_dl` Python import. Please do not
install it alongside the original `snapchat-dl` distribution because both
packages provide the same command and import.

## Report an Issue

Use the [issue tracker](https://github.com/DevKyleS/snapchat-dl/issues) and
choose the bug report or feature request form. Before opening an issue, check
for an existing report. Include enough detail to reproduce the problem, but do
not post credentials, private account information, or other sensitive data.
This project handles public Snapchat content only.

## Set Up a Development Environment

The package requires Python 3.11 or newer. CI currently tests Python 3.11 and
3.15.

1. Fork this repository on GitHub, then clone your fork and enter the project:

   ```bash
   git clone https://github.com/<your-username>/snapchat-dl.git
   cd snapchat-dl
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows, activate it with `.venv\Scripts\activate`.

3. Install the package and development tools:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -e .
   python -m pip install -r requirements_dev.txt
   ```

4. Create a branch for your change:

   ```bash
   git switch -c concise-description
   ```

## Run Checks

Run the automated unit tests before submitting changes:

```bash
make test
```

The regular test suite uses mocked responses and does not require live Snapchat
requests. Optional live tests are in `integration_tests/` and can be run with
`make test-integration`; they require network access and may depend on content
still being available. FFmpeg is needed for workflows that combine downloaded
HLS media.

Format Python source and tests with Black:

```bash
black snapchat_dl tests
```

If you change documentation, build it locally with `make docs`. Generated docs
are written to `docs/_build/html/`.

## Submit a Pull Request

- Keep the change focused and explain the user-visible behavior it addresses.
- Add or update tests for behavior changes. Include regression coverage when
  fixing a bug.
- Update user or developer documentation when behavior or workflows change.
- Run the relevant checks above and describe their results in the pull request.
- Avoid unrelated formatting or generated-file changes.

Push your branch to your fork and open a pull request against this repository's
`main` branch. The CI workflow tests the suite on Python 3.11 and 3.15.

## Maintainer Releases

Set the package version in `snapchat_dl/version.py`, verify the release contents
and tests, then push a tag in the `vMAJOR.MINOR.PATCH` format (for example,
`v2.2.0`). The publish workflow builds the distributions and uploads them to
PyPI through GitHub Actions trusted publishing. It runs for tags matching
`v*.*.*`; the repository's `publish` environment and PyPI trusted publisher
configuration must remain enabled.
