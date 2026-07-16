# 发布插件到上游兼容市场

> [!IMPORTANT]
> 本现代化 fork 当前没有由 Xero-Team 运营的独立官方插件市场。Dashboard
> 的默认市场源仍连接 AstrBot 上游服务，以保持现有的浏览、安装和更新流程可用。
> 本页介绍的是向 AstrBotDevs 维护的**上游插件市场**投稿；该渠道并非本 fork
> 运营的官方发布渠道，也不代表本 fork 对其中插件的审核、背书或支持。

在编写完插件后，你可以选择将插件发布到上游 AstrBot 插件市场，让更多上游社区用户使用你的插件。

上游市场使用 GitHub 托管插件，因此你需要先将插件代码推送到之前创建的 GitHub 插件仓库中。

你可以前往 [AstrBot 上游插件市场](https://plugins.astrbot.app) 提交你的插件。进入该网站后，点击右下角的 `+` 按钮，填写好基本信息、作者信息、仓库信息等内容后，点击 `提交到 GITHUB` 按钮。该网站及其审核流程由上游维护者管理。

> [!WARNING]
> **上游主仓库 Issue 提交方式已废弃**：此前通过 AstrBot 上游主仓库 Issue 提交插件的方式已不再使用。现在请前往上游的 **[AstrBot_Plugins_Collection](https://github.com/AstrBotDevs/AstrBot_Plugins_Collection)** 仓库提交你的插件。

你将会被导航到 AstrBot_Plugins_Collection 仓库的 Issue 提交页面，请确认信息无误后点击 `Create` 按钮提交，即可完成插件发布。

![fill out the form](https://files.astrbot.app/docs/source/images/plugin-publish/image.png)

> ⚠️ **大小限制**：发布到插件市场的插件压缩包（zip）大小**不得超过 16MB**。如果超过此限制，CI/CD 流水线将自动拒绝该发布请求。
>
> 为确保你的插件能顺利通过审核和发布，建议采取以下措施：
>
> - **压缩图片等静态资源**：对插件中的图片、音频等资源文件进行压缩，减小体积。
> - **清理不必要的文件**：避免将 `.git` 目录、`__pycache__`、`node_modules`、开发用配置文件等非必需文件提交到插件仓库中。建议在仓库根目录添加 `.gitignore` 来排除它们。
> - **优化依赖体积**：如果插件包含体积较大的依赖库，可考虑精简或按需引入。
> - **使用 `.gitattributes` 或发布分支**：通过只包含发布所需文件的策略来减小 zip 包体积。
>
> 如果插件确实因业务需要无法压缩到 16MB 以内，请联系上游市场维护者确认是否可以例外处理；本 fork 的维护者无法代为审核或绕过该限制。
