---
name: "youtube-to-novel"
description: "将 YouTube 视频或播客自动改编为小说。用户要求把视频、音频、YouTube 链接或播客内容写成小说、故事时调用。"
---

# YouTube / 播客 -> 小说创作 Skill

## 概览

本 skill 将视频或音频内容全自动转化为小说。AI Agent 负责所有中间步骤，用户只需提供链接和偏好。

**支持输入：**
- YouTube 视频链接
- 本地上传的视频文件（mp4/mov/avi）
- 本地上传的音频文件（mp3/wav/m4a）
- 播客 RSS 链接或直链音频

---

## 执行流程

遇到符合触发条件的请求后，按以下顺序执行：

### 第 0 步：收集用户偏好（如未提供）

如果用户没有指定以下参数，**一次性询问所有缺少的信息**（不要分多次询问）：

```text
我需要确认几个创作偏好再开始：
1. 小说类型？（科幻 / 悬疑 / 言情 / 奇幻 / 现实主义 / 历史 / 恐怖 / 幽默）
2. 叙事视角？（第一人称 / 第三人称 / 全知视角）
3. 文风？（文艺 / 通俗 / 幽默 / 沉重 / 诗意）
4. 目标字数？（短篇 3000 / 中篇 8000 / 长篇 20000+）
```

若用户说"随便"或"你决定"，使用默认值：现实主义 / 第三人称 / 文艺 / 5000 字。

---

### 第 1 步：环境检查与安装

```bash
# 检查并安装必要工具
which yt-dlp || pip install yt-dlp --break-system-packages -q
which ffmpeg || echo "请安装 ffmpeg: brew install ffmpeg 或 apt install ffmpeg"
pip show faster-whisper > /dev/null 2>&1 || pip install faster-whisper --break-system-packages -q
pip show Pillow > /dev/null 2>&1 || pip install Pillow --break-system-packages -q
# 注意：不需要安装 anthropic，使用 Trae 内置的多模态能力
```

---

### 第 2 步：下载视频与提取字幕

详见 `references/download.md` 获取完整命令参考。

**执行逻辑：**

```python
def step2_download(url, temp_dir):
    info = yt_dlp_info(url)
    subtitles = try_download_subtitles(url, langs=["zh", "zh-Hans", "en"])

    if not subtitles:
        audio = download_audio(url)
        subtitles = whisper_transcribe(audio, language="zh")

    video = download_video(url, resolution="360p")
    return {"info": info, "subtitles": subtitles, "video": video}
```

**进度提示：**

```text
正在获取视频信息...
发现可用字幕，正在提取...（或：未找到字幕，启用语音转写...）
正在下载 360p 视频（仅用于截帧）...
下载完成：{标题}（时长：{时长}）
```

---

### 第 3 步：提取关键帧并与字幕对齐

此步骤不可跳过。即使字幕内容完整，也必须做关键帧分析，因为字幕只提供“说了什么”，关键帧提供“在哪里说的、画面如何、现场氛围怎样”。

**截帧策略：**

| 视频时长 | 目标帧数 | 截取间隔 |
|---------|---------|---------|
| <= 10 分钟 | 15 帧 | 每 40 秒 |
| 10-30 分钟 | 20 帧 | 每 60 秒 |
| 30-60 分钟 | 25 帧 | 每 2 分钟 |
| 60-90 分钟 | 30 帧 | 每 2.5 分钟 |
| > 90 分钟 | 35 帧 | 每 3 分钟 |

计算公式：`interval = video_duration_seconds / target_frames`

```bash
ffmpeg -i {video_path} -vf "fps=1/120" -q:v 2 {frames_dir}/frame_%04d.jpg 2>/dev/null
```

**字幕对齐逻辑：**

- 解析字幕文件时间戳
- 将每一帧时间映射到对应字幕文本
- 生成配对数据：`[{timestamp, frame_path, subtitle_text}, ...]`

---

### 第 4 步：多模态内容分析

对每一帧图片和对应字幕使用 Trae 内置多模态能力进行分析，使用 `prompts/frame_analysis.txt` 中的 Prompt 模板。

**重点提取：**

- 讲座类：PPT、板书、手势、互动氛围
- 访谈类：表情、场景、道具、环境细节
- 通用项：光线、色调、空间感

最后生成全局内容摘要：人物、主线事件、情感走向、主题、关键视觉元素清单。

---

### 第 5 步：生成小说

使用 `prompts/novel_writing.txt` 中的 Prompt 模板，根据内容结构和用户偏好智能分章节创作。

必须使用第 4 步的多模态分析结果作为素材来源，不得仅用字幕文本直接生成小说。

**生成步骤：**

1. 分析素材内容结构，识别主题、场景、转折点
2. 生成小说大纲和小说 Bible
3. 向用户展示大纲和 Bible，确认是否调整
4. 逐章生成，并在每章后生成结构化摘要
5. 全部章节完成后生成全局摘要
6. 全文润色，检查一致性、衔接和文风

**进度提示：**

```text
正在规划故事结构...
正在构建小说 Bible（人物/世界观/情节线）...
第一章：{章节标题}...
第二章：{章节标题}...
正在汇总全局故事线...
正在润色全文...
```

---

### 第 6 步：输出结果

生成最终 Markdown 文件并向用户展示：

1. 小说标题和字数统计
2. 章节目录
3. 前 500 字预览
4. 下载链接

---

## 错误处理

| 错误场景 | 处理方式 |
|---------|---------|
| 视频无法访问（私密/地区限制） | 告知用户，建议下载后上传文件 |
| 无字幕且 Whisper 转写失败 | 跳过字幕，仅用关键帧分析 |
| 视频超过 3 小时 | 提示用户选择片段，或自动截取前 60 分钟 |
| ffmpeg 未安装 | 提供安装命令，等待用户安装后重试 |
| 多模态分析请求失败 | 自动重试 3 次，记录已完成分析不重复处理 |
| 字幕语言不支持 | 强制使用 Whisper 转写 |

---

## 参考文件

需要时读取以下文件获取详细信息：

- `prompts/frame_analysis.txt`
- `prompts/novel_writing.txt`
- `references/download.md`
- `references/subtitle_formats.md`

---

## 快速示例

**用户输入：**

> 帮我把这个视频写成悬疑小说：https://youtube.com/watch?v=xxx，第一人称，5000 字

**Agent 执行顺序：**

1. 识别到链接和偏好，无需询问
2. 下载视频并提取字幕
3. 截取关键帧
4. 使用多模态能力分析内容
5. 生成大纲、逐章写作并润色
6. 输出 `{标题}.md` 文件
