# XHS -> Notion Runtime

这个目录包含 `xhs -> notion` Skill 的关键运行时代码。

## 包含内容

- `src/`：抓取、产物生成、Notion 导出、可选脚本 API 总结
- `tests/`：smoke tests
- `config/config.example.yaml`：配置模板
- `requirements.txt`：Python 依赖
- `REAL_SETUP.md`：真实环境接入说明

## 不包含

- `config/config.yaml`
- `cookies/`
- `.trae_artifacts/`
- 任何真实 token、cookie 或个人数据

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp config/config.example.yaml config/config.yaml
python -m src.main --doctor
```
