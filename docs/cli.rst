Command line application
########################

This section describes using the Ytpb command line application: from an overview
and usage of commands to configuring and advanced use cases.

.. contents:: Contents
   :depth: 3
   :backlinks: top
   :local:

Overview
********

Synopsis
========

The general synopsis of ``ytpb`` commands is as follows::

  ytpb [GLOBAL_OPTIONS] COMMAND [SUBCOMMAND] [OPTIONS] [ARGS]...

Commands
--------

.. code:: man

   Usage: ytpb [OPTIONS] COMMAND [ARGS]...

   A playback for YouTube live streams

   Global options:
     --no-config    Do not load any configuration files.
     --config PATH  Specifies a path to a configuration file.
     --report       Dump all output to a file. It implies --debug.
     --debug        Enable verbose output for debugging.
     -q, --quiet    Supress all normal output.

   Other options:
     -V, --version  Show the version and exit.
     --help         Show this message and exit.

   Top-level commands:
     download  Download excerpts.
     capture   Capture a single or many frames.
     mpd       Compose MPEG-DASH manifests.

Subcommands
-----------

*capture*
^^^^^^^^^

.. code:: man

   Usage: ytpb capture [OPTIONS] COMMAND [ARGS]...

     Capture a single or many frames.

   Options:
     --help  Show this message and exit.

   Commands:
     frame      Capture a single frame.
     timelapse  Capture time-lapse frames.

*mpd*
^^^^^

.. code:: man

   Usage: ytpb mpd [OPTIONS] COMMAND [ARGS]...

   Options:
     --help  Show this message and exit.

   Commands:
     compose  Compose an MPEG-DASH manifest.
     refresh  Refresh a composed MPEG-DASH manifest.

Getting help
============

To show a list of available options, type ``--help`` after commands or
subcommands: ::

  $ ytpb --help
  $ ytpb download --help
  $ ytpb mpd compose --help

Usage
*****

Specifying rewind interval
==========================

* ``--interval <start>/<end>``

The rewind interval can be specified with the ```-i/--interval`` option. The
formatting of input interval and its parts is closely compliant with the
ISO-8601 time interval formatting. The interval composes of start and end parts,
separated with the "/" symbol.

These parts are a pair of points in a stream (absolute or relative ones) or some
special literals. The absolute points are date and times (indirect) and sequence
numbers of media segments (direct). One of interval parts can be relative to
another one by a time duration or date and time replacing components.

A. Using dates
--------------

*Date and time of a day*
^^^^^^^^^^^^^^^^^^^^^^^^

* ``--interval <date-time>/<date-time>``

where ``<date-time> = <date>"T"<time>"±"<shift>``:

``YYYY"-"MM"-"DD"T"hh":"mm":"ss"±"hh":"mm`` (I) or

``YYYYMMDD"T"hhmmss"±"hhmm`` (II).

The extended (I) and basic (II) formats are supported.

For example, an interval with two complete date and time representations: ::

  # Complete representations in extended format
  $ ytpb download -i 2024-01-02T10:20:00+00/2024-01-02T10:20:30+00 ...

  # Complete representations in basic format
  $ ytpb download -i 20240102T102000+00/20240102T102030+00 ...

The time part can be also provided with a reduced precision, with some low-order
components omitted (the date part should be always complete): ::

  # Representations with reduced precision in extended format
  $ ytpb download -i 2024-01-02T1020+00/2024-01-02T10:20:30+00 ...

  # Representations with reduced precision in basic format
  $ ytpb download -i 20240102T1020+00/20240102T102030+00 ...

Zulu time
"""""""""

Zulu time refers to the UTC time and denoted with the letter "Z"
used as a suffix instead of time shift. It's applicable for dates here and
elsewhere, even if it's not stated. For example, the following date will be
resolved to the same date as in the example above: ::

    $ ytpb download -i 20240102T1020Z/20240102T102030Z ...

Local time
""""""""""

To represent a local time, the time shift part can be
omitted. For example, if you're in the UTC+02 time zone, the above example
can be represented as: ::

  $ ytpb download -i 20240102T1220/20240102T122030 ...

*Time of today*
^^^^^^^^^^^^^^^

* ``-i/--interval <time>±<shift>/<time>±<shift>``

To refer to a current day, the date part can be ommited: ::

  $ ytpb download -i 10:20+00/T102030+00 ...

*Date and time replacing components*
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This allows to replace particular date and time components in another part of an
interval. The components to replace are referred explicitly by their one-letter
designators.

For example, the start part below: ::

  $ ytpb download -i 2023Y12M31DT1H/2024-01-02T10:20:00+00 ...

will be resolved as: ::

  $ ytpb download -i 2023-12-31T01:20:00+00/2024-01-02T10:20:00+00 ...

Note that the time part delimiter ("T") is necessary when only time components
to change are supplied: ::

  $ ytpb download -i 2024-01-02T10:20:00+00/T25M30S ...

*Unix timestamp*
^^^^^^^^^^^^^^^^

* ``--interval <timestamp>/<timestamp>``

where ``<timestamp> = "@"<epoch-seconds>``:

The date and time interval can also be specified with Unix timestamps as: ::

   $ ytpb download -i @1704190800/@1704190830 ...

B. Using duration
-----------------

* ``-i/--interval <start>/<duration>`` or

* ``-i/--interval <duration>/<end>``,

where ``<duration> = "P"DD"D""T""hh"H"mm"M"ss"S"``.

Sometimes it would be more convenient to specify an interval with duration: (a)
by start and duration and (b) by duration and end.

The duration string is prepended with "P" symbol and used one-letter date and
time component designators. The highest order of date components is days ("D").

For example, here are below two examples representing the same 30-second
interval: ::

  # Specified by a start and a duration
  $ ytpb download -i 2024-01-02T10:20:00+00/PT30S ...

  # Specified by a duration and an end
  $ ytpb download -i PT30S/2024-01-02T10:20:30+00 ...

C. Using sequence numbers
-------------------------

* ``-i/--interval <sequence-number>/<sequence-number>``

Besides dates, you can specify the sequence number (positive, starting from 0)
of an MPEG-DASH `media segment
<https://dashif-documents.azurewebsites.net/Guidelines-TimingModel/master/Guidelines-TimingModel.html#media-segment/>`_
to refer to a specific point in a live stream. Usually, sequence numbers are
used when a segment has already been previously determined.

