#!/usr/bin/gawk -f

# This program parses the ASCII metadata header in each file in a set of segment
# binary files for selected values. The sequence number is determined from the
# metadata.
#
# The output is CSV formatted, and goes to stdout.
#
# Usage: gawk -b -f parse-segment-youtube-metadata.awk SEGMENT_FILE...
#
# The sequences in the output are presented in the input order. So, in some
# cases you would need to pass the files in naturally sorted order. Depending
# on your system, you can try, for example:
#     $ gawk -b -f ... $(ls -v SEGMENT_FILE...)
#
# Or rename the files to add padding zeros (ommit -n for actual run):
#     $ rename -n -s 's/\d+/sprintf("%03d",$1)/e' *

BEGIN {
    # The metadata uses CRLF line endings.
    RS = "\r\n"
    print "sequence,Ingestion-Walltime-Us,First-Frame-Time-Us,Stream-Duration-Us"
}

/Sequence-Number:/ {
    match($0, /Number:[[:space:]]([0-9]+)/, m)
    sequence = m[1]
    next
}
/Ingestion-Walltime-Us:/  { ingestion = $2; next }
/Stream-Duration-Us:/     { stream_duration = $2; next }
/First-Frame-Time-Us:/    { first_frame = $2; nextfile }

ENDFILE {
    printf("%s,%s,%s,%s\n", sequence, ingestion, first_frame, stream_duration)
}
