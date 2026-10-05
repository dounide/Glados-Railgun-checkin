# Glados自动签到

## 食用方式：

### 注册一个GLaDOS的账号([注册地址](https://glados.space/landing/0A58E-NV28S-6U3QV-33VMG))

#### 我的邀请码：([0A58E-NV28S-6U3QV-33VMG](https://0a58e-nv28s-6u3qv-33vmg.glados.space))

#### 我的优惠码（9折）：([DEVILSTORE](https://0a58e-nv28s-6u3qv-33vmg.glados.space))

### **Fork**本仓库

![图片加载失败](imgs/1.png)

### 添加**secret**

1. 跳转至自己的仓库的`Settings`->`Secrets and variables`->`Action`

2. 添加1个`repository secret`，命名为`GLADOS_COOKIES`，其值对应GLaDOS账号的cookie值中的有效部分（获取方式如下）

- 在GLaDOS的签到页面按`F12`

- 切换到`Network`页面下，刷新

![图片加载失败](imgs/2.png)

- 手动签到一次，找到实际的 `/api/user/checkin` 请求，在 `Request Headers` 中复制完整 `Cookie` 值；不要只保留旧示例的两项。不要公开 Cookie。

  > 参考格式：koa:sess=eyJ1c2xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxAwMH0=; koa:sess.sig=xJkOxxxxxxxxxxxxxxxtnM; gld:sess=新版会话值; gld:sess.sig=新版签名值;

![图片加载失败](imgs/3.png)

- 多账号请在 `GLADOS_COOKIES` 中 添加多个 `cookies` 中间使用 `&`连接即可。（例如： `c1&c3&c3...`）

3. 配置积分兑换策略（非必须）

- 添加1个`repository secret`，命名为`GLADOS_EXCHANGE_PLAN`，配置自动兑换积分策略：

| 值 | 积分要求 | 兑换天数 |
|---|---------|---------|
| `plan100` | 100 积分 | 10 天 |
| `plan200` | 200 积分 | 30 天 |
| `plan500` | 500 积分 | 100 天 |

> 不配置时不自动兑换；只有显式设置 `plan100` / `plan200` / `plan500` 才启用。签到失败时跳过兑换。

4. 手机推送（非必须）

- 添加1个`repository secret`，命名为`PUSHDEER_SENDKEY`，其值对应 PushDeer key: ([获取地址](https://www.pushdeer.com/product.html))。

### **star**自己的仓库

![图片加载失败](imgs/4.png)

## 文件结构

```shell
│  checkin.py	# 签到脚本
│
├─.github
│  └─workflows
│          gladosCheck.yml	# Actions 配置文件
```

## 更新日志

- **2026-01**: 重构代码，添加log输出方便定位，支持新版网址，支持配置积分兑换策略。
- **2026-04**: 优化代码逻辑，优化日志输出，支持[新版域名](https://railgun.info) ，在 GLADOS_COOKIES 中添加新版域名下的 cookies 即可使用。


## 问题排查与定位
- 大家可以通过查询 actions 中的 running checkin 日志快速定位问题，有其他问题提交issue。

  <img width="1684" height="844" alt="image" src="https://github.com/user-attachments/assets/45348a5f-43e4-45f5-8fdf-ce84d343b30d" />

## 声明

本项目不保证稳定运行与更新, 因GitHub相关规定可能会删库, 请注意备份









## 2026-10-05 本地修复说明

详见 [排查与部署说明](REPAIR_NOTES.md)。本版本整合上游 2026-09-29 的设备平台适配和日志时区修复，并增加：

- Cookie 字段缺失提示（只输出字段名，不输出值）。
- `code=4` 且 `reason=device-mismatch` 时，对已知平台调整请求头，最多重试一次；其他业务拒绝不自动重试。
- GET 查询的有限重试；不因 429/5xx 或读取超时自动重放 POST，避免重复签到/兑换。
- 失败原因保留在日志和推送里；失败或缺少 Cookie 时返回非零退出码。重复签到不是失败。
- 修正 master 分支 push 触发，保留 UTC 04:00/10:00（北京时间 12:00/18:00）计划。
- GitHub Actions 执行离线回归测试，不使用 Secrets、不访问签到站点。

离线测试：`python -m unittest discover -s tests -v`。

**此版本尚未用真实账号验证，更新 Cookie 后需要手动触发 Actions 检查。**
