Python package
##############

*DISCLAIMER: The API is not stable yet and subject to change.*

Aside from the CLI, you can use ``ytpb`` as a Python package. The main class is
:class:`ytpb.playback.Playback`. It works with
:class:`ytpb.playback.PlaybackSession`, fetchers, audio and video streams,
etc. Behind the scene, the lower level functions from the verb-named modules are
utilized, such as :mod:`ytpb.download`, :mod:`ytpb.locate`, :mod:`ytpb.merge`,
etc.

.. toctree::
    :maxdepth: 1

    usage
    api/index
