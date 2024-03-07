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

  $ ytpb download -i 2024-01-02T10:20:00+00/PT30S <STREAM>
  $ ls
  Stream-Title_20240102T102000+00.mp4

By default, it will download an excerpt in the best :ref:`pre-defined
<Default format values>` quality: 128k AAC audio and 1080p30 (or less) H.264
video. See :ref:`cli:Specifying formats` on how to choose the formats to
download.

As for the start and end, they can be also defined in other ways (see
:ref:`cli:Specifying rewind interval`). For example, it would be handy to locate
the desired moments first by previewing them and only after download a full
excerpt. To run downloading in the :ref:`preview mode <Preview mode>`, use the
``-p/--preview`` option: ::

  $ ytpb download -i 2024-01-02T10:20:00+00/.. -p <STREAM>

Compose and play
****************

  Note: Requires a custom FFmpeg build (or <= 5.1.4). See issue `#4
  <https://github.com/xymaxim/ytpb/issues/4>`__.

If you want to play an excerpt without downloading it, you can compose a static
MPEG-DASH manifest (MPD) file and then play it in a player that supports DASH
streams: ::

  $ ytpb mpd compose -i 2024-01-02T10:20:00+00/PT30S <STREAM>
  $ mpv Stream-Title_20240102T102000+00.mpd

By default, a manifest will contain a 128k AAC audio track and 720p (or better)
30 fps VP9 video channels.

Fetch and demux
===============

Once you have a composed MPD, you can not only play it, but also convert
selected streams to a video file. First, list all available streams and then
select the desired streams to convert with the ``-map`` option (use ``-c copy``
to avoid transcoding actual audio and video): ::

  $ ffprobe <MPD>
  $ ffmpeg -i <MPD> -map 0:0 -map 0:1 -c copy out.mp4

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

  $ ytpb capture frame --moment now <STREAM>
  $ ls
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
