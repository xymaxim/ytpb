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

Demo
****

.. image:: https://asciinema.org/a/645203.svg
   :target: https://asciinema.org/a/645203
   :alt: Asciinema

*A demo of ytpb usage, showing downloading a live stream excerpt.*

Install
*******

Ytpb requires Python 3.11 or higher. The recommended way is to use `pipx
<https://pypa.github.io/pipx/>`_: ::

  $ pipx install ytpb

Further reading
***************

After installing, check out the `documentation`_. The `Why Ytpb?`_ page explains
why the project exists. For main usage scenarios, see `Quick start`_. The
`Command line application`_ page goes deeper into the usage. `Reference`_
provides some general aspects and terms. `Cookbook`_ contains some useful
examples. See `Changelog`_ for the history of releases. Have any issues,
suggestions, or want to contribute code? `Contributing`_ tells how to
participate in the project.

.. _Why Ytpb?: https://ytpb.readthedocs.io/en/latest/why.html
.. _Quick start: https://ytpb.readthedocs.io/en/latest/quick.html
.. _Command line application: https://ytpb.readthedocs.io/en/latest/cli.html
.. _Reference: https://ytpb.readthedocs.io/en/latest/reference.html
.. _Cookbook: https://ytpb.readthedocs.io/en/latest/cookbook.html
.. _Changelog: https://ytpb.readthedocs.io/en/latest/changelog.html

Similar projects
****************

- `Kethsar/ytarchive <https://github.com/Kethsar/ytarchive>`__ — archive streams from the start
- `rytsikau/ee.Yrewind <https://github.com/rytsikau/ee.Yrewind>`__ — rewind and save streams
- `yt-dlp/yt-dlp#6498 <https://github.com/yt-dlp/yt-dlp/pull/6498>`__ — brings rewind range selection to yt-dlp

License
*******

Ytpb is licensed under the MIT license. See `LICENSE`_ for details.

.. _LICENSE: https://github.com/xymaxim/ytpb/blob/main/LICENSE
