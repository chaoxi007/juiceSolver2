# Juice Solver 系统工作流程

## 整体架构

```
┌────────────────────────────────────────────────────────────────┐
│                         main.py (CLI)                           │
│  解析命令行参数 → 加载配置 → 初始化组件 → 启动 Agent           │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                        Agent.run()                              │
│                                                                │
│  1. 加载历史进度                                                │
│  2. 注册 solver 用户                                           │
│  3. 获取挑战列表                                                │
│  4. 排序 & 依赖分析                                            │
│  5. 逐题执行 observe → plan → act → verify                    │
│  6. 输出最终报告                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 启动阶段

```
python -m src.main --target http://localhost:3000
```

### 1. 加载配置 (`utils/config.py`)

读取 `config.yaml`，解析为结构化配置对象：

- `target.base_url` → Juice Shop 地址
- `llm.providers` → LLM 的 api_key / base_url / model
- `llm.routing` → 不同任务类型路由到哪个模型
- `agent.*` → 重试次数、请求间隔、超时时间

### 2. 初始化组件

```
Config ──→ LLMRouter（初始化有效的 LLM provider）
       ──→ HttpClient（创建 httpx 异步客户端，绑定目标 URL）
       ──→ Agent（组装所有子系统）
```

### 3. 注册 Solver 插件

Agent 构造时注册所有 Solver：

| Solver | 处理类别 |
|--------|----------|
| SQLiSolver | Injection |
| XSSSolver | XSS |
| AuthBypassSolver | Broken Authentication |
| AccessControlSolver | Broken Access Control, Security Misconfiguration |
| MisconfigurationSolver | Security Misconfiguration, Miscellaneous |
| SensitiveDataSolver | Sensitive Data Exposure |
| CryptographicSolver | Cryptographic Issues |
| LLMFallbackSolver | 所有类别（兜底） |

---

## 运行阶段

### Step 1: 恢复历史进度

```python
tracker.load_state("session_state.json")
```

如果之前运行过且中断了，从 JSON 文件恢复已解决的挑战列表，避免重复尝试。

### Step 2: 注册用户 & 登录

```
POST /api/Users/     → 注册 solver@juice.test
POST /rest/user/login → 获取 JWT token
```

后续所有请求自动携带 `Authorization: Bearer <token>`。

### Step 3: 获取挑战列表

```
GET /api/Challenges/ → 返回所有挑战的 JSON 数组
```

每个挑战包含：id, key, name, category, difficulty(1-6), description, solved。

### Step 4: 排序与依赖分析 (`discovery/prioritizer.py`)

排序规则（优先级从高到低）：

1. **难度升序** — 先解简单题，积累认证凭据和上下文
2. **有专用 Solver 的优先** — 有确定解法的排前面
3. **依赖关系** — 需要 admin 权限的排在 admin 登录之后

```
例：loginAdminChallenge (难度1) → adminSectionChallenge (难度2，依赖前者)
```

### Step 5: 逐题攻击循环

对队列中每个挑战执行：

```
┌─────────────────────────────────────────────────────┐
│              _attempt(challenge)                      │
│                                                      │
│  ┌──────────┐                                        │
│  │  SELECT  │ Registry 为挑战选择最佳 Solver         │
│  │  SOLVER  │ (按 can_solve() 置信度评分)            │
│  └────┬─────┘                                        │
│       │                                              │
│       ▼         最多重试 max_retries 次              │
│  ┌──────────┐                                        │
│  │  SOLVE   │ Solver 执行攻击                        │
│  │          │ (发送 HTTP 请求)                        │
│  └────┬─────┘                                        │
│       │                                              │
│       ▼                                              │
│  ┌──────────┐                                        │
│  │  VERIFY  │ GET /api/Challenges/                   │
│  │          │ 检查该题 solved 字段是否变为 true      │
│  └────┬─────┘                                        │
│       │                                              │
│       ├── solved=true  → 记录成功，进入下一题        │
│       └── solved=false → 重试或标记失败              │
└─────────────────────────────────────────────────────┘
```

---

## Solver 选择机制

### 置信度评分

每个 Solver 对给定挑战返回 0.0-1.0 的置信度：

```
challenge: "Login Admin"
  SQLiSolver.can_solve()       → 0.95  (知识库有精确解法)
  AuthBypassSolver.can_solve() → 0.50  (类别匹配)
  LLMFallbackSolver.can_solve()→ 0.20  (兜底)

