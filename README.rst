.. raw:: html

	<h1 align="center">(<<) Ytpb — YouTube Live Playback</h1>

.. image:: https://github.com/xymaxim/ytpb/actions/workflows/ci.yml/badge.svg
    :target: https://github.com/xymaxim/ytpb/actions/workflows/ci.yml

.. raw:: html

	<p align="center">
	Rewind to past moments in YouTube live streams and download or play excerpts.
	</p>

*(DISCLAMER: Work in progress. Any ideas and contributions are welcome.)*

*Ytpb* is a playback for YouTube live streams written in Python. It lets you go
back to past moments beyond the limits of the web player. You can keep selected
moments by downloading excerpts or play them instantly in your video player via
MPEG-DASH.

**Features**

- Command line interface (CLI) and Python library

- Rewind live streams far beyond the limits of the web player

- *Download audio and/or video excerpts*

  - Save excerpts in different available audio and video formats
  - Precisely cut to exact moments without slow re-encoding

- *Play and rewind instantly via MPEG-DASH*

  - Compose MPEG-DASH manifests to play it in your favorite player
  - Transcode/download excerpts into local files with FFmpeg
  - Play and rewind streams reactively and interactively (mpv + `mpv-ytpb
    <https://github.com/xymaxim/mpv-ytpb>`__)

- Capture a single frame or create time-lapse images

- Makes use of yt-dlp to reliably extract information about videos

**Demo**

.. raw:: html

         <script async id="asciicast-645203" src="https://asciinema.org/a/645203.js"></script>

*A demo of ytpb usage, showing downloading a live stream excerpt.*

.. contents:: **Table of contents**
   :depth: 2
   :local:

.. section-numbering::
   :depth: 2

What is Ytpb?
*************

YouTube allows viewers to pause, rewind, and continue playing live streams if
the DVR feature is enabled by an uploader. The seek-back limit is up to 12
hours. Several ways exist to record (e.g., `FFmpeg <https://ffmpeg.org/>`_ +
`yt-dlp`_) or play (e.g., mpv + `yt-dlp`_ or `Streamlink
<https://streamlink.github.io/>`_) live streams.

What if you want to seek back in a stream (especially beyond the limit of the
player)? Some projects (see, for example, `1
<https://github.com/jmf1988/ytdash>`__, `2
<https://github.com/Kethsar/ytarchive>`__, `3
<https://github.com/rytsikau/ee.Yrewind>`__, or `4
<https://github.com/yt-dlp/yt-dlp/pull/6498>`__) try to accomplish it in
different ways: by saving an entire stream from the beginning, by defining the
relative offset from now, or by specifying timestamps. However, all solutions,
to our knowledge, don't take into account the streaming instability causing from
intermittent stutters to large gaps. It results in inaccurate rewind timings:
the desired moment could be shifted to seconds, minutes, or even `hours
<https://github.com/xymaxim/ytpb/issues/2>`__.

*Ytpb* will help you to locate the rewind interval precisely and bring the
desired excerpt back in two ways: by downloading or playing it instantly in a
player (via MPEG-DASH).

**\*\*\***

After installing, take a look at the `Quick start`_ section describing the first
try. The following section tells about the `Command line application`_. The
`Reference`_ explains some general aspects and terms. The `Contributing`_
describes how to participate.

Installation
************

*Ytpb* requires Python 3.11 or higher. Currently, *Ytpb* isn't available on
PyPI. You can install it from GitHub. The recommended way is to use `pipx
<https://pypa.github.io/pipx/>`_:

.. code:: sh

	  $ pipx install git+https://github.com/xymaxim/ytpb

Quick start
***********

The *Ytpb* Command Line Interface (CLI) provides commands to download YouTube live
stream excerpts and compose MPEG-DASH manifests to play excerpts later in
different available qualities. Here are below basic examples demonstrating usage
scenarios.

Download
========

Let's start with downloading a 30-second excerpt of audio and video by
specifying start and end dates and stream URL or ID: ::

  $ ytpb download -i 2024-01-02T10:20:00+00/PT30S <STREAM>
  $ ls
  Stream-Title_20240102T102000+00.mp4

