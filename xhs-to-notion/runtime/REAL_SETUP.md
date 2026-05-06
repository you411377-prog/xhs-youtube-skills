# 真实环境接入清单

如果你没有技术背景，只需要准备下面 3 样必需资料发给我，我可以继续替你把环境接好。

## 1. 小红书 Cookie 文件

你需要给我下面两种形式中的任意一种：

- 直接把 `xhs_cookies.json` 文件发给我
- 或告诉我这个文件在你电脑上的完整路径

目标位置应该是：

```text
/Users/bytedance/Documents/trae_projects/social-media-assistant/cookies/xhs_cookies.json
```

## 2. AI Key（可选）

如果你想让脚本自己直接调模型，可以给我下面二选一：

- DeepSeek Key
- OpenAI Key

如果你只是想在 Trae 里按 Skill 方式使用，这一项可以先不提供，改由 Trae 内置 AI 来做总结。

如果你还想让程序分析图片内容，可以再额外给我：

- Gemini / OpenRouter Key

## 3. Notion Integration Token

这是 Notion 的接口密钥，通常看起来像一串很长的字符。

## 4. Notion Database ID

这是你希望归档笔记的 Notion 数据库 ID。

## 你发给我时的最简单格式

你可以直接按这个格式回复我：

```text
1. Cookie 文件路径：

2. Notion Token：

3. Notion Database ID：

4. 如果你要脚本自己调模型，再补充：
   我用的 AI 是：
   Key 是：
```

## 我会替你做什么

你把资料给我后，我会继续替你完成：

- 写入 `config/config.yaml`
- 检查 Cookie 是否有效
- 检查 Notion 数据库是否能访问
- 运行 `--doctor` 体检
- 用一条真实小红书链接做一次完整验证
- 如果你不提供 AI key，就按 Skill / Agent 架构帮你跑通

## 你自己也可以先点这个命令

```bash
cd /Users/bytedance/Documents/trae_projects/social-media-assistant
./.venv/bin/python -m src.main --doctor
```

它会直接告诉你现在还缺什么。
