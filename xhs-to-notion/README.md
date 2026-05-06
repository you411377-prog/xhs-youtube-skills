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

## 文件结构

```text
xhs-to-notion/
├── SKILL.md    # 主技能文件
└── README.md   # 安装说明和示例
```

---

## 说明

- 该 skill 默认使用 Agent 内置 AI 进行总结，不强制要求额外模型 API key
- 如果未配置 Notion，也可以只执行抓取和总结步骤