For example, an interval from the beginning to segment 100: ::

  $ ytpb download -i 0/100 ...

Sequence numbers can also be combined with other types: ::

  $ ytpb download -i 0/2024-01-02T10:20:30+00 ...
  $ ytpb download -i 0/PT30S ...
  $ ytpb download -i 0/now ...

D. Using keywords
-----------------

*'Earliest' keyword*
^^^^^^^^^^^^^^^^^^^^

* ``-i/--interval earliest/<end>``

To refer to the earliest available moment, the start part accepts the ``earliest``
keyword::

  $ ytpb download -i earliest/PT30S ...

It could refer to the beginning of a stream (e.g., the very first media segment)
or the earliest available segment if a stream lasts longer than the time
available to rewind.

*'Now' keyword*
^^^^^^^^^^^^^^^

* ``-i/--interval <start>/now``

To refer to the current moment, the end part accepts the ``now`` keyword: ::

  $ ytpb download -i 20240102T1020+00/now ...

To be exact, it refers to the last available media segment.

.. _Preview mode:

E. Preview mode
---------------

* ``--interval <start>/<end> --preview-start``
* ``--interval <start>/<end> --preview-end``
* ``--interval <start>/.. --preview-start``
* ``--interval ../<end> --preview-end``

If you only need to preview a moment in a stream, which you can refer to later,
the ``-ps / --preview-start`` and ``-pe / --preview-end`` options exist. It's
basically an alias for the short end duration.

In the above, the closed intervals were used, while for the preview modes, you
can define (not necessarily, though) intervals with an open end designated with
the '..' literal: ::

  $ ytpb download -i 2024-01-02T10:20:00+00/.. -ps ...
  $ ytpb download -i ../2024-01-02T10:20:00+00 -pe ...

(In case of a closed interval, the start or end part will be ignored, and you'll
see a note in the output that the preview mode is enabled.)

By default, the output preview duration varies from 10 to 10 + one segment
duration seconds. The imprecision is due to the reliance on the full-length,
uncut end segment (to reduce merging time). The minimal preview duration value
can be changed via the ``general.preview_duration`` field in the ``config.toml``
file.

Compatibility table
-------------------

