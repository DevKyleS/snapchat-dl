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

For a fresh install:

```bash
python -m pip install snapchat-dl-community
```

To switch from the original PyPI package, uninstall it first so its files and
console script do not conflict with the community distribution:

```bash
python -m pip uninstall snapchat-dl
python -m pip install --upgrade snapchat-dl-community
snapchat-dl --help
```

To install the current source directly from GitHub:

```bash
python -m pip install --upgrade git+https://github.com/DevKyleS/snapchat-dl.git
```

### Usage

```text

usage: snapchat-dl [-h] [-c | -u] [-i BATCH_FILENAME] [-P DIRECTORY_PREFIX]
                   [-s] [-d] [-l MAX_NUM_STORY] [-j MAX_WORKERS] [-t INTERVAL]
                   [--sleep-interval INTERVAL] [-q]
                   [username [username ...]]

positional arguments:
  username              At least one or more usernames to download stories
                        for.

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
