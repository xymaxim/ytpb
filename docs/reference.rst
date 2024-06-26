.. py:currentmodule:: ytpb

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

.. contents::
   :depth: 1
   :backlinks: none
   :local:

The desired MPEG-DASH representations, referred to media segments of specific
format, could be selected by conditional expressions (or *format spec*). One
format spec could refer to one or more representations.

Grammar
=======

Format specs have the following top-level grammar (defined in `Lark`_ syntax):

.. code-block::

     query: expression

     ?expression: ALL -> all
                | NONE -> none
                | conditional_expression
                | fallback_expression
                | piped_expression
                | "(" expression ")" -> group

     conditional_expression: condition
     piped_expression: expression ("|" (expression | function))+ -> pipe
     fallback_expression: expression ("?:" expression)+

     condition: CONDITION_STRING

     function.2: FUNCTION_NAME

     ALL: "all"
     NONE: "none" | "''" | "\"\""
     CONDITION_STRING: /[@a-z0-9_\.,<>=!:\[\]'"\s]+/i
     FUNCTION_NAME: /[a-z0-9_\-]+/i

The parsing of conditional expressions is done using the `pycond`_ package.

.. _Lark: https://lark-parser.readthedocs.io/en/stable/
.. _pycond: https://github.com/axiros/pycond

.. glossary::

   Queries
     Used to filter audio and/or video streams (MPEG-DASH representations).

   Expressions
     The simplest expressions are conditional ones. They can be stacked, along
     with query functions, with the pipe operator (``|``) to form a piped
     expression. To group expressions, use parantheses (``()``).

   Conditions
     Composed of atomic conditions (atoms) and can be placed in a row with
     combine boolean operators (``and``, ``or``,...). Atoms, in turn, lookup and compare
     attributes (MPEG-DASH representation :ref:`attributes <Lookup attributes>`)
     with conditional operators. Conditions can be structured by bracketing to
     create complex queries, e.g., ``codecs eq vp9 and [height eq 720 or height
     eq 1080]``.

   Operators
     Text or symbolic operators that refer to the Python's standard
     `rich-comparison methods
     <https://docs.python.org/3/library/operator.html>`_.

   Functions
     Applies to the result of a query and therefore should be placed after a
     query expression. The available functions are ``best`` and ``worst``. For
     example, ``quality >= 720p | best``.

   Fallback expressions
     Several expressions can be placed in a row with the help of the ``?:``
     operator. Each expression is qualified separately and the first (the most
     left) truthy expression is used. It can be useful to provide fallback
     expression(s) in addition to the main one. For example, ``(quality >= 720p
     and format = mp4 ?: quality >= 720p and format = webm) | best``.

.. _Lookup attributes:

Attributes
==========

The attributes of audio and video streams (MPEG-DASH representations) available
for use in conditions are listed below.

Common
------

.. autoclass:: ytpb.representations.RepresentationInfo
   :no-index:

Audio only
-----------

.. autoclass:: ytpb.representations.AudioRepresentationInfo
   :no-index:
   :exclude-members: itag, mime_type, codecs, base_url

Video only
----------

.. autoclass:: ytpb.representations.VideoRepresentationInfo
   :no-index:
   :exclude-members: itag, mime_type, codecs, base_url

Aliases
=======

The format spec expressions can be simplified with aliases (``@alias``). There
are built-in aliases as well as custom, user-defined ones. Also, they can be
formally divided into (a) those that are explicitly defined and (b) pattern
aliases, those that are described by the Python `regular expressions
<https://docs.python.org/3/library/re.html>`__.

Built-in aliases
----------------

*itags*
^^^^^^^

- ``(\d+)\b`` : ``itag eq \1``
    Example: ``@140`` — ``itag = 140``

*Formats*
^^^^^^^^^

- ``mp4`` — ``format = mp4``
- ``webm`` — ``format = webm``

*Codecs*
^^^^^^^^

- ``mp4a`` — ``codecs contains mp4a``
- ``avc1`` — ``codecs contains avc1``
- ``vp9`` — ``codecs = vp9``


*Qualities*
^^^^^^^^^^^

- ``(\d+)p\b`` : ``height = \1``
   Example: ``@720p`` — ``height = 720p``
- ``(\d+)p(\d+)\b`` : ``[height = \1 and frame_rate \2]``
   Example: ``@1080p60`` — ``[heigth = 1080p and frame_rate = 60]``

*Qualities with operators*
^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``([<>=]=?)(\d+)p\b`` : ``height \1 \2``
   Example: ``@>=720p`` — ``height >= 720p``

Available operators: ``<``, ``>``, ``=``, ``<=``, ``>=``. Note that the
``frame_rate`` part is not included.

*Frame rate*
^^^^^^^^^^^^

- ``(\d+)fps\b`` : ``frame_rate = \1``
    Example: ``@30fps`` — ``frame_rate = 30``

*Named qualities*
^^^^^^^^^^^^^^^^^

- ``low`` — ``height = 144``
- ``medium`` — ``height = 480``
- ``high`` — ``height = 720``
- ``FHD`` — ``height = 1080``
- ``2K`` — ``height = 1440``
- ``4K`` — ``height = 2160``

Custom aliases
--------------

The custom aliases could extend and update the built-in ones. The corresponding
configuration field is ``general.aliases``.

Here is an example of how to define aliases in ``config.toml``:

.. code:: TOML

   [general.aliases]
   fast = "codecs = vp9 and height = 480"

Aliases can be nested, allowing them to be reused:

.. code:: TOML

   preferred = "@<=1080p and @30fps"
   for-mpd = "@vp9 and @preferred | best"

To define pattern aliases, use single quotes to surround alias names and values:

.. code:: TOML

   '(\d+)x(\d+)\b' = 'width eq \1 and height eq \2'

Practical examples
==================

Defining fallback conditions
----------------------------

Let's assume that we, as users, prefer videos based on the following
criteria: (a) MP4 format in 1080p or 720p quality and 30 fps, ``@mp4 and [@720p
or 1080p] and @30fps | best``, and (b) if the condition is not met, try another,
broader one: ``@mp4 and @<=1080p | best``.

To demonstrate the exampe, we'll look at two live streams named Stream I and
Stream II and outputs from the ``yt-dlp --live-from-start -F`` command
(highlighted is a representation that satisfies the first criterion).

For Stream I, the first format spec will match ``itag = 136``, the best available
stream, since there are no streams in higher quality:

.. code-block::
   :caption: Stream I
   :emphasize-lines: 5

   ID  EXT  RESOLUTION FPS │   TBR PROTO  │ VCODEC        VBR ACODEC     ABR ASR MORE INFO
   ...
   135 mp4  854x480     30 │ 1350k dashG  │ avc1.4d401f 1350k video only         DASH video, mp4_dash
   244 webm 854x480     30 │  528k dashG  │ vp9          528k video only         DASH video, webm_dash
   136 mp4  1280x720    30 │ 2684k dashG  │ avc1.4d401f 2684k video only         DASH video, mp4_dash
   247 webm 1280x720    30 │  733k dashG  │ vp9          733k video only         DASH video, webm_dash

For Stream II, the first condition will not be fulfilled because there are no
such streams of 30 fps in MP4 format:

.. code-block::
   :caption: Stream II

   ...
   135 mp4  854x480     30 │ 1350k dashG │ avc1.4d401f 1350k video only          DASH video, mp4_dash
   244 webm 854x480     30 │  528k dashG │ vp9          528k video only          DASH video, webm_dash
   298 mp4  1280x720    60 │ 4018k dashG │ avc1.4d4020 4018k video only          DASH video, mp4_dash
   302 webm 1280x720    60 │ 1276k dashG │ vp9         1276k video only          DASH video, webm_dash
   299 mp4  1920x1080   60 │ 6686k dashG │ avc1.64002a 6686k video only          DASH video, mp4_dash
   303 webm 1920x1080   60 │ 4816k dashG │ vp9         4816k video only          DASH video, webm_dash
   308 webm 2560x1440   60 │ 9016k dashG │ vp9         9016k video only          DASH video, webm_dash

To match the second condition (``itag = 299``), we can make an addition to our
first query by combining two conditions with the fallback operator:

.. code-block::

   (@mp4 and [@720p or @1080p] and @30fps ?: @mp4 and @<=1080p) | best

This allows us to have one query expression that works for different cases.

.. _Default format values:

Default option values
=====================

The choice of the default ``--audio-format(s)`` and ``--video-format(s)`` option
values depends on user's preferences (formats, qualities, etc.), needs (fast
skimming or high-quality archiving), and formats availability. Here below are
below the default, built-in values. As part of :ref:`cli:Configuring`, they can
be overriden.

