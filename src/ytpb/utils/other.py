from ytpb.types import RelativePointInStream


S_TO_MS = 1e3
US_TO_S = 1e-6


def normalize_info_string(value: str) -> str:
    return " ".join(value.split())


def resolve_relativity_in_interval(start, end):
    is_start_relative = isinstance(start, RelativePointInStream)
    is_end_relative = isinstance(end, RelativePointInStream)

    if is_start_relative and is_end_relative:
        raise ValueError("Start and end couldn't be both relative")

    try:
        if is_start_relative:
            start = end - start
        elif is_end_relative:
            end = start + end
    except TypeError:
        pass

    return start, end