.. table:: **Table:** Interval parts compatibility

   +---------------------------+---------------+------+----------+----------------------+-----------------+------------+-------------+
   |                           | Date and time | Time | Duration | Replacing components | Sequence number | 'Earliest' | 'Now', '..' |
   |                           | / Timestamp   |      |          |                      |                 |            |             |
   +===========================+===============+======+==========+======================+=================+============+=============+
   | Date and time / Timestamp |       Y       |  Y   |    Y     |          Y           |        Y        |      Y     |      Y      |
   +---------------------------+---------------+------+----------+----------------------+-----------------+------------+-------------+
   | Time                      |       Y       |  Y   |    Y     |         *N*          |        Y        |      Y     |      Y      |
   +---------------------------+---------------+------+----------+----------------------+-----------------+------------+-------------+
   | Duration                  |       Y       |  Y   |   *N*    |         *N*          |        Y        |      Y     |     *N*     |
   +---------------------------+---------------+------+----------+----------------------+-----------------+------------+-------------+
   | Replacing components      |       Y       | *N*  |   *N*    |         *N*          |       *N*       |     *N*    |     *N*     |
   +---------------------------+---------------+------+----------+----------------------+-----------------+------------+-------------+
   | Sequence number           |       Y       |  Y   |    Y     |         *N*          |        Y        |      Y     |      Y      |
   +---------------------------+---------------+------+----------+----------------------+-----------------+------------+-------------+
   | 'Earliest'                |       Y       |  Y   |    Y     |         *N*          |        Y        |     *N*    |      Y      |
   +---------------------------+---------------+------+----------+----------------------+-----------------+------------+-------------+
   | 'Now', '..'               |       Y       |  Y   |   *N*    |         *N*          |        Y        |      Y     |     *N*     |
   +---------------------------+---------------+------+----------+----------------------+-----------------+------------+-------------+

Specifying formats
==================

Now let's look at the ``-af/--audio-format(s)`` and ``-vf/--video-format(s)``
options. They accept the *format spec* string, a query expression used to select
the desired formats (MPEG-DASH `representations
<https://dashif-documents.azurewebsites.net/Guidelines-TimingModel/master/Guidelines-TimingModel.html#representations/>`_,
to be exact), which are characterized by the itag values, qualities, used
codecs, etc.

See :ref:`reference:Format spec` for the grammar, aliases, and functions.

Conditionals and lookup attributes
----------------------------------

The itag values as format codes uniquely determine representations. For example,
providing a format spec in the form of a conditional expression as below gives
us a very specific audio stream:

.. code:: sh

   $ ytpb download -af 'itag = 140' -vf none ...

The audio and video itag values for a playing live stream can be seen in the
*Stats for nerds* popup in the browser. To show all available MPEG DASH-specific
formats, running the `yt-dlp <https://github.com/yt-dlp/yt-dlp/>`_ program is
helpful::

  $ yt-dlp --live-from-start -F <STREAM>

Here are other examples using other lookup :ref:`attributes
<reference:Attributes>` and logical conditions:

.. code:: sh

   $ ytpb download -vf 'best(format = mp4 and frame_rate = 30)' ...
   $ ytpb mpd compose -vf 'codecs = vp9 and [height = 1080 or height = 720]' ...

(Note that all commands except ``mpd compose`` require query results to be
non-ambiguous, with one representation per query. This is where the ``best()``
function can be used to limit query results.)

*Using format spec aliases*
^^^^^^^^^^^^^^^^^^^^^^^^^^^

:ref:`reference:Aliases` allow defining and use of a named condition (or
conditions) and make expressions much shorter and easier to understand. For
example, using the built-in aliases:

.. code:: sh

   $ ytpb download -vf 'best(@mp4 and @30fps)' ...

.. _Default format values:

Default option values
---------------------

The command options can be ommited and the default, built-in values listed below
will be used. As part of :ref:`Configuring`, they can be overriden.

.. code:: TOML

   [options.download]
   audio_format = "itag = 140"
   video_format = "best(@avc1 and @<=1080p and @30fps)"

   [options.capture.frame]
   video_format = "best(@30fps)"

   [options.capture.timelapse]
   video_format = "best(@30fps)"

   [options.mpd.compose]
   audio_formats = "itag = 140"
   video_formats = "@vp9 and [@1080p or @720p] and @30fps"

Specifying output name
======================

By default, merged files are saved in the current working directory with
names composed of the adjusted title, video ID and formatted input start
date::

  $ ytpb download -i PT30S/20240102T102030+00 abcdefgh123 && ls
  Stream-title_abcdefgh123_20240102T102000+00.mkv

There are several ways to change the output naming: (a) provide a full output
path or (b) provide a template output path (c) change the default corresponding
configuration value. All are without extension: the extension will be
automatically determined during the merging step.

