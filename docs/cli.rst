Command line application
########################

This section describes using the Ytpb command line application: from an overview
and usage of commands to configuring and advanced use cases.

.. contents:: Contents
   :depth: 2
   :backlinks: top
   :local:

Overview
********

Synopsis
========

Commands
--------

.. code:: man

  Usage: ytpb [OPTIONS] COMMAND [ARGS]...

  Global options:
    --no-config    Do not load any configuration files.
    --config PATH  Specifies a path to a configuration file.
    --debug        Enable verbose output for debugging.

  Other options:
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

*'Now' keyword*
^^^^^^^^^^^^^^^

* ``-i/--interval <start>/now``

To refer to the current moment, the end part accepts the ``now`` keyword: ::

  $ ytpb download -i 20240102T1020+00/now ...

(To be exact, it refers to the last available media segment.)

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

.. _Preview mode:

C. Preview mode
---------------

* ``--interval <start>/.. --preview``
* ``--interval <start>/<end> --preview``

If you only need to preview a moment in a stream, which you can refer to later,
the ``-p/--preview`` option exists. It's basically an alias for the short end
duration.

In the above, the closed intervals were used, while for the preview mode, you
can define (not necessarily, though) intervals with an open end designated with
the ".." literal: ::

  $ ytpb download -i 2024-01-02T10:20:00+00/.. -p ...

(In case of a closed interval, an end part will be ignored, and you'll see a
note in the output that the preview mode is enabled.)

By default, the output preview duration varies from 10 to 10 + one segment
duration seconds. The imprecision is due to the reliance on the full-length,
uncut end segment (to reduce merging time). The minimal preview duration value
can be changed via the ``general.preview_duration`` field in the ``config.toml``
file.

D. Using sequence numbers
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

Compatibility table
-------------------

.. table:: **Table:** Interval parts compatibility

   +---------------------------+---------------+------+----------+----------------------+-----------------+-------------+
   |                           | Date and time | Time | Duration | Replacing components | Sequence number | 'Now', '..' |
   |                           | / Timestamp   |      |          |                      |                 |             |
   +===========================+===============+======+==========+======================+=================+=============+
   | Date and time / Timestamp |       Y       |  Y   |    Y     |          Y           |        Y        |      Y      |
   +---------------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | Time                      |       Y       |  Y   |    Y     |         *N*          |        Y        |      Y      |
   +---------------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | Duration                  |       Y       |  Y   |   *N*    |         *N*          |        Y        |     *N*     |
   +---------------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | Replacing components      |       Y       | *N*  |   *N*    |         *N*          |       *N*       |     *N*     |
   +---------------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | Sequence number           |       Y       |  Y   |    Y     |         *N*          |        Y        |      Y      |
   +---------------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | 'Now', '..'               |       Y       |  Y   |   *N*    |         *N*          |        Y        |     *N*     |
   +---------------------------+---------------+------+----------+----------------------+-----------------+-------------+

Specifying formats
==================

Now let's look at the ``-af/--audio-format(s)`` and ``-vf/--video-format(s)``
options. It accepts *format spec* string, a query expression used to select the
desired formats (MPEG-DASH `representations
<https://dashif-documents.azurewebsites.net/Guidelines-TimingModel/master/Guidelines-TimingModel.html#representations/>`_,
to be exact).

Representations describe different versions of the content and are
characterized by attributes, such as itags (format codes), resolutions, used
codecs, etc.

See :ref:`reference:Format spec` for more information on format specs: their
grammar, aliases, and functions.

Some examples
-------------

*Conditional expressions and lookup attributes*
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``itag`` values as format codes uniquely determine representations. For
example, providing the format spec in the form of a conditional expression as
below gives us a very specific audio stream: ::

  $ ytpb download -af 'itag eq 140' ...

Or, with the following logical condition, one of two video streams: ::

  $ ytpb download -vf 'itag eq 271 or itag eq 248' ...

The specific audio and video ``itag`` values for a live stream can be seen in
the *Stats for nerds* popup in the browser. To show all available DASH-specific
formats, running the `yt-dlp <https://github.com/yt-dlp/yt-dlp/>`_ program is
helpful: ::

  $ yt-dlp --live-from-start -F <STREAM>

