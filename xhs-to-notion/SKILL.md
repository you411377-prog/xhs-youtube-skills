---
name: "xhs-to-notion"
description: "处理小红书链接：本地抓取内容与图片 -> 使用 Trae 内置 AI 总结整理 -> 归档到 Notion。用户发送小红书链接或要求归档笔记时触发。"
---

# XHS -> Notion

## 概览

这个 skill 用于把小红书笔记归档到 Notion。

和传统“脚本自己调模型 API”不同，这个 skill 采用 Agent 架构：

1. Python 脚本负责抓取小红书内容和图片
2. Trae Agent 使用内置 AI 读取抓取结果并生成总结
3. Python 脚本再把总结和原文一起归档到 Notion

因此，默认不要求用户额外配置 AI API key。

## 触发条件

满足任一条件时触发：

- 用户消息包含 `xiaohongshu.com/explore/` 或 `xhslink.com/`
- 用户明确说要把某条小红书笔记归档到 Notion
- 用户说“抓取小红书并总结整理”

## 前置检查

项目目录固定为：

```bash
/Users/bytedance/Documents/trae_projects/social-media-assistant
```

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
- 如果没有 AI key，就使用 Trae 内置 AI 做总结

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

### 第 2 步：读取抓取结果并用 Trae 内置 AI 生成总结

必须读取：

- `source.md` 中的正文和元信息
- `images/` 中的本地图片（如存在）

总结要求：

- 用中文输出
- 不要复述原文，要做“提炼和整理”
- 输出结构尽量稳定，建议包含：
  - 一句话总结
  - 核心信息点
  - 内容类型判断
  - 适合沉淀到 Notion 的整理版
  - 如有图片，补充图片传达的信息

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
3. Notion 结果：是否成功，页面链接是什么
4. 如果失败：明确失败在哪一步

## 可选降级

如果用户只想先体验抓取，不想归档：

- 只执行第 1 步和第 2 步
- 不执行 Notion 导出

如果 Notion 未配置，但用户只想看整理结果：

- 允许直接输出总结
- 不要阻塞整个流程

## 当前限制

- 当前仅完整支持小红书
- 抖音抓取尚未实现
- 飞书导出尚未实现
- 如果页面需要登录，仍然依赖用户自己的 Cookie
