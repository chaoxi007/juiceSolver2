# Juice Solver 系统工作流程

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          main.py (CLI)                               │
│  解析参数 → 加载配置 → 初始化组件 → 发现挑战 → 排序 → 逐题求解     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AgentLoop.run_challenge()                       │
│                                                                     │
│  构建三层上下文 → LLM 推理 → 解析动作 → 执行 → 吸收结果 → 循环     │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  四层记忆系统                                                │    │
│  │  L1: 对话窗口 (滑动)                                        │    │
│  │  L2: 工作记忆 (每挑战自动提取)                               │    │
│  │  L3: 持久记忆 (跨挑战共享)                                   │    │
│  │  L4: 世界模型 (LLM 提炼的结构化知识)                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 启动阶段

```bash
juice-solver --target http://localhost:3000 -n 10 -l DEBUG
```

### 1. 加载配置 (`utils/config.py`)

读取 `config.yaml`，解析为结构化配置对象：

| 配置项 | 说明 |
|--------|------|
| `target.base_url` | Juice Shop 地址 |
| `llm.providers` | LLM 的 api_key / base_url / model |
| `llm.routing` | 按任务类型路由到不同 provider |
| `agent.max_turns_per_challenge` | 每题最大回合数 (默认 25) |
| `agent.delay_between_requests_ms` | 请求间隔 (防触发限流) |
| `agent.max_total_time_minutes` | 全局超时 (默认 120 分钟) |
| `agent.memory_file` | 持久记忆存储路径 |
| `agent.log_dir` | 运行日志目录 |

### 2. 初始化组件

```
Config
  ├──→ LLMRouter        (初始化 Claude/OpenAI provider，按 task_type 路由)
  ├──→ HttpClient       (httpx 异步客户端 + AuthManager + 请求延迟)
  ├──→ ChallengeDiscovery (挑战发现)
  ├──→ MemoryStore      (持久记忆 JSON 文件)
  ├──→ WorldModel       (结构化世界知识)
  ├──→ ActionLogger     (JSONL 运行日志)
  ├──→ ProgressTracker  (进度追踪 + 状态持久化)
  └──→ AgentLoop        (组装以上所有子系统)
```

### 3. AgentLoop 构造

注册所有动作处理器 (ActionHandler)：

| Handler | 动作名 | 功能 |
|---------|--------|------|
| HttpRequestHandler | `http_request` | 发送 HTTP 请求 |
| LoginHandler | `login` | 认证并存储 JWT |
| RegisterUserHandler | `register_user` | 注册新用户 |
| CheckSolvedHandler | `check_solved` | 检查挑战是否已解决 |
| BrowserNavigateHandler | `browser_navigate` | Playwright 浏览器导航 |
| AnalyzeJsHandler | `analyze_js` | 分析 JS 源码提取秘密 |
| ThinkHandler | `think` | 内部推理 (无副作用) |
| GiveUpHandler | `give_up` | 放弃当前挑战 |
| ReadMemoryHandler | `read_memory` | 读取持久记忆 |
| WriteMemoryHandler | `write_memory` | 写入持久记忆 |
| UseSkillHandler | `use_skill` | 执行预编排的多步技能 |

---

## 挑战发现与排序

### 获取挑战列表

```
GET /api/Challenges/ → 返回所有挑战 JSON 数组
```

每个挑战包含：`id`, `key`, `name`, `category`, `difficulty`(1-6), `description`, `hint`, `solved`

### 排序规则 (`discovery/prioritizer.py`)

优先级从高到低：

1. **难度升序** — 先解简单题，积累凭据和上下文
2. **跳过特定类别** — XSS 类（需要复杂浏览器交互）自动跳过
3. **跳过已知不可解** — 如 `bullyChatbotChallenge`（依赖外部 Dialogflow）
4. **依赖关系重排** — 需要前置条件的排在依赖项之后

```
依赖示例：
  adminSectionChallenge     → 依赖 loginAdminChallenge
  fiveStarFeedbackChallenge → 依赖 loginAdminChallenge
  changePasswordBender      → 依赖 loginBenderChallenge
```

### 首次运行自动记录