By default, it will download an excerpt in the best `pre-defined <Default format values>`_
quality: 128k AAC audio and 1080p30 (or less) H.264 video. See the
`Specifying formats`_ subsection on how to choose the formats to download.

As for the start and end, they can be also defined in other ways (see the
`Specifying rewind interval`_ subsection). For example, it would be handy to
locate the desired moments first by previewing them and only after download a
full excerpt. To run downloading in the `preview mode <3. Preview mode>`_, use
the ``-p/--preview`` option: ::

  $ ytpb download -i 2024-01-02T10:20:00+00/.. -p <STREAM>

Compose and play
================

  Note: Requires a custom FFmpeg build (or <= 5.1.4). See issue `#4
  <https://github.com/xymaxim/ytpb/issues/4>`__.

This command takes a bit of the previous two commands. If you want to play the
excerpt without downloading it, you can compose a static MPEG-DASH manifest
(MPD) file and then play it in a player that supports DASH streams: ::

  $ ytpb mpd compose -i 2024-01-02T10:20:00+00/PT30S <STREAM>
  $ mpv Stream-Title_20240102T102000+00.mpd

By default, a manifest will contain a 128k AAC audio track and 720p (or better)
30 fps VP9 video channels.

Fetch and demux
---------------

Once you have a composed MPD, you can not only play it, but also convert
selected streams to a video file (with stream copy to avoid transcoding actual
audio and video). First, list all available streams and then select the desired
streams with the ``-map`` option: ::

  $ ffprobe <MPD>
  $ ffmpeg -i <MPD> -map 0:0 -map 0:1 -c copy out.mp4

Play
====

If you want to play and rewind live streams without downloading or composing,
take a look at `mpv-ytpb <https://github.com/xymaxim/mpv-ytpb>`__. It provides
interactive experience without leaving the mpv player.

Capture
=======

Capturing a frame (screenshot) of a moment or frames within an interval is
possible without making a video.

One frame
---------

For example, let's take a picture of the moment happening right now: ::

  $ ytpb capture frame --moment now <STREAM>
  $ ls
  Stream-Title_20231227T012954+00.jpg

Timelapse
---------

Capture not just a single frame, but a whole timelapse with one frame every
period of time: ::

  $ ytpb capture timelapse --interval 2024-01-02T10:20:00+00/PT30S --every 15S <STREAM>
  $ tree Stream-Title
  Stream-Title
  └── 20240102T102000+00
      └── ET15S
          ├── Stream-Title_20240102T102000+00_ET15S_0000.jpg
          ├── Stream-Title_20240102T102000+00_ET15S_0001.jpg
          └── Stream-Title_20240102T102000+00_ET15S_0002.jpg

Command line application
************************

This section describes using the *Ytpb* CLI: from an overview of commands, showing
their usage and configuration to advanced use cases.

Overview
========

Synopsis
--------

Commands
^^^^^^^^

.. code:: ini

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
^^^^^^^^^^^

``capture``
"""""""""""

.. code:: ini

  Usage: ytpb capture [OPTIONS] COMMAND [ARGS]...

    Capture a single or many frames.

  Options:
    --help  Show this message and exit.

  Commands:
    frame      Capture a single frame.
    timelapse  Capture time-lapse frames.

``mpd``
"""""""

.. code:: ini

  Usage: ytpb mpd [OPTIONS] COMMAND [ARGS]...

  Options:
    --help  Show this message and exit.

  Commands:
    compose  Compose an MPEG-DASH manifest.
    refresh  Refresh a composed MPEG-DASH manifest.


Getting help
------------

To show a list of available options, type ``--help`` after commands or
subcommands:

.. code:: sh

	  $ ytpb --help
	  $ ytpb download --help
	  $ ytpb mpd compose --help

Usage
=====

Specifying rewind interval
--------------------------

* ``--interval <start>/<end>``

The rewind interval can be specified with the ```-i/--interval`` option. The
formatting of input interval and its parts is closely compliant with the
ISO-8601 time interval formatting. The interval composes of start and end parts
separated with the "/" symbol.

These parts are a pair of points in a stream (absolute or relative ones) or some
special literals. The absolute points are date and times (indirect) and sequence
numbers of media segments (direct). One of interval parts can be relative to
another one by a time duration or date and time replacing components.

1. Using dates
^^^^^^^^^^^^^^

Date and time of a day
""""""""""""""""""""""

