# Subtitle Formats Reference

## Supported Formats

The skill expects subtitle files in `SRT` or `VTT` format.

## SRT Example

```text
1
00:00:01,000 --> 00:00:04,000
Hello and welcome.

2
00:00:04,500 --> 00:00:08,000
Today we will discuss the main idea.
```

## VTT Example

```text
WEBVTT

00:00:01.000 --> 00:00:04.000
Hello and welcome.

00:00:04.500 --> 00:00:08.000
Today we will discuss the main idea.
```

## Parsing Notes

- Convert timestamps to seconds before aligning subtitle text with frames.
- For `SRT`, use `,` as the millisecond separator.
- For `VTT`, use `.` as the millisecond separator.
- Merge very short adjacent subtitle segments if a single sentence is split unnaturally.
- If subtitle ranges overlap, prefer the segment whose midpoint is closest to the frame timestamp.
