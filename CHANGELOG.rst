Changelog
#########

Versions follow `Calendar Versioning`_ with the ``YYYY.M.D`` scheme.

.. _Calendar Versioning: https://calver.org

`2024.4.12`_
************

- Add the `Python package
  <https://ytpb.readthedocs.io/en/latest/package/index.html>`__ page with the
  basic usage and API reference
- Add the ``--version`` CLI option to show version number
- Add :attr:`ytpb.representations.RepresentationInfo.type` property
- Add :attr:`ytpb.playback.RewindInterval.duration` and
  :attr:`~ytpb.playback.RewindInterval.sequences` properties
- Accept Unix timestamps for moments and intervals (`b7dcbaf
  <https://github.com/xymaxim/ytpb/commit/b7dcbaf6eebe3f6022b7fa8eefe98f4b8af7c4cb>`__)
- Add :class:`ytpb.playback.RewindTreeMap` to keep rewind history (`91fd078
  <https://github.com/xymaxim/ytpb/commit/91fd078caf37f31fee167e0c2a20a38aa2badcd8>`__)

Breaking changes
================

- Rename :mod:`ytpb.mpd` to :mod:`ytpb.representations`
- Rename :mod:`ytpb.exceptions` to :mod:`ytpb.errors`
- Rename :meth:`ytpb.playback.Playback.get_downloaded_segment` to
  :meth:`~ytpb.playback.Playback.get_segment`
- Rename :meth:`ytpb.representations.extract_representations_info` to
  :meth:`~ytpb.representations.extract_representations`
- Remove unused :meth:`ytpb.representations.strip_manifest`

`2024.3.27`_
************

- Add Containerfile with instructions to build patched FFmpeg and MPV

Breaking changes
================

- Change return value of
  :meth:`ytpb.locate.SegmentLocator.find_sequence_by_time` to
  :class:`~ytpb.locate.LocateResult`

`2024.3.16`_
************

- Add options to dump base (``--dump-base-urls``) and segment
  (``--dump-segment-urls``) URLs to the ``download`` command (`#10
  <https://github.com/xymaxim/ytpb/pull/10>`__)
- Add the `Cookbook`_ documentation page

.. _Cookbook: https://ytpb.readthedocs.io/en/latest/cookbook.html

`2024.3.13`_
************

- Add the config.toml.example file
- Add ability to use `custom aliases`_ in format specs
- Add `aliases`_ for itags (``@<itag>``) as `dynamic aliases`_
- Fix allowing empty representations in the CLI commands

.. _custom aliases: https://ytpb.readthedocs.io/en/latest/reference.html#custom-aliases
.. _aliases: https://ytpb.readthedocs.io/en/latest/reference.html#itags
.. _dynamic aliases: https://ytpb.readthedocs.io/en/latest/reference.html#aliases

`2024.3.9`_
***********

- Add the CHANGELOG file and documentation page
- Change the first segment locating step: don't limit it to two jumps (`#8
  <https://github.com/xymaxim/ytpb/pull/8>`__)

.. _2024.4.12: https://github.com/xymaxim/ytpb/compare/v2024.3.27..v2024.4.12
.. _2024.3.27: https://github.com/xymaxim/ytpb/compare/v2024.3.16..v2024.3.27
.. _2024.3.16: https://github.com/xymaxim/ytpb/compare/v2024.3.13..v2024.3.16
.. _2024.3.13: https://github.com/xymaxim/ytpb/compare/v2024.3.9..v2024.3.13
.. _2024.3.9: https://github.com/xymaxim/ytpb/compare/v2024.3.7..v2024.3.9