首次运行时自动写入 `target_profile`：
- `base_url` — 目标地址
- `total_challenges` — 挑战总数
- `categories` — 所有类别列表

---

## Agent 主循环

### 单挑战执行流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                  AgentLoop.run_challenge(challenge)                  │
│                                                                     │
│  1. 构建系统提示词 (注入记忆上下文 + 世界模型 + 技能文档)           │
│  2. 初始化工作记忆 (WorkingMemory)                                  │
│  3. 初始化对话窗口 (ConversationWindow, max=100)                    │
│                                                                     │
│  ┌───────────── Turn Loop (最多 max_turns 轮) ──────────────┐       │
│  │                                                           │       │
│  │  ┌──────────┐                                             │       │
│  │  │ 构建消息 │ system_prompt + 历史对话 + 工作记忆摘要     │       │
│  │  └────┬─────┘                                             │       │
│  │       │                                                   │       │
│  │       ▼                                                   │       │
│  │  ┌──────────┐                                             │       │
│  │  │ LLM 推理 │ → 返回 JSON 动作对象                       │       │
│  │  └────┬─────┘   (带重试，最多 3 次)                       │       │
│  │       │                                                   │       │
│  │       ▼                                                   │       │
│  │  ┌──────────┐                                             │       │
│  │  │ 解析动作 │ Protocol.parse() → ActionRequest            │       │
│  │  └────┬─────┘   (容错：提取嵌入的 JSON)                   │       │
│  │       │                                                   │       │
│  │       ▼                                                   │       │
│  │  ┌──────────┐                                             │       │
│  │  │ 执行动作 │ Protocol.dispatch() → ActionResult          │       │
│  │  └────┬─────┘                                             │       │
│  │       │                                                   │       │
│  │       ▼                                                   │       │
│  │  ┌──────────┐                                             │       │
│  │  │ 吸收结果 │ WorkingMemory.absorb() 提取关键事实         │       │
│  │  └────┬─────┘                                             │       │
│  │       │                                                   │       │
│  │       ▼                                                   │       │
│  │  ┌──────────┐                                             │       │
│  │  │ 重复检测 │ 同一动作连续 3 次 → 注入警告               │       │
│  │  └────┬─────┘                                             │       │
│  │       │                                                   │       │
│  │       ▼                                                   │       │
│  │  判断是否解决 / 放弃 / 继续下一轮                         │       │
│  └───────────────────────────────────────────────────────────┘       │
│                                                                     │
│  挑战结束后：                                                        │
│  - 记录攻击结果到持久记忆                                            │
│  - 调用 WorldModelUpdater 提炼知识                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 终止条件

| 条件 | 结果 |
|------|------|
| `check_solved` 返回 solved=true | 成功 |
| `use_skill` 返回 solved=true | 成功 |
| Agent 调用 `give_up` | 失败（记录原因） |
| 达到 max_turns | 失败（回合耗尽） |
| 全局 deadline 到达 | 失败（超时） |

---

## 上下文构建策略 (Prompt Caching 优化)

消息组装顺序（为最大化 LLM Prompt Cache 命中率）：

```
┌─────────────────────────────────────────────────────┐
│ 1. System Prompt (静态前缀，跨 turn 不变)            │  ← 缓存命中
│    - 角色定义                                        │
│    - 动作文档 (ACTION_DOCS)                          │
│    - 技能列表 (含推荐技能)                           │
│    - 挑战信息                                        │
│    - 已知攻击手册 (CHALLENGE_HINTS)                  │
│    - 记忆上下文 (凭据、端点、攻击结果)               │
│    - 世界模型摘要                                    │
│    - 规则                                            │
├─────────────────────────────────────────────────────┤
│ 2. 完整对话历史 (assistant + user 交替)              │  ← 缓存命中
│    不做滑动裁剪，保持前缀稳定                        │
├─────────────────────────────────────────────────────┤
│ 3. 动态尾部 (每 turn 变化)                           │  ← 不缓存
│    - 工作记忆摘要 (Working Memory Summary)           │
│    - "What is your next action?"                     │
└─────────────────────────────────────────────────────┘
```

