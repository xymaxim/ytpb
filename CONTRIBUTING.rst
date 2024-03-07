Contributing
############

Reporting a problem
*******************

To report a problem, create a `GitHub issue
<https://github.com/xymaxim/ytpb/issues/>`__.

It would be much helpful to provide some information: a reference to a live
stream, command executed, and output. If available, please include all error
messages and tracebacks. One way is to run a command with the ``--report``
option: ::

  $ ytpb --report COMMAND ...

This will create a debug (``--debug`` is automatically implied) log file
``ytpb-yyyymmdd-HHMMSS.log``. For privacy, actual IP addresses in the output will
be replaced with ``0.0.0.0``.

Contributing code
*****************

To install all development requirements, simply run: ::

  $ pip install -e .[dev]

Testing
=======

Ytpb uses `pytest <https://docs.pytest.org/>`_ for unit and functional
tests.

Here is the structure of the ``tests`` directory:

.. code:: text

	  .
          ...
          ├── cli
          ├── data
          │   ├── expected
          │   ├── gap-cases
          │   └── segments

* ``...`` — unit tests are located here
* ``cli`` contains functional tests for the CLI application
* ``data`` contains testing data and artifacts

  * ``expected`` — expected test outputs

  * ``gap-cases`` — data for testing gap cases

  * ``segments`` — media segments

Running tests
-------------

To run all tests: ::

  $ python -m pytest tests

Mocking network calls
---------------------

Any network calls are disabled by the `pytest-socket
<https://github.com/miketheman/pytest-socket>`_ plugin. Instead, the `responses
<https://github.com/getsentry/responses>`_ package is used for mocking responses
from remote sources.

Functional tests
----------------

*Match outputs*
^^^^^^^^^^^^^^^

The actual test outputs are compared to the pre-defined expected ones with the
help of the `pytest-matcher <https://github.com/zaufi/pytest-matcher>`__
plugin. Such tests are characterized by the use of the plugin's ``expected_out``
fixture. The expected outputs are stored as files in
``./tests/data/expected``. Before running newly added tests, expectation files
should be generated (or if needed, updated for existing tests): ::

  $ python -m pytest --pm-save-patterns ...

And then, you can run tests as usual.
