#!/usr/bin/gawk -f

# This program parses the segment timeline in a MPEG-DASH MPD file and extract
# "d" and "yt:sid" attribute values for each segment. It also shows the
# corresponding sequence numbers. Note: The MPD file should be pretty formatted:
# each element begins on a new line.
#
# The output is CSV formatted, and goes to stdout.
#
# Usage: gawk -f parse-mpd-segment-timeline.awk MPD_FILE

BEGIN {
    print "sequence,d,yt:sid"
}

function get_attribute_value(line, attribute_name) {
    match(line, attribute_name "=\"(-?[0-9]+)", matches)
    return matches[1]
}

/<SegmentList.+startNumber=/ {
    start_number = get_attribute_value($0, "startNumber")
    # Take into account the position of the first <S d=... /> element:
    sequence_offset = start_number - (FNR + 2)
    next
}

/<S[[:space:]]d=/ {
    sequence = FNR + sequence_offset
    d = get_attribute_value($0, "d")
    yt_sid = get_attribute_value($0, "yt:sid")
    printf("%s,%s,%s\n", sequence, d, yt_sid ? yt_sid : "NULL")
}
