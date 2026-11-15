# 2026-11-15 Turnstile 验证故障

## 证据

- [第 134 次运行](https://github.com/dounide/Glados-Railgun-checkin/actions/runs/43217268186)：北京时间 2026-11-12 20:22:36，成功签到获得 1 积分。
- [第 135 次运行](https://github.com/dounide/Glados-Railgun-checkin/actions/runs/43421271270)：11 月 13 日 19:58:34，真实签到返回 `code=5, reason=turnstile`，消息为 Cloudflare verification failed，明确没有记录签到。
- [第 136 次运行](https://github.com/dounide/Glados-Railgun-checkin/actions/runs/43589291669)：11 月 14 日 19:17:22，相同失败；33 项离线测试及环境安装成功。
- 三次使用相同提交 `53bfd3a57d79a2347f1343120f0c340047cace68`、相同 `glados.space` 配置。不能把此业务验证失败归因为 502 或 Cookie 过期。
- 上游 [issue 66](https://github.com/Devilstore/Glados-Railgun-checkin/issues/66)、[issue 60](https://github.com/Devilstore/Glados-Railgun-checkin/issues/60) 有同类报告。上游目前最新提交为 2026-11-10 的 `4d3e1e5`，没有验证证据表明同步它即可解决本次 Turnstile 失败。
- [Cloudflare 官方文档](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)说明令牌有效期为 300 秒、用于一次验证；不能把一次网页令牌当作长期 GitHub Secret。

## 本次改动与边界

识别 `code=5` 且 `reason=turnstile`，显示“需要网页验证”，指向当前域名的网页签到入口。Actions 摘要只写人工处理说明，不包含 Cookie、令牌或原始站点响应。保留失败退出码、不做临时故障重试、不执行后续积分查询或兑换。其他业务错误仍按原规则处理。

用户已于 2026-11-15 提供签到前后截图：Cloudflare 验证通过后，积分从 48 增至 50，连续签到由 0 变为 1，按钮显示“Checkin! Got 2 Points”。页面套餐为 Free，奖励说明标注“Free cap max 2”。因此当天网页签到成功，本次 2 分与页面显示的免费套餐上限一致；并非脚本少发积分。

网页成功仅验证网页路径；无人值守 GitHub Actions 是否恢复需单独确认。当前没有已验证可用的官方替代自动签到入口，不能宣称此诊断更新恢复了自动签到。

本地新增验证通过：37 项离线测试，覆盖 Turnstile 错误的明确提示、不重试、不查询/兑换、保留失败退出码、摘要不写入 Cookie/原始响应、普通 code=5 不误报，以及成功运行不产生人工验证摘要。

保留原定时计划和 Secret，不自动切域名、增加消息通知或改动积分兑换配置。