关键设计：工作记忆摘要放在最末尾，避免破坏前面的缓存前缀。

---

## 技能系统

### 两类技能

| 类型 | 来源 | 参数 | 示例 |
|------|------|------|------|
| 通用技能 | `skills/library.py` 手动定义 | LLM 填充 | `sqli_login_bypass`, `forced_browsing` |
| 挑战专用技能 | 从 `CHALLENGE_HINTS` 自动生成 | 零参数 | `solve_loginAdminChallenge` |

### 通用技能列表

- `sqli_login_bypass` — SQL 注入绕过登录
- `forced_browsing` — 访问隐藏/受限路径
- `parameter_tampering` — 参数篡改
- `idor_access` — 不安全的直接对象引用
- `null_byte_bypass` — 空字节绕过文件扩展名过滤
- `mass_assignment` — 批量赋值（注册时注入 role=admin）
- `brute_force_login` — 暴力破解登录

### 技能执行流程 (`skills/runner.py`)

```
UseSkillHandler 接收 {"action": "use_skill", "params": {"skill": "...", ...}}
    │
    ├── 查找技能定义 (get_skill)
    ├── 检查认证要求 (requires_auth)
    │
    ▼
SkillRunner.execute(skill, params)
    │
    ├── 遍历 skill.steps[]
    │     │
    │     ├── 1. 模板变量解析 ({email_payload} → 实际值)
    │     ├── 2. 通过 Protocol.dispatch() 执行动作
    │     ├── 3. 检查期望状态码 (expect_status)
    │     ├── 4. 提取变量供后续步骤使用 (extract)
    │     └── 5. 错误处理 (on_fail: continue | abort)
    │
    ├── 自动追加 check_solved 步骤 (post_check=true)
    │
    └── 返回 SkillResult {success, solved, steps_executed, summary}
```

### 模板变量系统

技能步骤中的 `{variable}` 占位符在运行时被替换：

```python
# 技能定义
SkillStep(action="http_request", params={
    "method": "POST",
    "path": "/rest/user/login",
    "body": {"email": "{email_payload}", "password": "x"}
})

# LLM 调用时传入
{"action": "use_skill", "params": {"skill": "sqli_login_bypass", "email_payload": "' OR 1=1--"}}

# 实际执行
POST /rest/user/login  body={"email": "' OR 1=1--", "password": "x"}
```

---

## 四层记忆系统

### Layer 1: 对话窗口 (`agent/window.py`)

- 滑动窗口保留最近 K 轮 (当前 K=100，实质不裁剪)
- 每轮 = (assistant_message, user_result_message)
- 为 Prompt Caching 保持完整历史

### Layer 2: 工作记忆 (`memory/working.py`)

每个挑战独立实例，自动从每轮结果中提取：

| 提取内容 | 触发条件 |
|----------|----------|
| 端点信息 (method + path → status + 分类) | 每次 http_request |
| 认证状态 (logged_in, user) | login 成功/失败 |
| 关键发现 (响应摘要) | 200 且 body > 50 字符 |
| 失败尝试 (endpoint → error) | 4xx/5xx 或 error |

生成紧凑摘要注入 LLM 上下文尾部：

```
== Working Memory (Turn 5, 8 HTTP requests) ==
Auth: Logged in as admin@juice-sh.op
Key findings:
  - GET /rest/admin/application-configuration → {"config":...}...
  - Logged in as admin@juice-sh.op
Endpoints explored (6):
  POST /rest/user/login → 200 auth response
  GET /api/Challenges/ → 200 JSON data
  GET /rest/admin/application-configuration → 200 JSON data
Failed approaches (2):
  ✗ GET /api/Users → 401
  ✗ POST /rest/user/login → error: invalid credentials
```

持久化到磁盘 (`logs/working_memory/<challenge_key>.json`) 供调试。

### Layer 3: 持久记忆 (`memory/store.py`)

JSON 文件存储，跨挑战共享：

| 类别 | 内容 |
|------|------|
| `credentials` | 已知用户凭据 |
| `endpoints` | API 端点情报 |
| `attack_results` | 每题攻击结果 (solved/failed/reason) |
| `target_profile` | 目标基本信息 |

