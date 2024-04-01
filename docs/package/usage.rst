Basic usage
###########

.. contents:: Contents
   :depth: 1
   :backlinks: top
   :local:

Creating playback
*****************

.. currentmodule:: ytpb.playback

Default usage
=============

First, let's create a :class:`Playback` for a YouTube video and fetch some
essential information:

.. code-block:: python

          from ytpb.playback import Playback
	  playback = Playback(video_url := "https://www.youtube.com/watch?v=...")
	  playback.fetch_and_set_essential()

Such information includes basic video details,
:class:`ytpb.info.YouTubeVideoInfo`, and a set of streams (MPEG-DASH
representations), :class:`ytpb.types.SetOfStreams`.

By default, :class:`~ytpb.fetchers.YtpbInfoFetcher` is used to download and parse
all of the information needed to further work. Another available fetcher is
:class:`~ytpb.fetchers.YoutubeDLInfoFetcher`, which calls `yt-dlp
<https://github.com/yt-dlp/yt-dlp>`__ under the hood:

.. code-block:: python

   from ytpb.fetchers import YoutubeDLInfoFetcher
   fetcher = YoutubeDLInfoFetcher(video_url)
   playback = Playback(video_url, fetcher=fetcher)
   playback.fetch_and_set_essential()

*Note:* The default fetcher will be *perhaps* changed later to
:class:`~ytpb.fetchers.YoutubeDLInfoFetcher` as supposed to be more reliable.

:meth:`.Playback.from_url` can be used to create a playback in one step:

.. code-block:: python

   playback = Playback.from_url(video_url, fetcher=fetcher)

After, the basic information and streams are available.

Reading and writing to cache
============================

By default, cache is not touched during playback creation. With this, each
execution downloads and parses a main HTML page and MPEG-DASH MPD file, which is
not optimal. The :meth:`Playback.from_cache` can be used to create a playback
from an existing cache item (it also involves writing to cache). If an item is
not found or expired, :class:`CachedItemNotFoundError` will be raised.

.. code-block:: python

   from ytpb.exceptions import CachedItemNotFoundError
   try:
       playback = Playback.from_cache(video_url)
   except CachedItemNotFoundError:
       playback = Playback.from_url(video_url, write_to_cache=True)

Locating moments and intervals
******************************

Next, let's locate a rewind moment of :class:`.RewindMoment` by mapping a point
of :class:`ytpb.types.AbsolutePointInStream` (a date or a sequence number) to a
segment sequence number:

.. code-block:: python

   >>> from datetime import datetime
   >>> playback.locate_moment(datetime(2024, 3, 28, 8))
   RewindMoment(date=datetime.datetime(2024, 3, 28, 8, 0), sequence=93604,
   cut_at=4.660386085510254, is_end=False, falls_into_gap=False)

   >>> playback.locate_moment(93604)
   RewindMoment(date=datetime.datetime(2024, 3, 28, 4, 59, 55, 339614,
   tzinfo=datetime.timezone.utc), sequence=93604, cut_at=0, is_end=False,
   falls_into_gap=False)

While locating a moment requires an absolute point in stream, locating an
interval accepts both absolute and relative
(:class:`ytpb.types.RelativePointInStream`) points. For example, we can locate a
30-second interval starting on a specific date:

   >>> playback.locate_interval(datetime(2024, 3, 28, 8), timedelta(seconds=30))
   RewindInterval(start=RewindMoment(date=datetime.datetime(2024, 3, 28, 8, 0),
   sequence=93604, cut_at=4.660386085510254, is_end=False,
   falls_into_gap=False), end=RewindMoment(date=datetime.datetime(2024, 3, 28,
   8, 0, 30), sequence=93610, cut_at=4.387692928314209, is_end=True,
   falls_into_gap=False))

Behind the scenes, the instance of :class:`ytpb.locate.SegmentLocator` is used
to locate moments at lower level:

.. code-block:: python

   >>> from ytpb.locate import SegmentLocator
   >>> base_url = next(iter(playback.streams)).base_url
   >>> sl = SegmentLocator(base_url, session=playback.session)
   >>> sl.find_sequence_by_time(1711602000.0)
   LocateResult(sequence=93604, time_difference=4.660386085510254,
   falls_in_gap=False, track=[(97742, -20700.796554088593), (93601,
   19.838277101516724), (93604, 4.660386085510254)])

Selecting streams
*****************

The information about audio and video streams are described by
:class:`ytpb.types.AudioStream` and :class:`ytpb.types.VideoStream` types,
respectively. These types are basically aliases to
:class:`ytpb.mpd.AudioRepresentationInfo` and
:class:`ytpb.mpd.VideoRepresentationInfo`, which in turn are referenced to
MPEG-DASH `representations
<https://dashif-documents.azurewebsites.net/Guidelines-TimingModel/master/Guidelines-TimingModel.html#representation-timing>`__.

The streams can be selected in different ways: unambiguously by the ``itag``
value or ambiguously by using a predicate function or :ref:`format
spec<format-spec>`.

.. code-block:: python

   >>> from ytpb.types import AudioOrVideoStream, VideoStream

   >>> # Get the audio stream by its itag:
   >>> playback.streams.get_by_itag("247")
   VideoRepresentationInfo(itag=247)

   >>> # Filtering streams by a predicate function:
   >>> video_streams: SetOfStreams = playback.streams.filter(
   ...     lambda x: isinstance(x, VideoStream)
   ... )

   >>> # Querying streams by a format spec:
   >>> queried: list[AudioOrVideoStream] = video_streams.query(
   ...     "format eq webm and quality ge 720p"
   ... )
   [
       VideoRepresentationInfo(itag=248),
       VideoRepresentationInfo(itag=247),
   ]