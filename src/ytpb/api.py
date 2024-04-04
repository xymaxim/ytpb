from ytpb.errors import CachedItemNotFoundError
from ytpb.fetchers import InfoFetcher, YtpbInfoFetcher
from ytpb.playback import Playback
from ytpb.utils.url import normalize_video_url


def get_playback(
    stream_url_or_id: str,
    use_cache: bool = True,
    force_update_cache: bool = False,
    fetcher: InfoFetcher | None = None,
) -> Playback:
    """Gets a playback for a live stream.

    By default, it uses cache to store essential information between runs. The
    default cache directory is ``$XDG_CACHE_HOME/ytpb`` (with a fallback to
    ``~/.cache/ytpb``).

    Args:
        stream_url_or_id: A live stream URL or ID.
        use_cache: Whether to use cache.
        force_update_cache: Whether to force update cache item.
        fetcher: An information :ref:`fetcher <ytpb-fetchers>` to use. By
          default, :class:`~ytpb.fetchers.YtpbInfoFetcher` is used.

    Returns:
        A :class:`~ytpb.playback.Playback` object.

    Raises:
        BroadcastStatusError: If broadcast status of a live stream is not
          :attr:`~ytpb.info.BroadcastStatus.ACTIVE`.
    """
    stream_url = normalize_video_url(stream_url_or_id)

    if fetcher is None:
        fetcher = YtpbInfoFetcher(stream_url)

    need_read_cache = use_cache and not force_update_cache
    if need_read_cache:
        try:
            playback = Playback.from_cache(stream_url, fetcher=fetcher)
        except CachedItemNotFoundError:
            playback = Playback.from_url(
                stream_url, fetcher=fetcher, write_to_cache=True
            )
    else:
        playback = Playback.from_url(
            stream_url, fetcher=fetcher, write_to_cache=force_update_cache
        )

    return playback
