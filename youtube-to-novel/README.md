# YouTube -> Novel Skill

## 安装方法

### 方法 1：手动安装

将整个 `youtube-to-novel/` 文件夹放入你的 Skill 目录。

### 方法 2：直接复制 `SKILL.md`

如果你的环境只需要主技能描述文件，也可以直接使用 `SKILL.md`。

---

## 使用方法

安装后，直接告诉 Agent：

```text
帮我把这个视频写成小说：https://youtube.com/watch?v=xxx
```

或者：

```text
这个 YouTube 链接的内容帮我改编成悬疑短篇小说，第一人称，8000 字：
https://youtu.be/xxx
```

如果本地已配置 Notion 归档能力，skill 在生成完成后会自动把小说沉淀到 Notion，不需要再手动执行额外命令；归档页面会优先保持精简，只保留适合复看和检索的信息。

---

## 系统依赖

首次使用前请确保安装：

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Python 依赖
pip install yt-dlp faster-whisper Pillow
```

---

## 文件结构

```text
youtube-to-novel/
├── SKILL.md
├── README.md
├── runtime/
│   ├── artifact_reader.py
│   ├── export_to_notion.py
│   ├── models.py
│   ├── notion_exporter.py
│   └── requirements.txt
├── prompts/
│   ├── frame_analysis.txt
│   └── novel_writing.txt
└── references/
    ├── download.md
    └── subtitle_formats.md
```

---

## 说明

- 该 skill 使用内置多模态能力理解关键帧和字幕
- 长文本生成采用“大纲 -> 分章 -> 摘要回写 -> 全局润色”的连续工作流
- `runtime/` 中补充了这次实际使用到的 Notion 归档代码，便于通过 GitHub 做版本管理与复现

---

## Runtime: 导出到 Notion

如果你已经拿到了 `youtube-to-novel` 的本地产物目录，可以直接使用仓库里的最小 runtime 将小说沉淀到 Notion。

### 安装依赖

```bash
cd youtube-to-novel
pip install -r runtime/requirements.txt
```

### 运行命令

```bash
cd youtube-to-novel
python runtime/export_to_notion.py \
  --artifact-dir /path/to/.youtube_novel/<video_id> \
  --notion-api-key "ntn_xxx" \
  --notion-database-id "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

可选参数：

```bash
--novel-file /path/to/小说.md
```

### 产物目录约定

```text
.youtube_novel/<video_id>/
├── info.json
├── novel_metadata.json
├── *.srt
└── 小说标题.md
```

其中 `novel_metadata.json` 至少包含：

```json
{
  "genre": "科幻",
  "perspective": "第三人称",
  "style": "文艺",
  "target_words": 5000
}
```

### 当前实现覆盖范围

- 自动读取小说 Markdown、字幕、`info.json`、`novel_metadata.json`
- 生成适合复看的一句话视频摘要
- 将页面正文精简为：`标题 + 目录 + 小说正文`
- 将 `小说类型`、`叙事视角`、`文风` 等字段自动写入 Notion
- 默认不给页面附加完整视频转写，避免正文过长
