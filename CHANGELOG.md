# Changelog

Versions follow [Calendar Versioning](https://calver.org) with the `YYYY.M.D`
scheme.

## [2024.5.30]

- Make cutting non-default behavior and add the `-c / --cut` option
- Start using Jinja templates for output path templates
- Accept long option names for default option values in the config file
- Change the format of composed MPEG-DASH MPDs from compact to full (https://github.com/xymaxim/ytpb/issues/12)
- Remove `--from-playback` from `ytpb download`
- Rename `-X / --dry-run` to `-x / --dry-run`
- Rename `--segments-output-dir` to `-s / --segments-output-dir`

## [2024.5.12]

- Add Windows support ([#11](https://github.com/xymaxim/ytpb/issues/11))
- Fix not cutting issue introduced in v2024.5.3
  ([b0e4f3d](https://github.com/xymaxim/ytpb/commit/b0e4f3d10c6aad7401716f49e681bb97c2ee6d03))
- Replace all `ffprobe` calls to `av`'s function calls
- Move `ytpb.ffmpeg` to `ytpb.utils.ffmpeg`
- Add CI workflows to create test expectation files, build Windows binaries,
  publish on PyPI, and draft a GitHub release
- Run CI tests on Linux, MacOS, and Windows
- Start using dynamic versioning via `hatch-vcs`
- Convert CHANGELOG from ReST to Markdown format
- Apply patches from files in Containerfile to avoid merge conflicts

## [2024.5.3]

- Add support for resumable downloads
  ([#13](https://github.com/xymaxim/ytpb/pull/13))
- Change the segments output directory from the run temporary directory to a
  directory under the current working one
- Add `--ignore-resume`, `-S / --keep-segments`, and `--segments-output-dir`
  options
- Change the default output path to `<title>_<id>_<input_start_date>`
- Rename the `--no-cleanup` option to `--keep-temp`
- Replace the `--preview` option with `--preview-start` and `--preview-end`

## [2024.4.20]

- Fix wrong frame rate values of the video-only merged files when boundary
  segments are cut and encoded with H.264
  ([e1120bf](https://github.com/xymaxim/ytpb/commit/e1120bf4514333ff3ac5d4eac862ccb6a9d5f606))
- Write metadata tags with basic and rewind information to merged files
  ([aa7adf1](https://github.com/xymaxim/ytpb/commit/aa7adf1580e5a83c9abaa76f2836b9a0570cc4ba))
- Add the `--no-metadata` option to not write metadata tags to merged files

## [2024.4.12]

- Add the [Python
  package](https://ytpb.readthedocs.io/en/latest/package/index.html) page with
  the basic usage and API reference
- Add the `--version` CLI option to show version number
- Add `ytpb.representations.RepresentationInfo.type` property
- Add `ytpb.playback.RewindInterval.duration` and
  `ytpb.playback.RewindInterval.sequences` properties
- Accept Unix timestamps for moments and intervals
  ([b7dcbaf](https://github.com/xymaxim/ytpb/commit/b7dcbaf6eebe3f6022b7fa8eefe98f4b8af7c4cb))
- Add `ytpb.playback.RewindTreeMap` to keep rewind history
  ([91fd078](https://github.com/xymaxim/ytpb/commit/91fd078caf37f31fee167e0c2a20a38aa2badcd8))

### Breaking changes

- Rename `ytpb.mpd` to `ytpb.representations`
- Rename `ytpb.exceptions` to `ytpb.errors`
- Rename `ytpb.playback.Playback.get_downloaded_segment` to
  `ytpb.playback.Playback.get_segment`
- Rename `ytpb.representations.extract_representations_info` to
  `ytpb.representations.extract_representations`
- Remove unused `ytpb.representations.strip_manifest`

## [2024.3.27]

- Add Containerfile with instructions to build patched FFmpeg and MPV

### Breaking changes

- Change return value of `ytpb.locate.SegmentLocator.find_sequence_by_time` to
  `ytpb.locate.LocateResult`

## [2024.3.16]

- Add options to dump base (`--dump-base-urls`) and segment
  (`--dump-segment-urls`) URLs to the `download` command
  ([#10](https://github.com/xymaxim/ytpb/pull/10))
- Add the [Cookbook](https://ytpb.readthedocs.io/en/latest/cookbook.html)
  documentation page

## [2024.3.13]

- Add the config.toml.example file
- Add ability to use [custom
  aliases](https://ytpb.readthedocs.io/en/latest/reference.html#custom-aliases)
  in format specs
- Add [aliases](https://ytpb.readthedocs.io/en/latest/reference.html#itags) for
  itags (`@<itag>`) as [dynamic
  aliases](https://ytpb.readthedocs.io/en/latest/reference.html#aliases)
- Fix allowing empty representations in the CLI commands

## [2024.3.9]

- Add the CHANGELOG file and documentation page
- Change the first segment locating step: don\'t limit it to two jumps
  ([#8](https://github.com/xymaxim/ytpb/pull/8))

[Unreleased]: https://github.com/xymaxim/ytpb/compare/v2024.5.12..HEAD
[2024.5.12]: https://github.com/xymaxim/ytpb/compare/v2024.5.3..v2024.5.12
[2024.5.3]: https://github.com/xymaxim/ytpb/compare/v2024.4.20..v2024.5.3
[2024.4.20]: https://github.com/xymaxim/ytpb/compare/v2024.4.12..v2024.4.20
[2024.4.12]: https://github.com/xymaxim/ytpb/compare/v2024.3.27..v2024.4.12
[2024.3.27]: https://github.com/xymaxim/ytpb/compare/v2024.3.16..v2024.3.27
[2024.3.16]: https://github.com/xymaxim/ytpb/compare/v2024.3.13..v2024.3.16
[2024.3.13]: https://github.com/xymaxim/ytpb/compare/v2024.3.9..v2024.3.13
[2024.3.9]: https://github.com/xymaxim/ytpb/compare/v2024.3.7..v2024.3.9
