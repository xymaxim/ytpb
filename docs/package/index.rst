Python package
##############

*DISCLAIMER: The API is not stable yet and subject to change.*

Aside from the CLI, you can use ``ytpb`` as a Python package.

The main class is :class:`ytpb.playback.Playback`. It works with
:class:`~ytpb.playback.PlaybackSession`, :doc:`fetchers <api/ytpb.fetchers>`,
audio and video :doc:`streams <api/ytpb.representations>`, etc. Behind the
scene, the lower level functions from the verb-named modules are utilized, such
as :mod:`ytpb.download`, :mod:`ytpb.locate`, :mod:`ytpb.merge`.

On the level above, there are :doc:`api/ytpb.actions`. They function with a
playback to download excerpts, compose MPEG-DASH MPDs, and capture frames.

.. toctree::
    :maxdepth: 1

    usage
    api/index
