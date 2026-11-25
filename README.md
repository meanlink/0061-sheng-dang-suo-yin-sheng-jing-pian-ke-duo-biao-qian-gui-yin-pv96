# 声档索引 · 声景片刻的多标签归因

把有时长和证据数的片刻转为可检索标签，并保存归档编辑对候选标签的解释。

**模拟客户**　东栈声音档案组，两位采编负责周末声景素材

**现有流程**　采编用文件名记录声源。片段重叠被重复统计，较弱声音直接被强主奏覆盖，修改标签后无法确认依据。

**业务交接**　来源为带时间轴的声景监听记录，采编登记片刻特征，worker 做候选解释，档案编辑签发最终检索标签。

## 一日工作剧本

1. 10:00 选择旧码头早班 AS-71，从已录好的监听清单确认两分钟时长。
2. 10:10 按不重叠片刻登记听辨特征。
3. 10:15 核对第二片刻同时含水面与人群线索。
4. 10:25 复核员确认监听证据至少覆盖录音的一半，委托 worker 计算多标签。
5. 10:26 展开第一个片刻的人声与船流候选贡献。
6. 10:30 在许可范围内选中通过阈值的标签并附记档案依据。
7. 10:40 查阅员用最终归档标签筛选声源。

## 算法和演示边界

用独立的三个逻辑链接对语音、人群行走、引擎与浪涌等现象组成可解释权重。每个标签按 sigmoid(基线+各特征贡献) 评分，大于等于 0.65 的候选可被编辑采用。一个片刻可以含多个标签。

系数为人工设定的演示性标注规则，用于浏览和归档协作。项目不读取原始麦克风或个人信息，特征由监听编辑手工填写。

## 快速启动

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

- 前端浏览器地址为 `http://127.0.0.1:18455`。
- FastAPI 文档地址为 `http://127.0.0.1:19455/docs`。
- PostgreSQL 本地端口为 `17955`。后端与后台 worker 共用数据库事务和 Redis 健康探测。
- 开发 HTML、CSS、ES modules 后运行 `docker compose up -d --build frontend`。Python 代码修改后运行 `docker compose up -d --build backend worker`。
- `SEED_DEMO` 控制自动填充。可改三项宿主端口、`DEMO_PASSWORD`、`JWT_SECRET`、`POSTGRES_PASSWORD`。持久卷保存业务数据和队列状态。停机并保留数据使用 `docker compose down`。
- 技术栈为 Python 3.11、FastAPI、PostgreSQL 16、Redis 7、Nginx 与原生浏览器 JS。后端业务模块、SQL 迁移都在 `backend/`。界面和交互在 `frontend/`。

| 账号 | 密码 | 典型权限 |
|---|---|---|
| operator@demo.local | Demo2026! | 登记不重叠的片刻证据 |
| reviewer@demo.local | Demo2026! | 冻结归因并签最终标签 |
| viewer@demo.local | Demo2026! | 查阅记录和经计算的指标 |

共享角色和任务状态枚举分别位于 `backend/core.py` 的 `ROLES`、`JOB_STATES` 和 `frontend/base.js` 的 `roles`、`jobStates`。数据库检查约束与服务状态以相应 SQL 和模块为准。

许可证见 LICENSE。
