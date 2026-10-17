#!/usr/bin/env python
"""The setup script."""
from setuptools import find_packages
from setuptools import setup


version = {}
with open("snapchat_dl/version.py") as fp:
    exec(fp.read(), version)

with open("README.md") as readme_file:
    readme = readme_file.read()

requirements = list()

with open("requirements.txt", "r") as file:
    requirements = [r for r in file.readlines() if len(r) > 0]

setup(
    name="snapchat-dl-community",
    version=version["__version__"],
    description="Community-maintained Snapchat public stories downloader.",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/DevKyleS/snapchat-dl",
    author="Aakash Gajjar",
    author_email="skyqutip@gmail.com",
    maintainer="DevKyleS and contributors",
    maintainer_email="3204236+DevKyleS@users.noreply.github.com",
    entry_points={
        "console_scripts": [
            "snapchat-dl=snapchat_dl.app:main",
        ],
    },
    include_package_data=True,
    install_requires=requirements,
    extras_require={"test": ["pytest", "pytest-cov"]},
    python_requires=">=3.11",
    keywords=["snapchat", "stories", "publisher", "video downloader", "HLS", "CLI"],
    license="MIT license",
    packages=find_packages(include=["snapchat_dl", "snapchat_dl.*"]),
    zip_safe=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.15",
    ],
)