* ``--interval <date-time>/<date-time>``

where ``<date-time> = <date>"T"<time>"±"<shift>``:

``YYYY"-"MM"-"DD"T"hh":"mm":"ss"±"hh":"mm`` (I) or

``YYYYMMDD"T"hhmmss"±"hhmm`` (II).

The extended (I) and basic (II) formats are supported.

For example, an interval with two complete date and time representations:

.. code:: sh

	  # Complete representations in extended format:
	  $ ytpb download -i 2024-01-02T10:20:00+00/2024-01-02T10:20:30+00 ...

	  # Complete representations in basic format:
	  $ ytpb download -i 20240102T102000+00/20240102T102030+00 ...

The time part can be also provided with a reduced precision, with some low-order
components omitted (the date part should be always complete):

.. code:: sh

	  # Representations with reduced precision in extended format:
	  $ ytpb download -i 2024-01-02T1020+00/2024-01-02T10:20:30+00 ...

	  # Representations with reduced precision in basic format:
	  $ ytpb download -i 20240102T1020+00/20240102T102030+00 ...

**Zulu time**. Zulu time refers to the UTC time and denoted with the letter "Z"
used as a suffix instead of time shift. It's applicable for dates here and
elsewhere, even if it's not stated. For example, the following date will be
resolved to the same date as in the example above ::

    $ ytpb download -i 20240102T1020Z/20240102T102030Z ...

**Local time**. To represent a local time, the time shift part can be
omitted. For example, if you're in the UTC+02 time zone, the above example
can be represented as: ::

  $ ytpb download -i 20240102T1220/20240102T122030 ...

Time of today
"""""""""""""

* ``-i/--interval <time>±<shift>/<time>±<shift>``

To refer to a current day, the date part can be ommited: ::

  $ ytpb download -i 10:20+00/T102030+00 ...

