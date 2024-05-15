Ytpb
####

A playback for YouTube live streams.

|PyPI| |Tests|

.. |PyPI| image:: https://img.shields.io/pypi/v/ytpb
   :target: https://pypi.org/project/ytpb
   :alt: PyPI - Version

.. |Tests| image:: https://github.com/xymaxim/ytpb/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/xymaxim/ytpb/actions/workflows/ci.yml
   :alt: Tests

`Project page`_ |sep| `Documentation`_ |sep| `Contributing`_

.. |sep| unicode:: 0xA0
   :trim:

.. _Project page: https://github.com/xymaxim/ytpb
.. _Documentation: https://ytpb.readthedocs.io/
.. _Contributing: https://ytpb.readthedocs.io/en/latest/contributing.html

*Rewind to past moments in live streams and download or play excerpts*

Ytpb is a playback for YouTube live streams written in Python. It lets you go
back to past moments beyond the limits of the web player. You can keep selected
moments by downloading excerpts or play them instantly in your video player via
MPEG-DASH.

Check out also `mpv-ytpb <https://github.com/xymaxim/mpv-ytpb>`__ to play and
rewind live streams interactively without leaving a player.

Features
********

- Command line interface (CLI) and Python library
- Rewind live streams far beyond the limits of the web player
- Download audio and/or video excerpts

  - Save excerpts in different available audio and video formats
  - Precisely cut to exact moments without slow re-encoding

- Play and rewind instantly via MPEG-DASH

  - Compose DASH manifests to play it in your favorite player
  - Transcode/download excerpts into local files with FFmpeg

- Capture a single frame or create time-lapse images
- Makes use of yt-dlp to reliably extract information about videos (optionally)

Demos
*****

- Downloading a live stream excerpt (`link <https://asciinema.org/a/653861>`__)
- Composing an MPEG-DASH MPD and transcoding it to MP4 (`link
  <https://asciinema.org/a/653865>`__)
- Creating a time-lapse of a live stream excerpt (`link
  <https://asciinema.org/a/653869>`__)

Installation
************

Ytpb requires Python 3.11 or higher and has been `tested
<https://github.com/xymaxim/ytpb/actions/workflows/ci.yml>`__ on Linux, macOS,
and Windows. Also, it needs the recent version of `FFmpeg
<https://ffmpeg.org/download.html>`__ to be installed.

Installing from PyPI
====================

When you have all required dependencies, you can install Ytpb via `pipx
<https://pypa.github.io/pipx/>`_::

  $ pipx install ytpb

To upgrade to the newer version, do::

  $ pipx upgrade ytpb

Windows binaries
================

For Windows, pre-built binaries are available: check `releases
<https://github.com/xymaxim/ytpb/releases>`__ on GitHub. Make sure to `add
<https://www.wikihow.com/Install-FFmpeg-on-Windows>`__ the ``ffmpeg.exe`` file
to your system path or place it in the folder next to the Ytpb binary. Now
you're ready to use Ytpb in Terminal: type commands, not double-click.

Further reading
***************

After installing, check out the `documentation`_. The `Why Ytpb?`_ page explains
why the project exists. For main usage scenarios, see `Quick start`_. The
`Command line application`_ page goes deeper into the usage. `Reference`_
provides some general aspects and terms. See `Questions`_ for answers to the
most anticipated questions. `Cookbook`_ contains some useful examples.  Have any
issues, suggestions, or want to contribute code? `Contributing`_ tells how to
participate in the project.

.. _Why Ytpb?: https://ytpb.readthedocs.io/en/latest/why.html
.. _Quick start: https://ytpb.readthedocs.io/en/latest/quick.html
.. _Command line application: https://ytpb.readthedocs.io/en/latest/cli.html
.. _Reference: https://ytpb.readthedocs.io/en/latest/reference.html
.. _Questions: https://ytpb.readthedocs.io/en/latest/questions.html
.. _Cookbook: https://ytpb.readthedocs.io/en/latest/cookbook.html

Similar projects
****************

- `Kethsar/ytarchive <https://github.com/Kethsar/ytarchive>`__ — archive streams from the start
- `rytsikau/ee.Yrewind <https://github.com/rytsikau/ee.Yrewind>`__ — rewind and save streams
- `yt-dlp/yt-dlp#6498 <https://github.com/yt-dlp/yt-dlp/pull/6498>`__ — brings rewind range selection to yt-dlp

License
*******

Ytpb is licensed under the MIT license. See `LICENSE`_ for details.

.. _LICENSE: https://github.com/xymaxim/ytpb/blob/main/LICENSE
