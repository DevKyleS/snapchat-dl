<p>
  <div align="center">
  <h1>
    Snapchat Public Stories Downloader Community<br /> <br />
    <a href="https://pypi.org/project/snapchat-dl-community/">
      <img
        src="https://img.shields.io/pypi/v/snapchat-dl-community.svg?cacheSeconds=360"
        alt="Python Package"
      />
    </a>
    <a href="https://pypi.org/project/snapchat-dl-community/">
      <img
        src="https://img.shields.io/pypi/wheel/snapchat-dl-community"
        alt="Python Wheel"
      />
    </a>
    <a href="https://github.com/DevKyleS/snapchat-dl/actions/workflows/continuous-integration-pip.yml">
      <img
        src="https://img.shields.io/github/actions/workflow/status/DevKyleS/snapchat-dl/continuous-integration-pip.yml?cacheSeconds=360"
        alt="CI"
      />
    </a>
    <a href="https://codecov.io/gh/DevKyleS/snapchat-dl">
      <img
        src="https://img.shields.io/codecov/c/github/DevKyleS/snapchat-dl?cacheSeconds=360"
        alt="Code Coverage"
      />
    </a>
    <a href="https://pypi.org/project/snapchat-dl-community/">
      <img
        src="https://img.shields.io/pypi/pyversions/snapchat-dl-community"
        alt="Python Versions"
      />
    </a>
    <a href="https://github.com/psf/black">
      <img
        src="https://img.shields.io/badge/code%20style-black-000000.svg"
        alt="The Uncompromising Code Formatter"
      />
    </a>
    <a href="https://opensource.org/licenses/MIT">
      <img
        src="https://img.shields.io/badge/License-MIT-blue.svg"
        alt="License: MIT"
      />
    </a>
  </h1>
  </div>
</p>

### Installation

This community-maintained fork keeps the `snapchat-dl` command and `snapchat_dl`
Python import. It uses a separate PyPI distribution name and should replace,
not be installed alongside, the original `snapchat-dl` package.

Python 3.11 or newer is required. Install `pipx` using its
[installation guide](https://pipx.pypa.io/stable/installation/), then install
the package:

```bash
pipx install snapchat-dl-community
snapchat-dl --help
```

Alternatively, install into a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install snapchat-dl-community
snapchat-dl --help
```

If your Python installation does not include `venv`, consult your operating
system's Python documentation. Do not use `sudo pip` or
`--break-system-packages` to install this package system-wide.

If switching from the original distribution, uninstall it from the same
environment where it was installed before installing this one. For example,
use `pipx uninstall snapchat-dl` if it was installed with `pipx`, or activate
its virtual environment and run `python -m pip uninstall snapchat-dl` there.

### Privacy

The downloader does not collect usage analytics or send application telemetry.
It makes network requests to retrieve the public stories and media requested by
the user. The provided devcontainer disables VS Code telemetry. For local VS
Code sessions outside the devcontainer, set the user setting
`telemetry.telemetryLevel` to `off`; extensions may have their own telemetry
settings.

GitHub Actions explicitly uploads CI coverage reports to Codecov. This is
project coverage data, not runtime telemetry.

### Usage

Quote publisher URLs that contain query parameters so the shell passes the full
URL to `snapchat-dl` instead of treating `&` as a background operator:

```bash
snapchat-dl 'https://story.snapchat.com/p/<publisher-id>/<story-id>?timestamp=-1&share_id=<share-id>&locale=en-US'
```

```text

usage: snapchat-dl [-h] [-c | -u] [-i BATCH_FILENAME] [-P DIRECTORY_PREFIX]
                   [-s] [-d] [-l MAX_NUM_STORY] [-j MAX_WORKERS] [-t INTERVAL]
                   [--sleep-interval INTERVAL] [-q]
                   [username [username ...]]

positional arguments:
  username              Usernames or publisher URLs. Quote URLs containing
                        query parameters such as '&'.

optional arguments:
  -h, --help            show this help message and exit
  -c, --scan-clipboard  Scan clipboard for story links
                        ('https://story.snapchat.com/<s>/<username>').
  -u, --check-for-update
                        Periodically check for new stories.
  -i BATCH_FILENAME, --batch-file BATCH_FILENAME
                        Read usernames from batch file (one username per
                        line).
  -P DIRECTORY_PREFIX, --directory-prefix DIRECTORY_PREFIX
                        Location to store downloaded media.
  -s, --scan-from-prefix
                        Scan usernames (as directory name) from prefix
                        directory.
  -d, --dump-json       Save metadata to a JSON file next to downloaded
                        videos/pictures.
  -l MAX_NUM_STORY, --limit-story MAX_NUM_STORY
                        Set maximum number of stories to download.
  -j MAX_WORKERS, --max-concurrent-downloads MAX_WORKERS
                        Set maximum number of parallel downloads.
  -t INTERVAL, --update-interval INTERVAL
                        Set the update interval for checking new story in
                        seconds. (Default: 10m)
  --sleep-interval INTERVAL
                        Sleep between downloads in seconds. (Default: 1s)
  -q, --quiet           Do not print anything except errors to the console.

```