Date and time replacing components
""""""""""""""""""""""""""""""""""

This allows to replace particular date and time components in another part of an
interval. The components to replace are referred explicitly by its one-letter
designators.

For example, the start part below: ::

  $ ytpb download -i 2023Y12M31DT1H/2024-01-02T10:20:00+00 ...

will be resolved as: ::

  $ ytpb download -i 2023-12-31T01:20:00+00/2024-01-02T10:20:00+00 ...

Note that the time part delimiter ("T") is necessary when only time components
to change are supplied: ::

  $ ytpb download -i 2024-01-02T10:20:00+00/T25M30S ...


'Now' keyword
"""""""""""""

* ``-i/--interval <start>/now``

To refer to the current moment, the end part accepts the ``now`` keyword: ::

  $ ytpb download -i 20240102T1020+00/now ...

(To be exact, it refers to the last available media segment.)

2. Using duration
^^^^^^^^^^^^^^^^^

* ``-i/--interval <start>/<duration>`` or

* ``-i/--interval <duration>/<end>``,

where ``<duration> = "P"DD"D""T""hh"H"mm"M"ss"S"``.

Sometimes it would be more convenient to specify an interval with a
duration: (a) by a start and a duration and (b) by a duration and an end.

The duration string is prepended with "P" symbol and used one-letter date and
time component designators. The highest order of date components is days ("D").

For example, here are below two examples representing the same 30-second
interval:

.. code:: sh

	  # Specified by a start and a duration.
	  $ ytpb download -i 2024-01-02T10:20:00+00/PT30S ...

	  # Specified by a duration and an end.
	  $ ytpb download -i PT30S/2024-01-02T10:20:30+00 ...

3. Preview mode
^^^^^^^^^^^^^^^

* ``--interval <start>/.. --preview``
* ``--interval <start>/<end> --preview``

If you only need to preview a moment in a stream, which you can refer later, the
``-p/--preview`` option exists. It's basically an alias for the short end
duration.

In the above, the closed intervals were used, while for the preview mode, you
can define (not necessarily, though) intervals with an open end designated with
the ".." literal: ::

  $ ytpb download -i 2024-01-02T10:20:00+00/.. -p ...

(In case of a closed interval, an end part will be ignored and you'll see a note
in the output that the preview mode is enabled.)

By default, the output preview duration varies from 10 to 10 + one segment
duration seconds. The imprecision is due to the reliance on the full-length,
uncut end segment (to reduce merging time). The minimal preview duration value
can be changed via the ``general.preview_duration`` field in the ``config.toml``
file.

4. Using sequence numbers
^^^^^^^^^^^^^^^^^^^^^^^^^

* ``-i/--interval <sequence-number>/<sequence-number>``

Besides dates, you can specify the sequence number (positive, starting from 0) of a
MPEG-DASH `media segment
<https://dashif-documents.azurewebsites.net/Guidelines-TimingModel/master/Guidelines-TimingModel.html#media-segment/>`_
to refer to a specific point in a live stream. Usually sequence numbers are
used when a segment has already been previously determined.

For example, an interval from the beginning to segment 100: ::

  $ ytpb download -i 0/100 ...

Sequence numbers can be also combined with other types: ::

  $ ytpb download -i 0/2024-01-02T10:20:30+00 ...
  $ ytpb download -i 0/PT30S ...
  $ ytpb download -i 0/now ...

Compatibility table
^^^^^^^^^^^^^^^^^^^

.. table:: **Table:** Interval parts compatibility

   +----------------------+---------------+------+----------+----------------------+-----------------+-------------+
   |                      | Date and time | Time | Duration | Replacing components | Sequence number | 'Now', '..' |
   +======================+===============+======+==========+======================+=================+=============+
   | Date and time        |       Y       |  Y   |    Y     |          Y           |        Y        |      Y      |
   +----------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | Time                 |       Y       |  Y   |    Y     |         *N*          |        Y        |      Y      |
   +----------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | Duration             |       Y       |  Y   |   *N*    |         *N*          |        Y        |     *N*     |
   +----------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | Replacing components |       Y       | *N*  |   *N*    |         *N*          |       *N*       |     *N*     |
   +----------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | Sequence number      |       Y       |  Y   |    Y     |         *N*          |        Y        |      Y      |
   +----------------------+---------------+------+----------+----------------------+-----------------+-------------+
   | 'Now', '..'          |       Y       |  Y   |   *N*    |         *N*          |        Y        |     *N*     |
   +----------------------+---------------+------+----------+----------------------+-----------------+-------------+

Specifying formats
------------------

Now let's look at the ``-af/--audio-format(s)`` and ``-vf/--video-format(s)``
options. It accepts *format spec* string, a query expression used to select the
desired formats (DASH `representations
<https://dashif-documents.azurewebsites.net/Guidelines-TimingModel/master/Guidelines-TimingModel.html#representations/>`_,
to be exact).

Representations describe different versions of the content and are
characterized by attributes, such as itags (format codes), resolutions, used
codecs, etc.

See the `Format spec`_ section for more information on format specs: their
grammar, aliases, and functions.

Examples
^^^^^^^^

Conditional expressions and lookup attributes
"""""""""""""""""""""""""""""""""""""""""""""

The ``itag`` values as format codes uniquely determine representations. For
example, providing the format spec in the form of conditional expression as
below gives us a very specific audio stream: ::

  $ ytpb download -af 'itag eq 140' ...

Or, with the following logical condition, one of two video streams: ::

  $ ytpb download -vf 'itag eq 271 or itag eq 248' ...

The specific audio and video ``itag`` values for a live stream can be seen in
the *Stats for nerds* popup in the browser. To show all available DASH-specific
formats, running the `yt-dlp <https://github.com/yt-dlp/yt-dlp/>`_ program is
helpful: ::

  $ yt-dlp --live-from-start -F <STREAM>

Here are some other examples of format specs with lookup attributes (see the
`Attributes`_ subsection) and a function: ::

  $ ytpb download -vf 'best(format eq mp4 and [frame_rate eq 60 or frame_rate eq 30])' ...
  $ ytpb mpd compose -vf 'format eq webm and height le 1080 and frame_rate eq 30' ...


Note that the ``download`` command requires the query result to be
non-ambiguous, with one representation per query.

..
   To help resolve ambiguity and to make input format specs shorter, the ``-af``
   and ``-vf`` option values are prepended with ``mime_type contains audio`` and
   ``mime_type contains video`` *guard conditions*, respectively.

