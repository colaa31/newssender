# 每日国际新闻推送

一个由 GitHub Actions 定时运行的轻量新闻简报工具，每天将国际科技与国际政治新闻发送到 QQ 邮箱。

## 功能

- 每天北京时间 07:00 运行，也可在 GitHub Actions 页面手动触发。
- 从 Google News RSS 搜集近 30 小时的英语新闻，覆盖科技、AI、网络安全、芯片、国际政治、外交、选举和冲突等主题。
- 如果配置 `OPENAI_API_KEY`，会生成简体中文摘要并保留原始新闻链接；不配置时则发送标题、来源及 RSS 摘要。
- 使用 Python 标准库，无第三方依赖。

## 部署

1. 将本目录内容复制到一个 GitHub 仓库根目录（确保 `.github/workflows/daily-news.yml` 在仓库内）。
2. 在 QQ 邮箱网页端的 **设置 → 账户** 中开启 SMTP 服务，并生成 SMTP 授权码。QQ 邮箱 SMTP 地址为 `smtp.qq.com`，本工具使用 SSL 端口 `465`。
3. 在 GitHub 仓库 **Settings → Secrets and variables → Actions** 添加 Repository secrets：
   - `QQ_EMAIL`：你的完整 QQ 邮箱地址（同时作为发件人和收件人）
   - `QQ_EMAIL_AUTH_CODE`：QQ 邮箱生成的 SMTP 授权码，不是 QQ 登录密码
   - `OPENAI_API_KEY`（可选；用于中文摘要）
4. 可选地添加 Repository variable `OPENAI_MODEL` 指定模型；不填默认使用 `gpt-4.1-mini`。
5. 到 **Actions** 启用 workflow。第一次可点 **Run workflow** 验证邮箱配置。

## 修改推送时间和新闻范围

- 工作流 cron 使用 UTC。当前 `0 23 * * *` 对应北京时间每天 07:00。
- `NEWS_LOOKBACK_HOURS` 默认 30；`MAX_ITEMS_PER_TOPIC` 默认每个主题最多抓取 8 条，摘要最多保留 5 条。可在 workflow 环境变量中修改。
- 新闻由 Google News RSS 搜索聚合，可能出现重复、漏报或来源质量不一；摘要提供原文链接，重要信息应回到原文核实。

## 安全

邮箱授权码和 API key 只存放在 GitHub Actions Secrets 中，不要写进源码或提交到仓库。工作流只需要 `contents: read` 权限。
