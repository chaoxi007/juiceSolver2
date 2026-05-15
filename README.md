# Juice Solver

基于 LLM Agent 的 OWASP Juice Shop 自动化挑战求解器。

## 架构

```
src/
├── agent/          # Agent 主循环、提示词构建、协议解析
├── actions/        # 动作处理器（HTTP请求、登录、浏览器等）
├── skills/         # 技能库（通用技能 + 挑战专用技能）
├── memory/         # 多层记忆系统
│   ├── store.py        # 持久化记忆（Layer 3）
│   ├── working.py      # 工作记忆（Layer 2，每挑战）
│   └── world_model.py  # 世界模型（Layer 4，跨挑战知识）
├── llm/            # LLM 路由与调用
├── browser/        # Playwright 浏览器会话
├── discovery/      # 挑战发现与优先级排序
├── http_toolkit/   # HTTP 客户端
├── progress/       # 进度追踪与报告
├── run_log/        # 运行日志
└── utils/          # 配置、日志工具
```

## 记忆系统

四层记忆架构：

1. **对话窗口** — 滑动窗口保留最近 K 轮对话
2. **工作记忆** — 每个挑战自动提取关键事实（端点、认证状态、失败尝试）
3. **持久记忆** — 跨挑战共享的凭据、端点、攻击结果
4. **世界模型** — LLM 提炼的结构化目标知识（服务器信息、路由、用户、攻击面）

## 安装

```bash
pip install -e .
playwright install chromium
```

## 配置

复制并编辑配置文件：

```bash
cp config.example.yaml config.yaml
```

需要配置：
- `target.base_url` — Juice Shop 地址
- `llm.providers` — LLM API 密钥和端点

## 使用

```bash
# 启动 Juice Shop
docker run -p 3000:3000 bkimminich/juice-shop

# 运行求解器
juice-solver --target http://localhost:3000

# 限制挑战数量
juice-solver -n 10

# 调试模式
juice-solver -l DEBUG
```

## 技能系统

- **通用技能**：SQL注入、强制浏览、参数篡改、IDOR、空字节绕过等
- **挑战专用技能**：从知识库自动生成，包含已知攻击步骤

Agent 优先使用匹配的技能，无匹配时回退到原始 HTTP 请求探索。

## 依赖

- Python ≥ 3.11
- httpx, anthropic/openai, playwright, rich, pyyaml
