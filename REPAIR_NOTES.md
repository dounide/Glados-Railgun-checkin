# Glados-Railgun-checkin 排查与部署说明

## 排查结论（2026-10-05）

检查对象：dounide/Glados-Railgun-checkin，master，2a84a13（2026-07-11）。
对照上游：Devilstore/Glados-Railgun-checkin，cd89daf（2026-09-29）。

尚未读取用户的私有运行日志或 Cookie，不能断言此次失败一定是哪一项。公开 Actions 第 73 次运行显示 Success，但旧脚本业务失败时仍会正常退出，因此绿色状态不能证明签到成功。

1. **Cookie 变更是重点排查项**：上游 issue #37（2026-09-25）有用户报告，原来的 koa:sess / koa:sess.sig 外还需要 gld:sess / gld:sess.sig，更新完整 Cookie 后恢复。这是用户报告，不等于已确认本账号缺少字段。
2. **旧脚本缺少设备平台适配**：旧版固定使用 Windows UA。如果报错 code=4、reason=device-mismatch，参考上游补丁，按服务端返回的已知 loginDevice 平台调整 UA，再尝试一次。其他 reason、未知平台或持续拒绝需要人工处理，不能保证恢复。
3. **确定的状态上报缺陷**：旧版 main() 对签到失败不返回非零退出码，可能让失败显示绿色，并被“删除成功历史记录”步骤清掉。
4. **确定的触发配置错误**：默认分支 master，但 push 分支过滤为 main。这只影响提交触发，不是 schedule 或手动运行中的签到失败原因。

参考：
- https://github.com/Devilstore/Glados-Railgun-checkin/issues/37
- https://github.com/Devilstore/Glados-Railgun-checkin/commit/ee22e8c
- https://github.com/dounide/Glados-Railgun-checkin/actions/runs/37195458576

## 先更新 Cookie

1. 在自己原来登录的浏览器里打开实际使用的 GLaDOS/Railgun 站点，必要时重新登录。
2. 按 F12 打开 Network，手动签到一次，定位 `/api/user/checkin` 请求。
3. 从 Request Headers 复制完整 Cookie 值，不要复制响应 Set-Cookie，也不要把整条 cURL 命令填入 Secret。
4. 在仓库 Settings → Secrets and variables → Actions 中编辑 GLADOS_COOKIES。若请求中包含 gld:sess / gld:sess.sig，不要漏掉。
5. 多账号 Cookie 仍用 & 分隔。不要发送 Cookie 给他人，不要提交到源码或 issue。

示意（占位符不可直接使用）：

    koa:sess=...; koa:sess.sig=...; gld:sess=...; gld:sess.sig=...;

脚本对两个域名逐一请求。不同域名若使用不同会话，请依据各域名实际请求判断；不能假定一次复制的 Cookie 永远适用于所有域名。修复版任一域名任务失败都会让该次运行失败。

## 部署本地修复版

本地修改没有推送到 GitHub，也没有改动仓库 Secrets。

将修复包中的文件按原相对位置替换/添加到 GitHub master 分支：

- checkin.py
- logging_config.py
- .github/workflows/gladosCheck.yml
- tests/test_checkin.py（工作流会运行它，不能遗漏）
- README.md / REPAIR_NOTES.md / .gitignore 为说明和本地环境忽略规则

确保隐藏目录 .github 也上传。可以通过 Git 提交全部这些文件，或在 GitHub 网页编辑/添加相应文件。不需要上传 .venv、.git、日志或任何 Cookie 文件。

然后在 Actions → auto check → Run workflow，选择 master 手动执行。提交到 master 也会触发运行，不要同时触发很多次。

运行计划保持原样：UTC 04:00 / 10:00，即北京时间 12:00 / 18:00。GitHub 定时任务可能有延迟。

## 修复内容与行为变化

- 整合上游设备平台适配（仅对明确的 device-mismatch、已知平台重试一次）。
- 新 Cookie 字段缺失仅警告，不硬性拒绝旧站点仍有效的 Cookie；不输出 Cookie 值。
- 请求错误保留 HTTP 状态；非 JSON 响应有独立提示；不输出 HTTP 错误正文。
- GET 查询对网络抖动/429/5xx 有限重试。POST 不做状态错误/读取错误自动重放，避免积分兑换重复执行。
- 成功、重复签到正常退出；任一签到任务失败、无 Cookie 或主程序异常非零退出。
- 失败原因出现在摘要和推送，实际获得积分正确传递到摘要。
- 默认关闭自动兑换；若想继续旧版“500 积分兑换”的行为，显式设置 GLADOS_EXCHANGE_PLAN=plan500。已有显式有效计划继续生效。签到失败时不兑换。
- 修复日志北京时间转换和 master 提交触发。
- 签到失败后 Keep alive 仍会执行；失败后不再执行本次的删除历史运行步骤。

## 如何进一步确认原因

- code=4 且 reason=device-mismatch：设备平台不一致，检查修复版是否完成重试；仍失败则回原设备手动签到、重新登录并更新 Cookie。
- 401/403 或登录相关 message：Cookie 过期/不完整、站点限制等均有可能，要结合业务响应判断。
- 429：频率限制，降低频率并等待，不要反复手动触发。
- 非 JSON / HTML：可能跳到登录页、站点防护页或接口变更，不是“Python JSON 库坏了”。
- ConnectionResetError / Timeout：网络/服务端问题，不能仅凭这一条认定 Cookie 错误。
- code=1：重复签到，是可接受结果。

如需继续排查，只提供 Running checkin 的 HTTP 状态和 code/message/reason 等必要几行，隐藏 Cookie、邮箱和账号信息。不要为了排查把 Secrets 值打印到公开日志。

## 验证范围

离线 unittest 回归测试覆盖成功/重复、设备重试上限、未知平台/其他拒绝不重试、HTTP/超时/JSON 异常、Cookie 提示不暴露值、兑换策略、退出码、摘要以及时区/工作流配置。模拟网络与推送均被阻断。

尚未用真实账号执行签到，没有确认真实 Cookie 是否有效、目标站点是否允许此次请求，不能将离线测试通过当作线上签到恢复的证明。