Using aliases
"""""""""""""

`Aliases`_ allow to define a part or whole format spec for different cases and
make expressions much shorter. For example: ::

  $ ytpb download -vf 'best(@mp4 and @30fps)' ...

.. _Default format values:

Default values
^^^^^^^^^^^^^^

The format specs can be provided using the following ways (in order of increasing
priority): (a) using the default, built-in option values, (b) parsing
custom, user-defined configuration file, e.g. ``~/.config/ytpb/config.toml``,
and (c) via ``-af/--audio-format(s)`` and ``-vf/--video-format(s)`` options.

The default option values are as follows:

.. code:: TOML

	  [options.download]
	  audio_format = "itag eq 140"
	  video_format = "best(format eq mp4 and height le 1080 and frame_rate eq 30)"

	  [options.mpd.compose]
	  audio_formats = "itag eq 140"
	  video_formats = "best(format eq webm and height le 1080 and frame_rate eq 30)"

See the `Configuring`_ section for more information on configuring.

Specifying output name
----------------------

There are two options to change the default output naming: (a) specify a full output
path or (b) provide a template output path (both without extension). The extension
will be automatically determined during the merging stage. ::

  $ ytpb download -o '<title>_<input_start_date>_<duration>' ...
  $ ls
  $ Stream-Title_20240102T102000+00_PT30S.mp4

See the `Output name context`_ subsection for the available template variables.

Formatting titles
^^^^^^^^^^^^^^^^^

Titles can be formatted to adapt them for the output name: set maximum length,
normalize characters, change case, etc.

See the corresponding ``[output.title]`` section in ``config.toml``.