*Please note that these values don't correspond to the best quality videos and
are focused on a smooth experience balancing between video quality and download
speed.*

.. code:: TOML

   [options.download]
   audio_format = "itag = 140"
   video_format = """\
   (@avc1 and [@720p or @1080p] and @30fps ?: \
    @avc1 and @<=1080p ?: \
    @<=1080p) | best"""

   [options.capture.frame]
   video_format = "(@>=1080p and @30fps ?: all) | best"

   [options.capture.timelapse]
   video_format = "(@>=1080p and @30fps ?: all) | best"

   [options.mpd.compose]
   audio_formats = "itag = 140"
   video_formats = """\
   @vp9 and [@720p or @1080p] and @30fps ?: \
   @vp9 and [@720p or @1080p]"""

.. _Templating:

Templating and context variables
********************************

.. contents::
   :depth: 1
   :backlinks: none
   :local:

.. currentmodule:: ytpb.cli.templating

Output paths can be provided as templates. Our choice of templates settled on
`Jinja <https://jinja.palletsprojects.com/>`__. It's versatile, expressive and
allow users to produce very flexible outputs.

Quick intro
===========

Jinja has its own detailed `reference
<https://jinja.palletsprojects.com/en/latest/templates/>`__ for template
designers. For our needs we only need the basic features: to output variables,
format values, and run some simple expressions.

