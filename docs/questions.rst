Anticipated questions
#####################

Here are the answers to the most asked/anticipated questions.

   .. _Why is the duration longer:

#. **Why is the duration longer than the input interval?**

   If you don't use frame-accurate cutting via the ``-c / --cut`` option
   (default behavior), downloaded media segments are merged as is, without
   precise trimming of the boundary ones to match the interval. The maximum
   positive difference is equal to the duration of two segments and depends on
   the type of `live streaming latency
   <https://support.google.com/youtube/answer/7444635?hl=en>`_: up to 2 (for
   ultra-low latency), 4 (low), or 10 (normal) seconds.

   *But why cutting is not the default behavior?* It would be at some point, but
   currently it requires additional disc space (to already downloaded segments
   and a merged output file) almost equal to the size of an output excerpt,
   which is not practical.

   .. _Why is the duration shorter:

#. **Why is the duration shorter than the input interval?**

   Streams may contain gaps due to instability. A decrease in the duration of an
   output excerpt (by seconds, minutes or even hours) may be due to the
   following: (a) the start and/or end point hits a gap (in this case, the
   nearest available segment is taken) or (b) an excerpt contains one or many
   gaps inside, while the boundary points have not been affected by this.
