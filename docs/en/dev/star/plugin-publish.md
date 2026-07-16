# Publishing Plugins to the Upstream-Compatible Marketplace

> [!IMPORTANT]
> This modernized fork does not currently operate an independent official plugin
> marketplace under Xero-Team. The Dashboard's default registry still connects to
> upstream AstrBot services so that existing browse, install, and update flows keep
> working. This page describes submission to the **upstream marketplace** maintained
> by AstrBotDevs. It is not an official publication channel operated by this fork,
> and submission does not imply review, endorsement, or support by this fork.

After completing your plugin development, you may publish it to the upstream AstrBot Plugin Marketplace so that it is available to users of the upstream community.

The upstream marketplace uses GitHub to host plugins, so you'll need to push your plugin code to the GitHub plugin repository you created earlier.

You can submit your plugin by visiting the [upstream AstrBot Plugin Marketplace](https://plugins.astrbot.app). Once on the website, click the `+` button in the bottom-right corner, fill in the basic information, author details, repository information, and other required fields. Then click the `Submit to GITHUB` button. The site and its review process are managed by the upstream maintainers.

> [!WARNING]
> **Upstream main-repository Issue submission is deprecated**: The previous method of submitting plugins via Issues in the upstream AstrBot repository is no longer used. Submit upstream marketplace entries through the **[AstrBot_Plugins_Collection](https://github.com/AstrBotDevs/AstrBot_Plugins_Collection)** repository instead.

You will be redirected to the AstrBot_Plugins_Collection repository's Issue submission page. Please verify that all information is correct, then click the `Create` button to complete the plugin publication process.

![fill out the form](https://files.astrbot.app/docs/source/images/plugin-publish/image.png)

> ⚠️ **Size Limit**: The plugin zip package submitted to the marketplace **must not exceed 16MB**. If it exceeds this limit, the CI/CD pipeline will automatically reject the submission.
>
> To ensure your plugin passes review and publication smoothly, we recommend the following:
>
> - **Compress static assets**: Compress images, audio, and other resource files in your plugin to reduce their size.
> - **Clean up unnecessary files**: Avoid including directories like `.git`, `__pycache__`, `node_modules`, or development configuration files in your plugin repository. Add a `.gitignore` file to your repository root to exclude them.
> - **Optimize dependency size**: If your plugin depends on large libraries, consider trimming them down or importing only what is needed.
> - **Use `.gitattributes` or a release branch**: Reduce the zip package size by including only the files necessary for distribution.
>
> If your plugin cannot be compressed below 16MB, contact the upstream marketplace maintainers to ask whether an exception is possible. This fork's maintainers cannot review the submission or bypass that limit.
