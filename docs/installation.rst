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

For a fresh install, run:

.. code-block:: console

    $ python -m pip install snapchat-dl-community

To switch from the original package, uninstall it first so its files and
console script do not conflict with the community distribution:

.. code-block:: console

    $ python -m pip uninstall snapchat-dl
    $ python -m pip install --upgrade snapchat-dl-community
    $ snapchat-dl --help

To install the current source directly from GitHub:

.. code-block:: console

    $ python -m pip install --upgrade git+https://github.com/DevKyleS/snapchat-dl.git

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

The sources for Snapchat Downloader can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone https://github.com/DevKyleS/snapchat-dl.git

Or download the `tarball`_:

.. code-block:: console

    $ curl -L -o snapchat-dl-community.tar.gz https://github.com/DevKyleS/snapchat-dl/archive/refs/heads/main.tar.gz

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ python setup.py install


.. _Github repo: https://github.com/DevKyleS/snapchat-dl
.. _tarball: https://github.com/DevKyleS/snapchat-dl/archive/refs/heads/main.tar.gz
