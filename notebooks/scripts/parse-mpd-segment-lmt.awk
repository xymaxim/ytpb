#!/usr/bin/gawk -f

# This program parses a MPEG-DASH MPD file and extract the "lmt" attribute value
# of <SegmentURL /> elements for all sequences (grouped by the Representation's
# ID, an itag value). Note: The MPD file should be pretty formatted: each
# element begins on a new line.
#
# The output is CSV formatted, and goes to stdout.
#
# Usage: gawk -f parse-mpd-segment-lmt.awk MPD_FILE


BEGIN {
    print "itag,sequence,lmt"
}

function get_url_variable_value(line, variable_name) {
    split(line, url_parts, /[\/"]/)
    for (idx in url_parts) {
	if (url_parts[idx] == variable_name) {
	    return url_parts[idx + 1]
	}
    }
}

/<Representation/ {
    match($0, /id="(-?[0-9]+)/, m)
    itag = m[1]
}

/<SegmentURL/ {
    sequence = get_url_variable_value($2, "sq")
    lmt = get_url_variable_value($2, "lmt")
    printf("%s,%s,%s\n", itag, sequence, lmt)
}