### Layer 4: 世界模型 (`memory/world_model.py`)

LLM 提炼的结构化知识，挑战结束后由 `WorldModelUpdater` 更新：

```json
{
  "server": {"framework": "Express", "auth_mechanism": "JWT"},
  "routes": {
    "/rest/user/login": {"methods": ["POST"], "auth": "none", "notes": "SQL injectable"},
    "/ftp/": {"methods": ["GET"], "auth": "none", "notes": "directory listing"}
  },
  "users": [
    {"email": "admin@juice-sh.op", "role": "admin", "password": "admin123"}
  ],
  "file_system": {
    "/ftp/": "directory listing, .md/.pdf only, null byte bypass works"
  },
  "attack_surface": {
    "sqli_endpoints": ["/rest/user/login"],
    "redirect_allowlist": ["https://github.com/nicknisi/presentations"]
  },
  "insights": [
    "Login endpoint is vulnerable to SQL injection in email field",
    "FTP directory allows null byte bypass for restricted extensions"
  ]
}
```

更新流程：

```
挑战结束 → 截取对话 (max 6000 chars)
         → 发送给 LLM (EXTRACTION_PROMPT)
         → 解析 JSON 输出
         → WorldModel.merge_update() (去重合并)
```

---

## LLM 路由机制

### 按任务类型路由

| 任务类型 | 用途 | 配置键 |
|----------|------|--------|
| `agent` | Agent 主循环推理 | `routing.agent` |
| `extraction` | 世界模型知识提炼 | `routing.extraction` (fallback to default) |
| `general` | 通用任务 | 默认 provider |

### 调用参数

| 场景 | temperature | max_tokens | json_mode |
|------|-------------|------------|-----------|
| Agent 推理 | 0.7 | 2048 | true |
| 知识提炼 | 0.2 | 2048 | true |

### 重试机制

LLM 调用失败时自动重试（最多 3 次），退避间隔递增 (5s, 10s, 15s)。

---

## HTTP 工具包

### 请求流程

```
Agent 发出 http_request 动作
    │
    ├── HttpRequestHandler.execute()
    │     ├── inject_auth=true → 自动注入 Authorization: Bearer <token>
    │     ├── 执行请求间隔延迟 (delay_between_requests_ms)
    │     └── 发送请求 (httpx)
    │
    └── 返回 ActionResult
          ├── status_code
          ├── headers (精简)
          └── body (截断至合理长度)
```

### 认证管理 (AuthManager)

```
AuthManager:
  ├── token: str | None          当前活跃 JWT
  ├── credentials: dict          email → {password, token} 多用户存储
  ├── set_token(token, email, password)   登录成功后调用
  ├── switch_user(email)         切换到已知用户
  ├── decode_jwt()               解码当前 token 查看角色
  └── current_user_email         从 JWT 提取当前用户
```

登录成功后，所有后续 `http_request` 自动携带 `Authorization` header。

---

## 浏览器会话 (`browser/session.py`)

基于 Playwright 的无头浏览器，用于：

- SPA 路由 (`/#/...`) 需要客户端渲染
- DOM XSS 触发
- `http_request` 返回 HTML shell 但未触发挑战的场景

通过 `browser_navigate` 动作调用，支持：
- `wait_until`: 等待条件 (networkidle, load, domcontentloaded)
- `wait_for_selector`: 等待特定 DOM 元素
- `extract_selector`: 提取元素内容

---

## JS 分析 (`actions/analyze_js.py`)

用于从前端 JS bundle 中提取敏感信息：

### 功能

- 会话级缓存（同一文件只下载一次）
- 预编译正则模式库：
  - 加密/API URL
  - 硬编码凭据
  - 邮箱地址
  - 白名单/允许列表
  - 路由定义
- 自定义关键词搜索（±200 字符上下文窗口）
- 结果限制：每模式最多 10 条，每搜索词最多 5 条

### 使用场景

- 查找硬编码的管理员密码
- 发现重定向白名单
- 提取 API 端点
- 找到隐藏的配置项

---

## 重复检测与防卡死