选择: SQLiSolver (最高分)
```

### 决策优先级

```
已知精确解法 (hints.py 中有 challenge key)  → 置信度 0.85-0.95
类别匹配但无精确解法                         → 置信度 0.40-0.70
LLM 兜底                                    → 置信度 0.20
```

---

## Solver 执行策略

### 策略一：已知模式直接执行

对于知识库中有确定解法的挑战，直接发送预置 payload，不调用 LLM：

```python
# hints.py 中的映射
"loginAdminChallenge": {
    "steps": [{"method": "POST", "endpoint": "/rest/user/login",
               "body": {"email": "' OR 1=1--", "password": "x"}}]
}
```

执行流程：
```
读取 hints → 构造 HTTP 请求 → 发送 → 检查响应状态码
```

### 策略二：分类载荷遍历

没有精确解法但类别匹配时，遍历该类别的预置载荷：

```
SQLi: 尝试 payloads.py 中的 auth_bypass 列表
XSS:  尝试 stored_api 载荷列表
Auth: 遍历已知用户 + 常见密码组合
```

### 策略三：LLM 推理（兜底）

前两种都无法解决时，调用 LLM 生成攻击计划：

```
┌─────────────────────────────────────────┐
│  输入给 LLM 的上下文:                    │
│  - 挑战名称、类别、难度、描述            │
│  - 已知 API 端点列表                     │
│  - 当前认证状态                          │
│  - 之前的失败尝试                        │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  LLM 输出 (JSON):                        │
│  {                                       │
│    "reasoning": "分析过程",              │
│    "steps": [                            │
│      {"method": "POST",                  │
│       "endpoint": "/rest/...",           │
│       "body": {...}}                     │
│    ]                                     │
│  }                                       │
└────────────────┬────────────────────────┘
                 │
                 ▼
         解析 JSON → 执行 HTTP 请求
```

---

## LLM 路由机制

不同任务类型可路由到不同模型：

| 任务类型 | 用途 | 推荐模型 |
|----------|------|----------|
| planning | 分析挑战、制定攻击策略 | 强模型 (Opus/Sonnet) |
| attack_gen | 生成具体攻击载荷 | 强模型 |
| classification | 快速分类判断 | 快模型 (Haiku) |
| fallback | 未知挑战的深度推理 | 最强模型 |

当前配置全部路由到 claude，可在 `config.yaml` 的 `routing` 中调整。

---

## HTTP 工具包

### 请求流程

```
Solver 调用 http.post("/rest/user/login", json_body={...})
    │
    ├── 自动注入 Authorization header (如果已登录)
    ├── 执行请求间隔延迟 (delay_between_requests_ms)
    ├── 发送请求
    ├── 记录到 history (供 LLM 分析失败原因)
    └── 返回 httpx.Response
```

### 认证管理

```
AuthManager:
  - 存储多用户凭据 (email → {password, token})
  - 支持用户切换 (switch_user)
  - JWT 解码 (decode_jwt) 用于检查当前角色
```

---

## 进度追踪

### 实时记录

每完成一题立即记录：
- 挑战信息 (key, name, category, difficulty)
- 使用的 Solver
- 状态 (solved / failed / skipped)
- 尝试次数、耗时

### 持久化

每题结束后保存到 `session_state.json`：

```json
{
  "solved_keys": ["scoreBoardChallenge", "loginAdminChallenge", ...],
  "records": [...]
}
```

下次启动时自动恢复，跳过已解决的挑战。

### 最终报告

运行结束后输出 Rich 格式表格：

```
─────────── Solve Session Complete ───────────
  Total attempted: 42
  Solved: 28
  Failed: 14
  Solve rate: 66.7%
  Elapsed: 185.3s

┌─────────────────────────┬────────┬────────┐
│ Category                │ Solved │ Failed │
├─────────────────────────┼────────┼────────┤
│ Injection               │ 5      │ 2      │
│ XSS                     │ 3      │ 4      │
│ Broken Access Control   │ 8      │ 3      │
│ ...                     │        │        │
└─────────────────────────┴────────┴────────┘
```

---

## 停止条件

当前实现的停止条件：

- **所有未解决挑战遍历完毕** → 正常退出
- **无法获取挑战列表** (Juice Shop 未运行) → 报错退出
- **单题异常** → 捕获异常，标记失败，继续下一题

---

## 数据流总览

```
config.yaml
    │
    ▼
┌─────────┐     ┌───────────┐     ┌──────────────┐
│ Config  │────→│ LLMRouter │────→│ Claude/OpenAI│
└─────────┘     └───────────┘     └──────────────┘
    │
    ▼
┌─────────┐     ┌───────────────┐     ┌────────────┐
│  Agent  │────→│ ChallengeDisc │────→│ Juice Shop │
└─────────┘     └───────────────┘     │   API      │
    │                                  └────────────┘
    │           ┌───────────────┐           ▲
    ├──────────→│ SolverRegistry│           │
    │           └───────┬───────┘           │
    │                   │                   │
    │                   ▼                   │
    │           ┌───────────────┐           │
    │           │  Solver.solve │───────────┘
    │           └───────────────┘     HTTP 请求
    │
    ▼
┌─────────────────┐     ┌──────────────────┐
│ ProgressTracker │────→│ session_state.json│
└─────────────────┘     └──────────────────┘
    │
    ▼
┌──────────┐
│ Reporter │ → 终端输出
└──────────┘
```