Here are some other examples of format specs with lookup attributes (see
:ref:`reference:Attributes`) and a function: ::

  $ ytpb download -vf 'best(format eq mp4 and [frame_rate eq 60 or frame_rate eq 30])' ...
  $ ytpb mpd compose -vf 'format eq webm and height le 1080 and frame_rate eq 30' ...


Note that the ``download`` command requires the query result to be
non-ambiguous, with one representation per query.

*Using aliases*
^^^^^^^^^^^^^^^

:ref:`reference:Aliases` allow defining a part or whole format spec for
different cases and make expressions much shorter. For example: ::

  $ ytpb download -vf 'best(@mp4 and @30fps)' ...

.. _Default format values:

Default values
--------------

The format specs can be provided using the following ways (in order of increasing
priority): (a) using the default, built-in option values, (b) parsing
custom, user-defined configuration file, e.g. ``~/.config/ytpb/config.toml``,
and (c) via ``-af/--audio-format(s)`` and ``-vf/--video-format(s)`` options.

The default option values are as follows:

.. code:: TOML

	  [options.download]
	  audio_format = "@140"
	  video_format = "best(@mp4 and <=1080p and @30fps)"

          [options.capture.frame]
	  video_format = "best(@mp4 and @30fps)"

          [options.capture.timelapse]
	  video_format = "best(@mp4 and @30fps)"

	  [options.mpd.compose]
	  audio_formats = "@140"
	  video_formats = "@webm and [@720p or @1080p] and @30fps"

See `Configuring`_ for more information on configuring.

Specifying output name
======================

There are two options to change the default output naming: (a) specify a full output
path or (b) provide a template output path (both without extension). The extension
will be automatically determined during the merging stage. ::

  $ ytpb download -o '<title>_<input_start_date>_<duration>' ...
  $ ls
  $ Stream-Title_20240102T102000+00_PT30S.mp4

See :ref:`reference:Output name context` for the available template variables.

Formatting titles
-----------------

Titles can be formatted to adapt them for the output name: set maximum length,
normalize characters, change case, etc.

See the corresponding ``[output.title]`` section in ``config.toml``.

*Available styles*
^^^^^^^^^^^^^^^^^^

Two styles are available: ``original`` and ``custom``.

.. collapse:: Click here for details on available styles...

   Let's consider the following titles as original:

   1. FRANCE 24 – EN DIRECT – Info et actualités internationales en continu 24h/24
   2. 【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG

   .. raw:: html

            <h6><code>original</code></h6>

   An original title with unallowed symbols replaced. Allows Unicode characters.

   .. code:: TOML

             [output.title]
             style = "original"

   1. ``FRANCE 24 – EN DIRECT – Info et actualités internationales en continu 24h-24``
   2. ``【LIVE】新宿駅前の様子 Shinjuku, Tokyo JAPAN【ライブカメラ】 | TBS NEWS DIG``

   .. raw:: html

      <h6><code>custom</code></h6>

   Format an original title with settings from the ``[output.title.custom]``
   section: reduce length, convert to ASCII-only characters, make
   POSIX-compatible, make lowercase.

   *Shortening titles*. For example, to shorten the title length (by truncating at
   word boundaries) and keep Unicode characters, the following settings:

   .. code:: TOML

             [output.title]
             style = "custom"

             [output.title.custom]
             max_length = 30
             characters = "unicode"

   will produce:

   1. ``FRANCE 24 — EN DIRECT — Info et actualités``
   2. ``【LIVE】新宿駅前の様子 Shinjuku, Tokyo``

   *Converting to ASCII-only*. To convert all characters to ASCII-only, the following:

   .. code:: TOML

             [output.title.custom]
             characters = "ascii"

   will produce:

   1. ``FRANCE 24 -- EN DIRECT -- Info et actualites internationales en continu 24h-24``
   2. ``[(LIVE)] Xin Su Yi Qian noYang Zi Shinjuku, Tokyo JAPAN[(raibukamera)] | TBS NEWS DIG``

   *Making POSIX-compliant*. To make the output filename POSIX-compliant and
   lowercase it, the following:

   .. code:: TOML

             [output.title.custom]
             max_length = 50
             separator = "-"
             characters = "posix"
             lowercase = true

   will produce:

   1. ``france-24--en-direct--info-et-actualites-internationales-en-continu-24h-24``
   2. ``live-xin-su-yi-qian-noyang-zi-shinjuku-tokyo-japan-raibukamera-tbs-news-dig``

