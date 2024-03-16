Cookbook
########

Download segments with cURL
***************************

Initially, and currently, Ytpb was not focused on stream archiving. While the
basic retry mechanism exists for failed requests, there is no support for
resumable downloading at this time. As an alternative, we can use the `cURL`_
program to download segments.

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