Using variables
---------------

The simplest form to display template variables (`link
<https://jinja.palletsprojects.com/en/latest/templates/#variables>`__) is to
place them in between the ``{{ }}`` expression delimiters:

.. code:: jinja

   {{ variable }}
   "A variable's value"

Mutliple variables can be formatted together by using: (a) several
expressions, (b) the standard :meth:`str.format` method or the related filter
(`link
<https://jinja.palletsprojects.com/en/3.1.x/templates/#jinja-filters.format>`__),
or (c) the ``~`` (tilde) operator.

.. code:: jinja

   {{ A }} and {{ B }}
   {{ '{} and {}'.format(A, B) }}
   {{ A ~ 'and' ~ B  }}
   "Alpha and Beta"

Each command has its own context: a set of variables, such as YouTube video ID,
title, start and end dates, etc. See :ref:`Context variables` for the list of
all available variables.

Processing with filters
-----------------------

In most cases, you will need to format values of variables. With *filters*
(`link <https://jinja.palletsprojects.com/en/latest/templates/#filters>`__) you
can process them and change their string representation.

For example, let's change the case of a title and strip whitespace:

.. code:: jinja

   {{ 'Stream title'|title|replace(' ', '') }}
   "StreamTitle"

As you can see, filters can be combined and called without brackets (if there
are no required arguments or no need to redefine default values).

Jinja comes with a lot of useful `built-in filters
<https://jinja.palletsprojects.com/en/latest/templates/#list-of-builtin-filters>`__. We
also provide our :ref:`custom filters<Custom filters>`.

Running expressions
-------------------

*Expressions* (`link
<https://jinja.palletsprojects.com/en/latest/templates/#expressions>`__) let you
work with templates very similar to regular Python. Actually, you're already
familiar with expressions: literals are their simplest form and the pipe (``|``)
symbol is an operator to apply a filter.

For example, let's keep only some part of a title with Python methods and make
it titlecase again with a filter:

.. code:: jinja

   {{ 'Stream title - Bla bla'.split(' - ')[0]|title }}
   "Stream Title"

.. _Custom filters:

Custom filters
==============

In addition to Jinja `built-in filters
<https://jinja.palletsprojects.com/en/3.0.x/templates/#builtin-filters>`__, here
is the list of our custom available filters, which can be applied on variables
of the listed types:

- `str`: :func:`.adjust`
- `datetime.datetime`: :func:`.isodate`, :func:`.utc`, :func:`.timestamp`
- `datetime.timedelta`: :func:`.duration`

.. centered:: \* \* \*

.. autofunction:: adjust
.. autofunction:: isodate
.. autofunction:: utc
.. autofunction:: timestamp
.. autofunction:: duration

.. _Context variables:

Context variables
=================

Here are the available variables that you can use in your templates. The
variables are defined by contexts of the (sub-)commands:

  :ref:`download <download-context>`, :ref:`capture frame <capture-frame-context>`,
  :ref:`capture timelapse <capture-timelapse-context>`, :ref:`mpd compose <mpd-compose-context>`

Base contexts
-------------

.. autoclass:: ytpb.cli.templating.MinimalOutputPathContext
.. autoclass:: ytpb.cli.templating.AudioStreamOutputPathContext
.. autoclass:: ytpb.cli.templating.VideoStreamOutputPathContext
.. autoclass:: ytpb.cli.templating.IntervalOutputPathContext

Command contexts
----------------

.. _download-context:

``ytpb download``
^^^^^^^^^^^^^^^^^

.. autoclass:: ytpb.cli.commands.download.DownloadOutputPathContext

.. _capture-frame-context:

``ytpb capture frame``
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: ytpb.cli.commands.capture.CaptureOutputPathContext

.. _capture-timelapse-context:

``ytpb capture timelapse``
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: ytpb.cli.commands.capture.TimelapseOutputPathContext

.. _mpd-compose-context:

``ytpb mpd compose``
^^^^^^^^^^^^^^^^^^^^

.. autoclass:: ytpb.cli.commands.mpd.MPDOutputPathContext

