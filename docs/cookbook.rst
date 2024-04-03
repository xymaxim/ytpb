Cookbook
########

.. contents:: Contents
   :depth: 1
   :backlinks: top
   :local:

Download segments with cURL
***************************

Initially, and currently, Ytpb was not focused on long stream archiving. While
the basic retry mechanism exists for failed requests (see
:class:`~ytpb.playback.PlaybackSession`), there is no support for resumable
downloading at this time. As an alternative, we can use the `cURL`_ program to
download segments.

.. _cURL: https://curl.se/

Base URLs
=========

With the ``--dump-base-urls`` option, we can print the base URLs corresponded to
the given format specs: ::

  $ ytpb download --dump-base-urls -af none -vf @247 none STREAM
  https://BASE_URL

They can later be used to build segment URLs in your custom scripts.

Segment URLs
============

Encoding rewind range
---------------------

Another option, ``--dump-segment-urls``, allows encoding rewind information
(located segment sequence numbers) into URLs to access segments: ::

  $ ytpb download --dump-segment-urls -af @140 -vf none STREAM
  https://BASE_URL/sq/[START-END]

Such format of URLs with a `numerical range
<https://everything.curl.dev/cmdline/globbing#numerical-ranges>`__ glob is
supported by cURL.

*If needed, the glob part can be replaced with a sequence expansion:*

  ::

    $ echo "https://BASE_URL/sq/[START-END]" \
        | sed -E 's/\[(.+)-(.+)\]$/{\1..\2}/'
    https://BASE_URL/sq/{START..END}

We can download audio segments to output files named incrementally: ::

  $ ytpb download --dump-segment-urls ... | xargs curl -L -O

Using config file
-----------------

Also, we can save URLs to a file for later use: ::

  $ ytpb download --dump-segment-urls -af @140 -vf @247 STREAM \
      > segment-urls.txt | cat segment-urls.txt
  https://AUDIO_BASE_URL/sq/[START-END]
  https://VIDEO_BASE_URL/sq/[START-END]

Such file can be edited into a cURL `config file
<https://everything.curl.dev/cmdline/configfile>`__: ::

  $ cat segment-urls-config.txt
  url = AUDIO_URL
  -o audio/#1.mp4
  url = VIDEO_URL
  -o video/#1.webm

And be used to download segments with resume support (``-C -``): ::

  $ curl -L -C - -K segment-urls-config.txt

Fetch and demux segments with FFmpeg
************************************

  *Note:* Requires a custom FFmpeg build (or <= 5.1.4). See issue `#4
  <https://github.com/xymaxim/ytpb/issues/4>`__ for details.

After composing an MPEG-DASH MPD file with: ::

  $ ytpb mpd compose -i 2024-01-02T10:20:00+00/PT30S STREAM
  $ ls
  Stream-Title_20240102T102000+00.mpd

you can convert selected streams to an audio/video file.

First, list all available streams: ::

  $ ffprobe MPD
  ...
  Stream #0:0: Video: h264 (Main) (avc1 / 0x31637661), yuv420p(tv, bt709), 1280x720 [SAR 1:1 DAR 16:9], 30 fps, 30 tbr, 90k tbn (default)
    Metadata:
      id              : 136
  Stream #0:1: Video: vp9 (Profile 0), yuv420p(tv, bt709), 1280x720, 30.30 fps, 30 tbr, 1k tbn (default)
    Metadata:
      id              : 247
  Stream #0:2: Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, stereo, fltp
      (default)
    Metadata:
      id              : 140

Then, select the desired ones to be converted with the ``-map`` `option
<https://trac.ffmpeg.org/wiki/Map>`__: ::

    $ ffmpeg -i MPD -map 0:1 -map 0:2 -c copy out.mp4

Here's an equivalent for ``ffmpeg`` running in a `container
<https://github.com/xymaxim/ytpb/issues/4#issuecomment-2012443084>`__: ::

    $ podman run --rm -it -v $PWD:/root:Z ytpb \
        ffmpeg -i MPD -c copy /root/out.mp4

The ``-map`` option can be omitted and the `default behavior
<https://trac.ffmpeg.org/wiki/Map#Defaultbehavior>`__ will be applied. Use ``-c
copy`` to `avoid <https://ffmpeg.org/ffmpeg.html#Stream-copy>`__ transcoding
actual audio and video.