(A) Provide a full value directly via the ``-o / --output`` option::

      $ ytpb download -o output/path ... && ls output/*
      output/path.mkv

(B) Provide a template value via the ``-o / --output`` option::

      $ ytpb download -o '{{ title|adjust }}_{{ input_start_date|isodate }}' ... && ls
      Stream-title_20240102T102000+00.mkv

    See :ref:`Templating` for templating and available variables.

(C) Change the default option value in the ``config.toml`` file:

    .. code:: TOML

       [options.download]
       output = "{{ title|adjust }}_{{ input_start_date|isodate }}"

       [options.capture.frame]
       ...

Saving segment files
====================

*Related command:* ``ytpb download``

After merging downloaded segment files to make an excerpt, the segments will be
deleted. Do you want to keep them? There are two options here.

*First*, download an excerpt and keep segment files by using the ``-S /
--keep-segments`` option::

  $ ytpb download ... -S <STREAM>
  ...
  Success! Saved to 'Stream-Title_abcdefgh123_20240102T102030+00.mkv'.
  ~ Segments are kept in 'Stream-Title_abcdefgh123_20240102T102030+00'.

The download destination can be changed via ``-s / --segments-output-dir``::

  $ ytpb download ... -S --segments-output-dir segments <STREAM>
  ...
  Success! Saved to 'Stream-Title_abcdefgh123_20240102T102030+00.mkv'.
  ~ Segments are kept in 'segments'.

Of course, the later option can be used without ``-S``, for example, to download
segments (will be deleted after merging) to another drive.

*Second*, download only segment files without merging them::

  $ ytpb download ... --no-merge <STREAM>
  ...
  Success! Segments saved to 'Stream-Title_abcdefgh123_20240102T102030+00'.

Resuming unfinished downloads
=============================

*Related command:* ``ytpb download``

If a download gets interrupted for some reason (network problems, unhandled
exceptions, aborting with ``Ctrl+C``, etc.), you can continue the unfinished
download by execution of the same command again. Each run creates a resume file
used to keep information needed for resumption, which is cleaned after
successful completion. The commands are matched based on the following input
option values: ``--interval``, ``--audio-format``, ``--video-format``, and
``--segments-output-dir``. Resuming behavior can be disabled by the
``--ignore-resume`` option to avoid using an existing resume file and start
download from scratch.

.. _Configuring:

Configuring
***********

The configuration provides the way to set up default values of the command
options and change other settings via configuration files. It's optional and the
default, built-in settings are used otherwise.

By default, the ``config.toml`` file is looked up under the ``~/.config/ytpb``
directory (or ``$XDG_CONFIG_HOME``) if you're on Unix or under platform-specific
system directories if you're on `macOS
<https://platformdirs.readthedocs.io/en/latest/api.html#platformdirs.macos.MacOS.site_data_dir>`__
or `Windows
<https://platformdirs.readthedocs.io/en/latest/api.html#platformdirs.windows.Windows.site_data_dir>`__. Also,
the ``--config`` option can be used to override the default file location.

The priority of applying settings is the following, from lowest to highest:

1. Default, built-in settings.
2. The ``config.toml`` file under the default directory.
3. A file specified via the ``--config`` option.
4. User-provided command options.

See `config.toml.example`_ for the available fields and their descriptions.

.. _config.toml.example: https://github.com/xymaxim/ytpb/blob/main/config.toml.example

Advanced usage
**************

Writing metadata tags
=====================

*Related command:* ``ytpb download``

By default, metadata tags will be added to an output excerpt file. Use the
``--no-metadata`` option to disable it.

.. rubric:: Metadata tags overview

.. autoclass:: ytpb.cli.commands.download.MetadataTagsContext
   :no-index:

The input and actual date values are expected to be different in only two cases:
(a) if the boundary (start and end) points fall in gaps or (b) the ``--cut``
option is not requested (default). In the opposite cases, after accurate cut,
they're supposed to be identical.

The dates can be represented as seconds since the epoch via the configuration
value: ``output.metadata.dates = unix``.

Running without downloading
===========================

There is a dry run mode (``-x / --dry-run``) to run without downloading. It
could be useful if you are not interested in having an output excerpt file: for
example, you want to locate the rewind interval or debug just the first steps
(by combining a dry run mode with the ``--debug`` global option).

For example, just to locate start and end moments, use::

  $ ytpb download ... --dry-run <STREAM>
  ...
  (<<) Locating start and end in the stream... done.
  Actual start: 25 Mar 2023 23:33:54 +0000, seq. 7959120
  Actual end: 25 Mar 2023 23:33:58 +0000, seq. 7959121

  ~ This is a dry run. Skip downloading and exit.

It can be combined with the ``--keep-temp`` option to keep temporary
files::

  $ ytpb download ... --dry-run --keep-temp <STREAM>

Using cache
===========

Using cache helps to avoid getting information about videos and downloading
MPEG-DASH manifest on every run. The cached files contain the basic information
and the base URLs for segments, and are stored under
``$XDG_CACHE_HOME/ytpb``. It's a default behavior. The cache expiration is
defined by the segment base URLs expiration time. The ``--no-cache`` option allows
avoiding touching cache: no reading and writing. Another option,
``--force-update-cache``, exists to trigger cache update.
