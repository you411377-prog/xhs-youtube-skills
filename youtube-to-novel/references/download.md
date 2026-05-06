# yt-dlp 和 ffmpeg 命令参考

## yt-dlp 常用命令

### 获取视频信息（不下载）

```bash
yt-dlp --dump-json "URL" | python -c "
import json, sys
info = json.load(sys.stdin)
print(f'标题：{info[\"title\"]}')
print(f'时长：{info[\"duration\"]}秒')
print(f'频道：{info[\"channel\"]}')
print(f'描述：{info[\"description\"][:200]}')
"
```

### 下载自带字幕（优先中文）

```bash
yt-dlp \
  --write-sub \
  --write-auto-sub \
  --sub-lang "zh-Hans,zh,zh-Hant,en" \
  --convert-subs srt \
  --skip-download \
  -o "%(title)s.%(ext)s" \
  "URL"
```

### 仅下载音频（用于 Whisper 转写）

```bash
yt-dlp \
  -x \
  --audio-format mp3 \
  --audio-quality 0 \
  -o "audio.%(ext)s" \
  "URL"
```

### 下载视频（用于截帧）

```bash
yt-dlp \
  -f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]" \
  --merge-output-format mp4 \
  -o "video.%(ext)s" \
  "URL"
```

### 检查可用字幕语言

```bash
yt-dlp --list-subs "URL"
```

---

## ffmpeg 关键帧提取命令

### 固定间隔截帧

```bash
ffmpeg -i video.mp4 -vf "fps=1/30" -q:v 2 frames/frame_%04d.jpg
ffmpeg -i video.mp4 -vf "fps=1/60" -q:v 2 frames/frame_%04d.jpg
ffmpeg -i video.mp4 -vf "fps=1/30,scale=1280:720" -q:v 3 frames/frame_%04d.jpg
```

### 场景变化检测截帧

```bash
ffmpeg -i video.mp4 \
  -vf "select='gt(scene,0.4)',scale=1280:720" \
  -vsync vfr \
  -q:v 3 \
  frames/scene_%04d.jpg
```

### 获取视频基本信息

```bash
ffprobe -v quiet -print_format json -show_format -show_streams video.mp4 | \
  python -c "
import json, sys
info = json.load(sys.stdin)
duration = float(info['format']['duration'])
print(f'时长：{int(duration//60)}分{int(duration%60)}秒')
"
```

### 提取音频（备用）

```bash
ffmpeg -i video.mp4 -vn -acodec mp3 -q:a 2 audio.mp3
```

---

## Whisper 转写命令

### 使用 faster-whisper

```python
from faster_whisper import WhisperModel

model = WhisperModel("medium", device="cpu", compute_type="int8")
segments, info = model.transcribe("audio.mp3", language="zh", beam_size=5)

with open("subtitle.srt", "w", encoding="utf-8") as f:
    for i, seg in enumerate(segments, 1):
        start = format_timestamp(seg.start)
        end = format_timestamp(seg.end)
        f.write(f"{i}\n{start} --> {end}\n{seg.text.strip()}\n\n")

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
```

### 使用原版 whisper

```bash
whisper audio.mp3 --language zh --model medium --output_format srt --output_dir ./
```
