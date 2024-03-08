Why Ytpb?
#########

YouTube allows viewers to pause, rewind, and continue playing live streams if
the DVR feature is enabled by an uploader. The seek-back limit is up to 12
hours. Several ways exist to record (e.g., `FFmpeg <https://ffmpeg.org/>`_ +
`yt-dlp`_) or play (e.g., `mpv <https://mpv.io/>`_ + `yt-dlp`_ or `Streamlink
<https://streamlink.github.io/>`_) live streams.

.. _yt-dlp: https://github.com/yt-dlp/yt-dlp

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

Ytpb will help you to locate the rewind interval precisely and bring the
desired excerpt back in two ways: by downloading or playing it instantly in a
player (via MPEG-DASH).
