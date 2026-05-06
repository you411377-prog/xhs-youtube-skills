---
name: "xhs -> notion"
description: "处理小红书链接：本地抓取内容与图片 -> 默认使用 Trae 内置 AI 做文字与图片理解 -> 归档到 Notion；如用户已配置 API，也允许脚本内直跑。"
---

# XHS -> Notion

## 概览

这个 skill 用于把小红书笔记沉淀到 Notion，并适配两种工作环境：

1. 默认模式：使用 Trae / Agent 内置 AI 完成文字总结和图片理解
2. 可选模式：如果用户已经配置外部 API，则允许脚本自己调模型

设计原则：

- 只在 Trae 里用时，优先走 Agent 模式，减少用户额外配置
- 需要脱离 Trae、做网站、批处理或自动化服务时，再切到脚本 API 模式
- 无论使用哪种 AI 模式，抓取和 Notion 归档都由本地 Python 脚本负责
- 总结输出采用“固定骨架 + 可选扩展”模式，兼顾稳定入库和内容灵活性

## 触发条件

满足任一条件时触发：

- 用户消息包含 `xiaohongshu.com/explore/`、`xiaohongshu.com/discovery/item/` 或 `xhslink.com/`
- 用户明确说要把某条小红书笔记归档到 Notion
- 用户说“抓取小红书并总结整理”
- 用户说“xhs -> notion”

## 固定目录

项目目录固定为：

```bash
/Users/bytedance/Documents/trae_projects/social-media-assistant
```

抓取产物默认目录：

```bash
.trae_artifacts/xhs_to_notion/latest
```

## 前置检查

首次运行前先检查：

```bash
cd /Users/bytedance/Documents/trae_projects/social-media-assistant
./.venv/bin/python -m src.main --doctor
```

至少需要：

1. `cookies/xhs_cookies.json`
2. `config/config.yaml`
3. Notion token
4. Notion database id

说明：

- AI key 是可选项
- 如果没有 AI key，默认使用 Trae / Agent 内置 AI
- 如果用户已经在 `config/config.yaml` 里配置了 `ai.deepseek.api_key`、`ai.openai.api_key` 或图片分析 key，则允许切换到脚本 API 模式

## 模式选择规则

执行任务时，必须先按以下顺序判断运行模式：

### 规则 1：默认优先 Agent 模式

如果当前任务发生在 Trae 内，且用户没有明确要求“脚本自己调用模型”，默认使用：

- Trae 内置文本模型做总结
- Trae 内置多模态能力做图片理解

此时：

- 不要求外部 LLM API key
- Python 只负责抓取和归档

### 规则 2：用户已配置 API 时允许脚本模式

如果用户明确要求“脚本自己调模型”，或当前环境不依赖 Trae Agent，则可以走脚本模式：

- 文本总结：使用 `src/summarizer/ai_summarizer.py`
- 图片分析：使用 `src/analyzer/image_analyzer.py`

此时要求：

- 已配置对应的 API key
- 若缺 key，则回退到 Agent 模式，而不是直接失败

### 规则 3：图片理解模型要求

无论哪种模式，都必须满足图片理解能力：

- Agent 模式：Trae 平台应提供可用的多模态图片理解能力
- 脚本模式：用户应配置图片分析所需的模型 API

如果图片理解能力不可用：

- 仍可继续处理正文总结
- 但必须明确告知用户“图片只做了弱分析或未分析”

## 执行流程

遇到符合条件的请求后，按以下顺序执行：

### 第 1 步：抓取内容到本地产物目录

执行命令：

```bash
cd /Users/bytedance/Documents/trae_projects/social-media-assistant
./.venv/bin/python -m src.main --fetch-only "{{用户发送的链接}}" --artifact-dir .trae_artifacts/xhs_to_notion/latest
```

抓取完成后，会生成：

- `.trae_artifacts/xhs_to_notion/latest/source.md`
- `.trae_artifacts/xhs_to_notion/latest/content.json`
- `.trae_artifacts/xhs_to_notion/latest/images/`

如果命令失败，优先向用户说明是：

