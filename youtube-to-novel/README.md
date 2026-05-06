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

如果本地已配置 Notion 归档能力，skill 在生成完成后会自动把小说沉淀到 Notion，不需要再手动执行额外命令。

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