Practical examples
==================

Let's practice with some showcase examples.

Sanitize file paths
-------------------

The default approach for working with output file paths is to render portable
paths, e.g. with multi-platform support. The following steps can be highlighted:

- **Prepare variables**: Replace unsafe delimiter characters (``/``, ``|``) with
  ``-``, sanitize some variables (``title``, ``author``, etc.)
- **Render output**: Render a template string to an output file path
- **Post-process**: Sanitize a rendered file path

The first and last steps are carried out automatically.

Let's imagine that we have a live stream with the following title:

.. code-block:: jinja
   :caption: Original title

   "Panorama Pointe Percée | 24/7 en direct !"

As you see, it contains a letter with diactrical mark, but also some unsafe
characters such as ``|`` (not portable) and ``/`` (used to separate
directories), so we strip the latter ones by default:

.. code-block:: jinja
   :caption: Sanitized title

   {{ title }}
   "Panorama Pointe Percée - 24-7 en direct !"

Now this variable can be effortlessly used in output file paths, but let's
adjust it more. For example, get rid of whitespaces (to use a path without
quoting) and accept only POSIX-compliant filename characters with the
:func:`~ytpb.cli.templating.adjust` filter:

.. code:: jinja

   {{ title|adjust }}
   "Panorama-Pointe-Percee-24-7-en-direct"

And with another separator between words:

.. code:: jinja

   {{ title|adjust(separator='_') }}
   "Panorama_Pointe_Percee_24_7_en_direct"

Of course, ASCII characters can be kept with:

.. code:: jinja

   {{ title|adjust('ascii', separator='-') }}
   "Panorama_Pointe_Percee_24_7_en_direct_!"

As for an output path, any non-portable characters will be automatically
removed, as well as ending separators:

.. code-block:: jinja
   :caption: Sanitized file path

   {{ title|adjust('ascii', separator='-')}}_?
   "Panorama_Pointe_Percee_24_7_en_direct_!"


Custom format dates
-------------------

While the custom :func:`~ytpb.cli.templating.isodate` filter is available, dates
can be formatted with the standard :meth:`~datetime.date.strftime()` function.

Let's take a date, convert to UTC with the :func:`utc` filter and then custom
format it:

.. code:: jinja

   {{ (input_start_date|utc).strftime('%Y%m%d_%H%M%S') }}
   "20240102_102030"

Set and reuse variables
-----------------------

Sometimes it would be useful to set new variables. You can define a variable
with the ``{% set ... %}`` statement, and use new variables later:

.. code:: jinja

   {% set a_title = title|adjust %}
   {% set destination = '{}/{}'.format(a_title, input_start_date.format('%Y/%m')) %}
   {{ destination ~ '/' ~ a_title ~ '_' ~ input_start_date|isoformat }}
   "Stream-title/2024/01/Stream-title_20240102T102030+00"

Conditionally print variables
-----------------------------

What if you `want
<https://www.reddit.com/r/youtubedl/comments/1cydndz/conditional_output_template_with_batch_download>`__
to include some information based on a condition? Let's try to print the 'HD'
suffix only for HD quality representations in this example.

Set a new variable based on the result of the ``if-else`` inline expression
(`link <https://jinja.palletsprojects.com/en/3.0.x/templates/#if-expression>`__)
by accessing an attribute of a video stream
(:class:`~ytpb.representations.VideoRepresentationInfo`) object:

.. code:: jinja

   {% set hd_suffix = 'HD' if video_stream.height >= 720 else None %}

Output string can be composed in several ways:

.. code:: jinja

   {# Using multiple expressions and string concatenation #}
   {{ title|adjust }}_{{ video_stream.quality }}{{ '_' ~ hd_suffix if hd_suffix }}

   {# Using *string* list elements joined by the delimiter #}
   {{ [title|adjust, video_stream.quality, hd_suffix]|select('string')|join('_') }}

And rendered outputs will be:

.. code:: jinja

   {# Some representation #}
   "Stream-title_480p"

   {# Another representation #}
   "Stream-title_1080p60_HD"

However, as you may have noticed, the example will fail for audio-only
downloads. While you can use the inline condition, in the next example we'll see
another approach based on *statements*.

Use condition statements
------------------------

The idea would be to differentiate between audio and video template strings with
the help of the ``if`` statement (`link
<https://jinja.palletsprojects.com/en/3.0.x/templates/#if>`__): it will make a
template much cleaner. Here's a slightly simplified example:

.. code:: jinja

   {% if video_stream %}
       {{ title|adjust }}/{{ video_stream.quality }}/... }}
   {% else %}
       {{ title|adjust }}/audio/... }}
   {% endif %}
   "Stream-title/1080p/..." or
   "Stream-title/auto/..."
