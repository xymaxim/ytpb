Changelog
#########

Versions follow `Calendar Versioning`_ with the ``YYYY.M.D`` scheme.

.. _Calendar Versioning: https://calver.org

`2024.3.27`_
************

- Add Containerfile with instructions to build patched FFmpeg and MPV

Breaking changes
================

- Change return value of ``SegmentLocator.find_sequence_by_time()`` to
  ``LocateResult``

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

.. _2024.3.27: https://github.com/xymaxim/ytpb/compare/v2024.3.16..v2024.3.27
.. _2024.3.16: https://github.com/xymaxim/ytpb/compare/v2024.3.13..v2024.3.16
.. _2024.3.13: https://github.com/xymaxim/ytpb/compare/v2024.3.9..v2024.3.13
.. _2024.3.9: https://github.com/xymaxim/ytpb/compare/v2024.3.7..v2024.3.9
