# XHS -> Notion Skill

## 安装方法

### 方法 1：手动安装

将整个 `xhs-to-notion/` 文件夹放入你的 Skill 目录。

### 方法 2：直接复制 `SKILL.md`

如果你的环境只需要主技能描述文件，也可以直接使用 `SKILL.md`。

---

## 使用方法

安装后，直接告诉 Agent：

```text
帮我把这个小红书链接归档到 Notion：https://www.xiaohongshu.com/explore/xxxx
```

或者：

```text
抓取这条小红书并整理成适合沉淀到 Notion 的内容。
```

---

## 最新架构

这版 skill 采用 `Agent 优先，脚本可选回退` 的双模式架构：

1. 默认模式：Python 脚本负责抓取，Trae / Agent 负责文字总结和图片理解
2. 可选模式：如果用户已经配置自己的模型 API，允许脚本自己调模型

适用建议：

- 只在 Trae 里用：优先默认模式，不额外配置 AI key
- 以后要做网站、批处理或独立服务：再切到脚本 API 模式

---

## 前置依赖

首次使用前请确保本地项目已准备好以下配置：

- `cookies/xhs_cookies.json`
- `config/config.yaml`
- Notion token
- Notion database id

项目目录默认为：

```bash
/Users/bytedance/Documents/trae_projects/social-media-assistant
```

可先执行健康检查：

```bash
cd /Users/bytedance/Documents/trae_projects/social-media-assistant
./.venv/bin/python -m src.main --doctor
```

---

## 总结模板

这版 skill 的总结输出采用：

- `固定骨架`
- `可选扩展`

固定骨架保证每篇都能稳定写入 Notion 字段，至少包括：

- `一句话观点`
- `主题标签`
- `知识类型`
- `核心问题`
- `关键结论`
- `适用场景`
- `启发等级`
- `可行动点`
- `复看状态`

可选扩展用于避免内容死板，按实际内容追加：

- `图片观察`
- `评论区讨论摘录`
- `争议点`
- `反例与边界`
- `数据/证据`
- `额外信息`

这样既能保证 Notion 检索稳定，也能适配不同内容类型。

---

## 文件结构

```text
xhs-to-notion/
├── SKILL.md    # 主技能文件
└── README.md   # 安装说明和示例
```

---

## 说明

- 该 skill 默认使用 Agent 内置 AI 进行总结和图片理解，不强制要求额外模型 API key
- 如果用户填写自己的 API，也允许脚本内自行完成总结与图片分析
- 如果未配置 Notion，也可以只执行抓取和总结步骤
