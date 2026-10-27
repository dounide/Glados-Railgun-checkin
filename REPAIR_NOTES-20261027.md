# 2026-10-27 自动签到排查与修复

## 证据

- 仓库：`dounide/Glados-Railgun-checkin`，排查时的默认分支 `master`，提交 `5b276adaa3e4acd63537957aa84f4b46ce0a81d0`。
- [第 111 次运行](https://github.com/dounide/Glados-Railgun-checkin/actions/runs/40200934173)：北京时间 2026-10-25 22:09，签到返回 `code=1`，当天已签到。后续自动兑换因不足 100 积分被拒绝，但签到状态正常。
- [第 112 次运行](https://github.com/dounide/Glados-Railgun-checkin/actions/runs/40303267610)：北京时间 2026-10-26 17:55，状态、签到、积分均返回 `code=-2`；签到消息为“没有权限”。
- [第 114 次运行](https://github.com/dounide/Glados-Railgun-checkin/actions/runs/40428871962)：北京时间 2026-10-27 08:50，同样鉴权失败。已加载一个 Cookie，未提示四个会话字段缺失，Python 和依赖安装成功。
- 成功与失败运行使用同一份代码。问题是站点不接受仓库保存的会话；日志本身不能确定是过期、会话被撤销还是域名不匹配。
- 本次浏览器页面显示在 `https://glados.space/console/checkin` 已登录，而旧脚本只请求 `glados.cloud`。官方前端设置 API baseURL 为 `/api`，签到调用 `/user/checkin`，token 为当前 hostname，因此 `.space` 页面对应 `https://glados.space/api/user/checkin` 和 `token=glados.space`。

上游 [#50](https://github.com/Devilstore/Glados-Railgun-checkin/issues/50)、[#46](https://github.com/Devilstore/Glados-Railgun-checkin/issues/46) 存在按账号、域名不同而结果不同的报告。这不是旧域名全部停用的证据，不自动轮换域名或把部分成功掩盖成全部成功。

## 修复

1. 默认使用与当前登录来源一致的 `glados.space`，支持通过 Actions Variable `GLADOS_DOMAINS` 显式选择站点。只接受三个已知站点，防止误把会话发到错误主机。
2. 鉴权失败提示指出当前域名和相应 Cookie 的更新入口；失败仍返回非零退出码。
3. 积分不足或积分查询失败时跳过兑换，已有显式兑换计划保持有效。
4. 默认日志显示实际获得积分，空的 `GLADOS_VERBOSE` 使用默认值。
5. 工作流加入离线回归测试，签到失败后仍执行 Keep alive，保留原有定时计划。

## 会话更新与真实验证

如现有 Secret 仍被拒绝，需要在 `.space` 重新登录，从实际 `/api/user/checkin` 请求的 Request Headers 复制完整 Cookie，直接更新 GitHub Actions Secret `GLADOS_COOKIES`。不要发送到聊天，不要填到普通 Variables，不要提交到 Git。

部署后执行 `auto check`。通过标准是签到日志明确显示成功或当天已签到、全部任务无失败，且 Actions 成功。离线测试通过不能替代这个真实验证。

本记录生成时，尚未完成更新后 Secret 的线上验证。最终执行结果将保存到本项目的验证记录。

## 本地文件

本次基于线上提交创建独立修复目录，原 `Glados-Railgun-checkin` 中的未提交修改和 10 月 5 日修复包保留。