### 重复动作检测

追踪最近 3 次动作的 `action:path` 组合：

```
如果连续 3 次相同 → 注入警告：
"⚠️ WARNING: You have repeated the same action 3 times with no progress.
 You MUST try a completely different approach, action, or path.
 If you are stuck, use give_up."
```

### 放弃策略

系统提示词中的规则：
> 如果连续 3+ 次收到相同错误（如 500），或意识到缺乏所需能力，立即调用 `give_up`。

---

## 进度追踪与报告

### 实时记录

每题结束立即记录：
- 挑战信息 (key, name, category, difficulty)
- 状态 (solved / failed)
- 使用的求解方式 ("agent")
- 尝试次数、耗时

### 状态持久化

每题结束后保存到 `session_state.json`：

```json
{
  "solved_keys": ["scoreBoardChallenge", "loginAdminChallenge", ...],
  "records": [{"key": "...", "name": "...", "status": "solved", ...}]
}
```

下次启动自动恢复，跳过已解决的挑战。

### 终端输出

实时显示每题结果（Rich 格式）：

```
  SOLVED Login Admin (12.3s)
  FAILED Forged Feedback (45.7s)
  TIMEOUT Global time limit reached after 7200s
```

运行结束输出汇总报告（按类别/难度统计）。

---

## 全局超时控制

```
session_start = time.time()
max_total_seconds = config.agent.max_total_time_minutes * 60

每题开始前检查：
  if time.time() - session_start >= max_total_seconds:
      跳过剩余挑战

每轮开始前检查：
  if time.time() >= deadline:
      中止当前挑战
```

---

## 运行日志 (`run_log/action_logger.py`)

每个动作记录为 JSONL 格式：

```json
{
  "challenge_key": "loginAdminChallenge",
  "turn": 2,
  "action": "http_request",
  "params": {"method": "POST", "path": "/rest/user/login", ...},
  "result_status": "success",
  "result_data": {"status_code": 200, ...},
  "duration_ms": 45.2
}
```

用于事后分析 Agent 行为、调试失败案例。

---

## 数据流总览

```
config.yaml
    │
    ▼
┌──────────┐     ┌───────────┐     ┌──────────────┐
│  Config  │────→│ LLMRouter │────→│ Claude/OpenAI│
└──────────┘     └───────────┘     └──────────────┘
    │                                      ▲
    ▼                                      │ LLM 调用
┌──────────┐     ┌────────────────┐        │
│AgentLoop │────→│ Protocol       │        │
└──────────┘     │ (解析+分发)    │        │
    │            └───────┬────────┘        │
    │                    │                 │
    │                    ▼                 │
    │            ┌────────────────┐        │
    │            │ ActionHandlers │        │
    │            │ ├─ http_request│───────────→ Juice Shop
    │            │ ├─ use_skill   │───┐        (HTTP API)
    │            │ ├─ browser     │───┼──→ Juice Shop
    │            │ ├─ login       │───┘    (Browser)
    │            │ ├─ analyze_js  │
    │            │ ├─ check_solved│
    │            │ └─ think/give_up
    │            └────────────────┘
    │
    ├──→ WorkingMemory (L2, 每挑战)
    ├──→ MemoryStore (L3, 持久化 JSON)
    ├──→ WorldModel (L4, 结构化知识)
    ├──→ ProgressTracker → session_state.json
    └──→ ActionLogger → logs/*.jsonl

                    ┌─────────────────────┐
                    │  WorldModelUpdater   │
                    │  (挑战结束后提炼)    │
                    │  对话 → LLM → JSON  │
                    │  → WorldModel.merge  │
                    └─────────────────────┘
```

---

## 停止条件

| 条件 | 行为 |
|------|------|
| 所有队列挑战遍历完毕 | 正常退出，输出报告 |
| 全局超时 (max_total_time_minutes) | 跳过剩余挑战，输出报告 |
| 无法获取挑战列表 (Juice Shop 未运行) | 报错退出 |
| LLM 连续失败 (3 次重试后) | 跳过当前挑战，继续下一题 |
| 单题异常 | 捕获异常，标记失败，继续下一题 |