Available styles
""""""""""""""""

Two styles are available: ``original`` and ``custom``.

.. raw:: html

	 <details>
	 <summary><a>Expand for details on available styles...</a></summary>

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

.. raw:: html

	 </details>

Formatting dates
^^^^^^^^^^^^^^^^

The date formatting can be changed via the ``output.date.styles`` field in the
``config.toml`` file. The default styles (``"basic,reduced,hh"``) correspond to
the basic representation with the reduced precision. Some examples:

.. code:: TOML

	  [output.date]
	  # 2024-01-02T10:20:00+00:00
	  styles = "extended,complete,hhmm"

	  # 20240102T102000+00
	  styles = "basic,complete,hh"

	  # 20240102T1020Z
	  styles = "basic,reduced,z"

Configuring
===========

The configuration provides the way to setup default values of the command
options and change other settings via configuration files. It's optional, and
the default, built-in settings are used.

By default, the ``config.toml`` file is looked up under the ``~/.config/ytpb``
directory (or in ``$XDG_CONFIG_HOME`` if set). Also, the ``--config`` option can
be used to override the default file. The priority of applying the settings is
following: default settings < the ``config.toml`` file under the default
directory < a file provided via the ``--config`` option < commands options.

See the ``config.toml.example`` configuration file for the available fields and
descriptions.


Advanced usage
==============

Merging without cutting
-----------------------

By default, boundary segments are cutted to exact times during the merging step
to produce an excerpt. It may takes some time to re-encode boundary segments. If
you don't need exact precision, it could be practical to omit cutting via the
``--no-cut`` option. In this case the accuracy will be slightly reduced, which
will depend on the constant segment duration (or type of `live streaming latency
<https://support.google.com/youtube/answer/7444635?hl=en>`_): in worst case, the
error will be 1 (for ultra-low latency), 2 (low latency), or 5 (normal latency)
seconds.

::

   $ ytpb download ... --no-cut

Keep segment files
------------------

By default, after merging downloaded segment files to produce an excerpt, the
segments will be deleted. Do you want to keep them? There are two options here.

*First*, download only segment files without merging them (it also implies another option, ``--no-cleanup``): ::

  $ ytpb download ... --no-merge
  ...
  Success! Segments saved to /tmp/.../segments/.
  notice: No cleanup enabled, check /tmp/.../

Actually, it keeps not only segments (in ``/tmp/.../segments``) but some other
auxiliary files in the run temporary directory (``/tmp/...``). Note that, in
this case, the temporary directory shall be removed manually afterwards.

*Second*, download an excerpt and keep segment files: ::

  $ ytpb download ... --no-cleanup
  ...
  notice: No cleanup enabled, check /tmp/.../


Running without downloading
---------------------------

There is a dry run mode to run without downloading. It could be useful if you
are not interested in having output excerpt file: for example, you want to locate the
desired segments or debug just the first steps (by combining a dry run mode with
the logging options; see the subsection below).

For example, just to locate the start and end segments, use: ::

  $ ytpb download ... --dry-run
  ...
  (<<) Locating start and end in the stream... done.
  Actual start: 25 Mar 2023 23:33:54 +0000, seq. 7959120
  Actual end: 25 Mar 2023 23:33:58 +0000, seq. 7959121

  notice: This is a dry run. Skip downloading and exit.

It can be combined with the ``--no-cleanup`` option as well: ::

  $ ytpb download ... --dry-run --no-cleanup

Using cache
-----------

Using cache helps to avoid getting info about videos and downloading MPEG-DASH
manifest on every run. The cached files contain the info and the base URLs for
segments, and are stored under ``XDG_CACHE_HOME/ytpb``. It's a default
behaviour. The cache expiration is defined by the base URLs expiration time. The
``--no-cache`` option allows to avoid touching cache: no reading and
writing. Another option, ``--force-update-cache``, exists to trigger cache
update.

..
   Logging options
   ---------------

   TODO


Python package
**************

Aside from the CLI, you can use *Ytpb* as a Python package. See `DEVELOPING.rst`_.

Reference
*********

Format spec
===========

The desired DASH representations, referred to media segments of specific format,
could be selected by conditional expressions (or *format spec*). One format spec
could refer to one or more representations.

Grammar
-------

The parsing of conditional expressions is done using `pycond`_ package.

.. _pycond: https://github.com/axiros/pycond

The expressions have the following grammar:

.. code:: EBNF

    expression : condition
               | function '(' condition ')'
	       | 'none' ;

    condition : atom (('and' | 'or' | ...) (atom | condition))*
              | '[' condition ']'
	      | alias ;

    atom : attribute operator value ;

    alias : '@' alias-name ;

where ``condition`` is in the form:

.. code:: text

    [ < atom1 > < and | or | and not ... > <atom2 > ] ... .

The *operators* are text-style operators and refer to the Python's standard
`rich-comparison methods <https://docs.python.org/3/library/operator.html>`_,
such as ``eq``, ``ne``, etc.

The functions are applied after filtering by a condition. Currently the only
available function is ``best``. An example: ``best(quality ge 720p and frame_rate eq 30)``.
It applies after the querying and should wrap the whole expression.

..
   Guard conditions
   ----------------

   The following *guard conditions* are automatically applied during the run in
   addition to the ``--audio-format(s)`` and ``--video-format(s)`` options:
   ``mime_type contains audio`` and ``mime_type contains video``, respectively.

Attributes
----------

The attributes of audio and video streams (DASH representations) available for
use in conditions are listed below.

Common
^^^^^^

.. table::
   :widths: 20 20 60

   +---------------+--------+--------------------------------------------------+
   | Attribute     | Type   | Description                                      |
   +===============+========+==================================================+
   | ``itag``      | Number | Value of itag. Example: 244.                     |
   +---------------+--------+--------------------------------------------------+
   | ``mime_type`` | String | MIME type. Example: video/webm.                  |
   +---------------+--------+--------------------------------------------------+
   | ``codecs``    | String | Codec name. Example: vp9.                        |
   +---------------+--------+--------------------------------------------------+

Audio only
^^^^^^^^^^

.. table::
   :widths: 20 20 60

   +-------------------------+------------+------------------------------------+
   | Attribute               | Type       | Description                        |
   +=========================+============+====================================+
   | ``audio_sampling_rate`` | Number     | Sampling rate (in Hz). Example:    |
   |                         |            | 44100.                             |
   +-------------------------+------------+------------------------------------+

Video only
^^^^^^^^^^

.. table::
   :widths: 20 20 60

   +----------------+--------+-------------------------------------------------+
   | Attribute      | Type   | Description                                     |
   +================+========+=================================================+
   | ``width``      | Number | Width of frame. Example: 1920.                  |
   +----------------+--------+-------------------------------------------------+
   | ``height``     | Number | Height of frame. Example: 1080.                 |
   +----------------+--------+-------------------------------------------------+
   | ``frame_rate`` | Number | Frame per second (FPS). Example: 30.            |
   +----------------+--------+-------------------------------------------------+
   | ``quality``    | String | Quality string (resolution and FPS).            |
   |                |        | Example: '720p', '1080p60'.                     |
   +----------------+--------+-------------------------------------------------+

Aliases
-------

The expressions can be simplified with aliases in the form ``@alias``. There are
built-in aliases as well as custom, user-defined ones.

Built-in aliases
^^^^^^^^^^^^^^^^

Formats
"""""""

- ``mp4`` — ``format eq mp4``
- ``webm`` — ``format eq webm``

Qualities
"""""""""

