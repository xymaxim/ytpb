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

For example, let's strip some emoji from a title and make it titlecase:

.. code:: jinja

   {{ '🔴 Stream title '|replace('🔴 ', '')|title }}
   "Stream Title"

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

   {{ 'Stream title | Bla bla'.split(' | ')[0]|title }}
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

#. `Custom format dates`

   While a custom :func:`ytpb.cli.templating.isodate` filter is available, dates
   can be formatted with the standard :meth:`~datetime.date.strftime()`
   function.

   Let's take a date, convert to UTC with the :func:`utc` filter and then custom
   format it:

   .. code:: jinja

      {{ (input_start_date|utc).strftime('%Y%m%d_%H%M%S') }}
      "20240102_102030"

#. `Set and reuse variables`

   Sometimes it would be useful to set new variables. You can define a variable
   with the ``{% set ... %}`` statement, and use new variables later:

   .. code:: jinja

      {% set a_title = title|adjust %}
      {% set destination = '{}/{}'.format(a_title, input_start_date.format('%Y/%m')) %}
      {{ destination ~ '/' ~ a_title ~ '_' ~ input_start_date|isoformat }}
      "Stream-title/2024/01/Stream-title_20240102T102030+00"

#. `Conditionally print variables`

   What if you `want
   <https://www.reddit.com/r/youtubedl/comments/1cydndz/conditional_output_template_with_batch_download>`__
   to include some information based on a condition? Let's try to print the 'HD'
   suffix only for HD quality representations in this example.

   Set a new variable based on the result of the ``if-else`` inline expression
   (`link
   <https://jinja.palletsprojects.com/en/3.0.x/templates/#if-expression>`__) by
   accessing an attribute of a video stream
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
   downloads. While you can use the inline condition, in
   the next example we'll see another approach based on *statements*.

#. `Use condition statements`

   The idea would be to differentiate between audio and video template strings
   with the help of the ``if`` statement (`link
   <https://jinja.palletsprojects.com/en/3.0.x/templates/#if>`__): it will make
   a template much cleaner. Here's a slightly simplified example:

   .. code:: jinja

      {% if video_stream %}
          {{ title|adjust }}/{{ video_stream.quality }}/... }}
      {% else %}
          {{ title|adjust }}/audio/... }}
      {% endif %}
      "Stream-title/1080p/..." or
      "Stream-title/auto/..."
