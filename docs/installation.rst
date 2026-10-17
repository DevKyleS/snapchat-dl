.. highlight:: shell

============
Installation
============


Stable release
--------------

This community-maintained fork keeps the ``snapchat-dl`` command and the
``snapchat_dl`` Python import. It has a separate PyPI distribution name and
should replace, not be installed alongside, the original ``snapchat-dl``
package.

Python 3.11 or newer is required. Install ``pipx`` using the `pipx installation
guide`_, then install the package:

.. code-block:: console

    $ pipx install snapchat-dl-community
    $ snapchat-dl --help

To install or upgrade directly from the latest ``main`` branch instead:

.. code-block:: console

    $ pipx install --force 'git+https://github.com/DevKyleS/snapchat-dl.git@main'
    $ snapchat-dl --help

Alternatively, use a virtual environment:

.. code-block:: console

    $ python3 -m venv .venv
    $ source .venv/bin/activate
    $ python -m pip install --upgrade pip
    $ python -m pip install snapchat-dl-community
    $ snapchat-dl --help

If your Python installation does not include ``venv``, consult your operating
system's Python documentation. Do not use ``sudo pip`` or
``--break-system-packages`` to install this package system-wide.

If switching from the original distribution, uninstall it from the same
environment where it was installed before installing this one. For example,
use ``pipx uninstall snapchat-dl`` if it was installed with ``pipx``, or
activate its virtual environment and run ``python -m pip uninstall snapchat-dl``
there.

.. _pipx installation guide: https://pipx.pypa.io/stable/installation/


From sources
------------

Clone the public `Github repo`_:

.. code-block:: console

    $ git clone https://github.com/DevKyleS/snapchat-dl.git

Then install the source in a virtual environment:

.. code-block:: console

    $ cd snapchat-dl
    $ python3 -m venv .venv
    $ source .venv/bin/activate
    $ python -m pip install --upgrade pip
    $ python -m pip install .


.. _Github repo: https://github.com/DevKyleS/snapchat-dl
