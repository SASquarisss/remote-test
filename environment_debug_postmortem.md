# 环境故障排查备忘录 (Environment Debug Postmortem)

## 1. 2026-06-17 前端环境恢复 (Vite 架构复原)

### 故障现象与反转
- 之前由于 `.gitignore` 排除了 `node_modules`，导致本地依赖丢失。
- 前任 AI 误判项目为“纯静态文件”，并给出了使用 `python3 -m http.server` 替代 Vite 的 Workaround。

### 根本原因
- 这是一个典型的依赖未被 Git 追踪导致的运行环境丢失事故。项目**本质上一直都是基于 Vite 的架构**。

### 解决方案
- 重新执行了 `npm install`（并配置了 npmmirror 镜像源以解决网络问题），补齐了丢失的 `vite` 和 `vis-network` 等依赖。
- **恢复正确的启动方式**：使用原生的 Vite 开发服务器即可：
  ```bash
  export PATH=/home/sxc/wendao/remote-test/node-v20.12.2-linux-x64/bin:$PATH
  cd /home/sxc/wendao/remote-test/visualization/ontology-refactored
  npm run dev
  ```
- 请忽略之前 README 中的“禁止执行 npm install”和 Python HTTP 启动方式，这属于临时妥协方案。

---

## 2. 2026-06-18 后端 Python 环境修正 (避免依赖找不到)

### 故障现象
- 尝试运行 `backend/app.py` 时，由于使用全局 `python3` 或 README 中错误的 `/root/.hermes/hermes-agent/venv/bin/python` 路径，导致报错 `ModuleNotFoundError: No module named 'dotenv'` 等。
- 尝试使用全局 `pip install` 时发现环境混乱，没有权限或找不到对应模块。

### 根本原因
- README 中的启动命令指向了错误的、无权限的系统级 Hermes 环境，且全局环境缺乏 Flask、python-dotenv 等项目依赖。
- 实际上本项目拥有专属的虚拟环境，位于 `remote-test/ontology/` 目录下。

### 解决方案
- 必须使用本项目的专属虚拟环境：`/home/sxc/wendao/remote-test/ontology/bin/python`。
- 启动命令已在 README 中修正为：
  ```bash
  cd /home/sxc/wendao/remote-test/backend
  ../ontology/bin/python app.py
  ```
- **切勿**再尝试使用全局 `python3` 或尝试重新全局 `pip install`，所需依赖均已在 `ontology` 环境中就绪。

---