- ``144p``, ``240p``, ``360p``, ``480p``, ``720p``, ``1080p``, ``1440p``,
  ``2160p`` — ``height eq 144 and frame_rate 30``, ...
- ``144p30``, ``240p30``, ``360p30``, ``480p30``, ``720p30``, ``1080p30``, ``1440p30``,
  ``2160p30`` — ``height eq 144 and frame_rate 30``, ...
- ``720p60``, ``1080p60``, ``1440p60``, ``2160p60`` —
  ``height eq 720 and frame_rate eq 60``, ...

Qualities with operators
""""""""""""""""""""""""

Available operators: ``<``, ``<=``, ``==``, ``>``, ``>=``. Height values are the
same as in the `Qualities`\: ``144p``, ``240p``, ...

For example, ``@<=1080p`` expands to ``height le 1080``. Note that the
``frame_rate`` part is not included.

Named qualities
"""""""""""""""

- ``low`` — ``height eq 144``
- ``medium`` — ``height eq 480``
- ``high`` — ``height eq 720``
- ``FHD`` — ``height eq 1080``
- ``2K`` — ``height eq 1440``
- ``4K`` — ``height eq 2160``

Frame per second
""""""""""""""""

``30fps``, ``60fps`` — ``frame_rate eq 30``, ``frame_rate eq 60``

Custom aliases
^^^^^^^^^^^^^^

The custom aliases could extend and update the built-in ones. The corresponding
field in ``config.toml`` is ``format_spec.aliases``.

Here is an example of how to define (and reuse) aliases:

.. code:: TOML

	  [format_spec]
	  aliases = {
	    "preferred-video": "best(height le 1080 and frame_rate eq 30fps)"
	    "video-for-mpd": "[@720p or @1080p] and @webm",
	  }

Locating moment in a stream
===========================

A moment in a stream is associated with a date it occurred (captured). For
dates, we rely on the ingestion dates of media segments. (A MPEG-DASH stream
consists of a chain of sequential segments with a fixed duration.) Thus, to
locate a moment with an input date, a segment containing a desired moment first
needs to be located. After, if cut is requested (as it does by default), an
offset to be cut to perfectly (as possible) match a moment can be
determined. Plus, a moment can be inside a gap caused by a frame loss. All of
these may make the difference between input and actual dates.

Output name context
===================

An output name can be specified as a template by referring to the context
variables as ``<variable>``. The available template variables are:

- ``id`` — YouTube video ID
- ``title`` — original title. Example: 'Example Title'. The title formatting can
  be changed via the ``[output.title]`` configuration section.
- ``input_start_date``, ``input_end_date`` — input start and end dates. Example:
  '20230102T030400+00'. The ISO 8601 date formatting can be changed via the
  ``output.date.style`` configuration option.
- ``actual_start_date``, ``actual_end_date`` — actual start and end dates
- ``duration`` — actual duration. Example: 'PT1M30S'.

Contributing
************

If you are willing to contribute, you are very welcome. Do you have any ideas or
suggestions? Or have you experienced a problem? Please `open
<https://github.com/xymaxim/ytpb/issues/>`_ an issue on GitHub. If you a
developer and want to help, please refer to `<CONTRIBUTING.rst>`_.

License
*******

The project is licensed under the MIT license. See `<LICENSE>`_ for details.
