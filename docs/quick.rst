Quick start
###########

The Ytpb Command Line Interface (CLI) provides commands to download YouTube live
stream excerpts and compose MPEG-DASH manifests to play excerpts later in
different available qualities. Here are below basic examples demonstrating usage
scenarios.

Download
********

Let's start with downloading a 30-second excerpt of audio and video by
specifying start and end dates and stream URL or ID: ::

  $ ytpb download -i 2024-01-02T10:20:00+00/PT30S <STREAM> && ls
  Stream-Title_20240102T102000+00.mp4

By default, it will download an excerpt in the best :ref:`pre-defined
<Default format values>` quality: 128k AAC audio and 1080p30 (or less) H.264
video. See :ref:`cli:Specifying formats` on how to choose the formats to
download.

As for the start and end, they can be also defined in other ways (see
:ref:`cli:Specifying rewind interval`). For example, it would be handy to locate
the desired moments first by previewing them and only after download a full
excerpt. To run downloading in the :ref:`preview mode <Preview mode>`, use the
``-ps / --preview-start`` or ``-ps / --preview-end`` options::

  $ ytpb download -i 2024-01-02T10:20:00+00/PT30S -ps <STREAM>

Note that the duration of an output excerpt :ref:`may be a bit longer <Why is
the duration longer>` because the merging of media segments is done without
cutting. You can use the ``-c / --cut`` option to frame-accurately cut an
excerpt, but this will require additional disk space almost equal to the size of
an excerpt.

Check also out how to `download
<https://ytpb.readthedocs.io/en/latest/cookbook.html#download-segments-with-curl>`__
media segments with an external downloader.

Compose and play
****************

If you want to play an excerpt without downloading it, you can compose a static
MPEG-DASH manifest (MPD) file: ::

  $ ytpb mpd compose -i 2024-01-02T10:20:00+00/PT1H <STREAM> && ls
  $ Stream-Title_20240102T102000+00.mpd

By default, a manifest will contain a 128k AAC audio track and 720p (or better)
30 fps VP9 video channels.

Next, you can play a composed manifest in a player that supports MPEG-DASH. For
example, with `VLC <https://www.videolan.org/vlc/>`__::

  $ vlc Stream-Title_20240102T102000+00.mpd

Or with `mpv <https://mpv.io/>`__:

  *Note:* Requires a custom mpv build. See `#4
  <https://github.com/xymaxim/ytpb/issues/4>`__ for details.

::

  $ mpv Stream-Title_20240102T102000+00.mpd

Check also out how to `convert
<https://ytpb.readthedocs.io/en/latest/cookbook.html#fetch-and-demux-segments-with-ffmpeg>`__
a manifest to a media file with FFmpeg.

Play
****

Playing and rewinding live streams are possible without downloading or
composing. Take a look at `mpv-ytpb <https://github.com/xymaxim/mpv-ytpb>`__. It
provides interactive experience with no need to leave the mpv player.

Capture
*******

Capturing a frame (screenshot) of a moment or frames within an interval is
possible without making a video.

One frame
=========

For example, let's take a picture of the moment happening right now: ::

  $ ytpb capture frame --moment now <STREAM> && ls
  Stream-Title_20231227T012954+00.jpg

Timelapse
=========

Capture not just a single frame, but a whole timelapse with one frame every
period of time: ::

  $ ytpb capture timelapse -i 2024-01-02T10:20:00+00/PT30S --every 15S <STREAM>
  $ tree Stream-Title
  Stream-Title
  └── 20240102T102000+00
      └── ET15S
          ├── Stream-Title_20240102T102000+00_ET15S_0000.jpg
          ├── Stream-Title_20240102T102000+00_ET15S_0001.jpg
          └── Stream-Title_20240102T102000+00_ET15S_0002.jpg