Formatting dates
----------------

The date formatting can be changed via the ``output.date.styles`` field in the
``config.toml`` file. The default set of styles (``"basic,reduced,hh"``)
corresponds to the basic representation with the reduced precision. Some other
examples:

.. code:: TOML

	  [output.date]
	  # 2024-01-02T10:20:00+00:00
	  styles = "extended,complete,hhmm"

	  # 20240102T102000+00
	  styles = "basic,complete,hh"

	  # 20240102T1020Z
          # 20240102T1220+02
	  styles = "basic,reduced,z"

Configuring
***********

The configuration provides the way to set up default values of the command
options and change other settings via configuration files. It's optional, and
the default, built-in settings are used.

By default, the ``config.toml`` file is looked up under the ``~/.config/ytpb``
directory (or in ``$XDG_CONFIG_HOME`` if set). Also, the ``--config`` option can
be used to override the default file location. The priority of applying the
settings is following: default settings < the ``config.toml`` file under the
default directory < a file provided via the ``--config`` option < commands
options.

See `config.toml.example`_ for the available fields and their descriptions.

.. _config.toml.example: https://github.com/xymaxim/ytpb/blob/main/config.toml.example

Advanced usage
**************

Merging without cutting
=======================

By default, boundary segments are cutted to exact times during the merging step
to produce an excerpt. It may take some time to re-encode boundary segments. If
you don't need exact precision, it could be practical to omit cutting via the
``--no-cut`` option. In this case the accuracy will be slightly reduced, which
will depend on the constant segment duration (or type of `live-streaming latency
<https://support.google.com/youtube/answer/7444635?hl=en>`_): in the worst case,
the error will be 1 (for ultra-low latency), 2 (low latency), or 5 (normal
latency) seconds.

::

   $ ytpb download ... --no-cut

Keep segment files
==================

By default, after merging downloaded segment files to produce an excerpt, the
segments will be deleted. Do you want to keep them? There are two options here.

*First*, download only segment files without merging them (it also implies
another option, ``--no-cleanup``): ::

  $ ytpb download ... --no-merge
  ...
  Success! Segments saved to /tmp/.../segments/.
  notice: No cleanup enabled, check /tmp/.../

Actually, it keeps not only segments (in ``/tmp/.../segments``) but some other
auxiliary files in the run temporary directory (``/tmp/...``). Note that, in
this case, the temporary directory shall be removed manually afterward.

*Second*, download an excerpt and keep segment files: ::

  $ ytpb download ... --no-cleanup
  ...
  notice: No cleanup enabled, check /tmp/.../


Running without downloading
===========================

There is a dry run mode to run without downloading. It could be useful if you
are not interested in having an output excerpt file: for example, you want to
locate the desired segments or debug just the first steps (by combining a dry
run mode with the logging options; see the subsection below).

For example, just to locate start and end segments, use: ::

  $ ytpb download ... --dry-run
  ...
  (<<) Locating start and end in the stream... done.
  Actual start: 25 Mar 2023 23:33:54 +0000, seq. 7959120
  Actual end: 25 Mar 2023 23:33:58 +0000, seq. 7959121

  notice: This is a dry run. Skip downloading and exit.

It can be combined with the ``--no-cleanup`` option as well: ::

  $ ytpb download ... --dry-run --no-cleanup

Using cache
===========

Using cache helps to avoid getting info about videos and downloading MPEG-DASH
manifest on every run. The cached files contain the info and the base URLs for
segments, and are stored under ``XDG_CACHE_HOME/ytpb``. It's a default
behavior. The cache expiration is defined by the base URLs expiration time. The
``--no-cache`` option allows avoiding touching cache: no reading and
writing. Another option, ``--force-update-cache``, exists to trigger cache
update.