- Cookie 缺失或失效
- 链接无效
- 笔记已删除或私密

### 第 2 步：读取抓取结果并生成总结

必须读取：

- `source.md` 中的正文和元信息
- `content.json` 中的结构化字段
- `images/` 中的本地图片（如存在）

### 第 2A 步：默认 Agent 模式

默认由 Trae / Agent 执行：

- 阅读 `source.md`
- 阅读 `content.json`
- 逐张查看本地图片
- 如有评论区摘录，也一起纳入判断
- 结合图文一起生成总结

### 第 2B 步：可选脚本 API 模式

如果用户明确要求脚本自己调模型，且配置已完整，可直接执行：

```bash
cd /Users/bytedance/Documents/trae_projects/social-media-assistant
./.venv/bin/python -m src.main "{{用户发送的链接}}"
```

或在需要跳过脚本内总结时仍可使用：

```bash
./.venv/bin/python -m src.main --no-summary "{{用户发送的链接}}"
```

## 总结模板规则

总结必须使用“固定骨架 + 可选扩展”模式。

### 固定骨架

以下小标题必须始终输出，并写入 `summary.md`：

```md
# 一句话观点

## 主题标签

## 知识类型

## 核心问题

## 关键结论

## 适用场景

## 启发等级

## 可行动点

## 复看状态
```

固定骨架要求：

- 用中文输出
- 不要复述原文，要做“提炼和整理”
- 必须综合正文、元信息、图片、评论区摘录（如有）
- 每个小标题都要出现
- 如果某项信息不足，可以写“无明显信息”或“暂不判断”，不要省略标题

### 可选扩展

在固定骨架之后，可以按内容类型追加可选小节，常见包括：

- `## 图片观察`
- `## 评论区讨论摘录`
- `## 争议点`
- `## 反例与边界`
- `## 数据/证据`
- `## 额外信息`

可选扩展规则：

- 不是每篇都必须出现
- 只有在内容确实提供了额外增量信息时才写
- 可选扩展主要写进页面正文，不强制映射为 Notion 属性

### 字段判定规则

- `主题标签`：写 3 到 6 个最适合检索的主题词
- `知识类型`：优先从 `方法 / 观点 / 案例 / 清单 / 模型 / 经验` 中选择一个；若都不合适，可给最接近的判断
- `核心问题`：写这条内容真正试图回答的问题
- `关键结论`：写 3 到 6 条最值得记住的结论
- `适用场景`：写 2 到 5 个未来会复看它的使用场景
- `启发等级`：只写 `高 / 中 / 低`
- `可行动点`：写可执行动作，不写空泛鸡汤
- `复看状态`：默认写 `已整理`；如果信息太弱可写 `已读`

### 输出落盘

将总结写入：

- `.trae_artifacts/xhs_to_notion/latest/summary.md`

### 第 3 步：把总结归档到 Notion

执行命令：

```bash
cd /Users/bytedance/Documents/trae_projects/social-media-assistant
./.venv/bin/python -m src.main --export-from-artifact --artifact-dir .trae_artifacts/xhs_to_notion/latest --summary-file .trae_artifacts/xhs_to_notion/latest/summary.md
```

### 第 4 步：向用户汇报结果

汇报时保持简洁，包含：

1. 抓取结果：标题、作者、图片数、标签
2. 总结结果：一句话摘要 + 2-4 个核心点
3. 图片理解：是否已结合图片分析
4. Notion 结果：是否成功，页面链接是什么
5. 如果失败：明确失败在哪一步

## 可选降级

如果用户只想先体验抓取，不想归档：

- 只执行第 1 步和第 2 步
- 不执行 Notion 导出

如果 Notion 未配置，但用户只想看整理结果：

- 允许直接输出总结
- 不要阻塞整个流程

如果图片无法读取：

- 继续输出基于正文和元信息的总结
- 明确告诉用户图片未成功分析

## 当前限制

- 当前仅完整支持小红书
- 抖音抓取尚未实现
- 飞书导出尚未实现
- 如果页面需要登录，仍然依赖用户自己的 Cookie
