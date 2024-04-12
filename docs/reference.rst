Reference
#########

This document explains some general aspects and terms.

*For the API reference, see* :doc:`this <package/api/index>` *document.*

.. contents:: Contents
   :depth: 2
   :backlinks: top
   :local:

.. _format-spec:

Format spec
***********

The desired MPEG-DASH representations, referred to media segments of specific
format, could be selected by conditional expressions (or *format spec*). One
format spec could refer to one or more representations.

Grammar
=======

The parsing of conditional expressions is done using `pycond`_ package.

.. _pycond: https://github.com/axiros/pycond

The expressions have the following grammar:

.. code:: ANTLR

    expression : condition
               | function '(' condition ')'
	       | 'none' ;

    condition : atom (('and' | 'or' | ...) (atom | condition))*
              | '[' condition ']'
	      | alias ;

    atom : attribute operator value ;

    alias : '@' aliasName ;

where ``condition`` is in the form:

.. code:: text

    [ < atom1 > < and | or | and not ... > <atom2 > ] ... .

The *operators* are text-style operators and refer to the Python's standard
`rich-comparison methods <https://docs.python.org/3/library/operator.html>`_,
such as ``eq``, ``ne``, etc.

The functions are applied after filtering by a condition. Currently, the only
available function is ``best``. An example: ``best(quality ge 720p and
frame_rate eq 30)``.  It applies after the querying and should wrap the whole
expression.

Attributes
==========

The attributes of audio and video streams (MPEG-DASH representations) available
for use in conditions are listed below.

Common
------

.. table::

   +---------------+--------+--------------------+------------+
   | Attribute     | Type   | Description        | Example    |
   +===============+========+====================+============+
   | ``itag``      | Number | Value of itag      | 244        |
   +---------------+--------+--------------------+------------+
   | ``mime_type`` | String | MIME type          | video/webm |
   +---------------+--------+--------------------+------------+
   | ``type``      | String | Discrete MIME type | video      |
   +---------------+--------+--------------------+------------+
   | ``format``    | String | MIME subtype       | webm       |
   +---------------+--------+--------------------+------------+
   | ``codecs``    | String | Codec name         | vp9        |
   +---------------+--------+--------------------+------------+

Audio only
----------

.. table::

   +-------------------------+------------+-----------------------+---------+
   | Attribute               | Type       | Description           | Example |
   +=========================+============+=======================+=========+
   | ``audio_sampling_rate`` | Number     | Sampling rate (in Hz) | 44100   |
   +-------------------------+------------+-----------------------+---------+

Video only
----------

.. table::

   +----------------+--------+-------------------------------------+---------------+
   | Attribute      | Type   | Description                         | Example       |
   +================+========+=====================================+===============+
   | ``width``      | Number | Width of frame                      | 1920          |
   +----------------+--------+-------------------------------------+---------------+
   | ``height``     | Number | Height of frame                     | 1080          |
   +----------------+--------+-------------------------------------+---------------+
   | ``frame_rate`` | Number | Frame per second (FPS)              | 30, 60        |
   +----------------+--------+-------------------------------------+---------------+
   | ``quality``    | String | Quality string (resolution and FPS) | 720p, 1080p60 |
   +----------------+--------+-------------------------------------+---------------+

Aliases
=======

The expressions can be simplified with aliases (``@alias``). There are built-in
aliases as well as custom, user-defined ones. The built-in aliases, in turn, can
be divided into static (explicitly defined) and dynamic (defined by a regex
pattern) ones.


Built-in aliases
----------------

*itags*
^^^^^^^

- ``(\d+)`` — ``itag eq \1``

For example, ``@140`` expands to ``itag eq 140``.

*Formats*
^^^^^^^^^

- ``mp4`` — ``format eq mp4``
- ``webm`` — ``format eq webm``

*Qualities*
^^^^^^^^^^^

- ``144p``, ``240p``, ``360p``, ``480p``, ``720p``, ``1080p``, ``1440p``,
  ``2160p`` — ``height eq 144 and frame_rate 30``, ...
- ``144p30``, ``240p30``, ``360p30``, ``480p30``, ``720p30``, ``1080p30``, ``1440p30``,
  ``2160p30`` — ``height eq 144 and frame_rate 30``, ...
- ``720p60``, ``1080p60``, ``1440p60``, ``2160p60`` —
  ``height eq 720 and frame_rate eq 60``, ...

*Qualities with operators*
^^^^^^^^^^^^^^^^^^^^^^^^^^

Available operators: ``<``, ``<=``, ``==``, ``>``, ``>=``. Height values are the
same as in `Qualities`\: ``144p``, ``240p``, ...

For example, ``@<=1080p`` expands to ``height le 1080``. Note that the
``frame_rate`` part is not included.

*Named qualities*
^^^^^^^^^^^^^^^^^

- ``low`` — ``height eq 144``
- ``medium`` — ``height eq 480``
- ``high`` — ``height eq 720``
- ``FHD`` — ``height eq 1080``
- ``2K`` — ``height eq 1440``
- ``4K`` — ``height eq 2160``

*Frame per second*
^^^^^^^^^^^^^^^^^^

``30fps``, ``60fps`` — ``frame_rate eq 30``, ``frame_rate eq 60``

Custom aliases
--------------

The custom aliases could extend and update the built-in ones. The corresponding
field in ``config.toml`` is ``general.aliases``.

Here is an example of how to define (and reuse) aliases:

.. code:: TOML

	  [general.aliases]
	  preferred-videos = "@<=1080p and @30fps"
          video-for-mpd = "best(@preferred-videos and @webm)"

Locating moment in a stream
***************************

A moment in a stream is associated with a date it occurred (captured). We rely
on the ingestion dates of media segments for dates. (A MPEG-DASH stream consists
of a chain of sequential media segments with a fixed duration.) Thus, to locate a
moment with an input date, a segment containing a desired moment first needs to
be located. After, if cut is requested (as it does by default), an offset to be
cut to perfectly (as possible) match a moment can be determined. Plus, a moment
can be inside a gap caused by a frame loss. All of these may make the difference
between input and actual dates.

Output name context
*******************

An output name can be specified as a template by referring to the context
variables as ``<variable>``. The available template variables are:

.. table::

   +-----------------------+---------------------+--------------------+-----------------------------+
   | Variable              | Description         | Example            | Corresponding configuration |
   |                       |                     |                    | section                     |
   +=======================+=====================+====================+=============================+
   | ``id``                | YouTube video ID    | abcdefgh123        | —                           |
   +-----------------------+---------------------+--------------------+-----------------------------+
   | ``title``             | Title               | Stream Title       | ``[output.title]``          |
   +-----------------------+---------------------+--------------------+-----------------------------+
   | ``input_start_date``  | Input start date    | 20240102T102030+00 | ``[output.date.style]``     |
   +-----------------------+---------------------+--------------------+-----------------------------+
   | ``input_end_date``    | Input end date      | ~                  | ~                           |
   +-----------------------+---------------------+--------------------+-----------------------------+
   | ``actual_start_date`` | Actual start date   | ~                  | ~                           |
   +-----------------------+---------------------+--------------------+-----------------------------+
   | ``actual_end_date``   | Actual end date     | ~                  | ~                           |
   +-----------------------+---------------------+--------------------+-----------------------------+
   | ``duration``          | Actual duration     | PT1M30S            | —                           |
   +-----------------------+---------------------+--------------------+-----------------------------+
