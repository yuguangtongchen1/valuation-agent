# 估价 Agent 公开介绍站

纯静态 HTML、CSS、JavaScript。无需构建或访问私有数据。

本地查看：

```sh
python3 -m http.server 5199 --directory docs
```

页面：

- `index.html`：产品介绍、逐行展开参考、历史报价详情、安装与复制提示词。
- `skill.html`：Codex Skill 使用说明。

所有报价、项目、供应商均为合成演示。无历史数据文件、飞书 token、私有链接、网络 API 或第三方追踪。

资源和站内链接均使用相对路径，可部署到 GitHub Pages 的子路径。公开仓库提供可安装 CLI 和 Skill；发布前须校验公开包没有业务资料，并核验 Pages 实际构建版本。
