# 视频文案工作台

本地批量提取抖音、B站、小红书及音视频文件的口播文案，导出 Excel、Word、SRT、TXT 和 ZIP。

## 项目目录

- [versions/Web](versions/Web/README.md)：完整 Web 开发目录，包含源码、测试、启动脚本、模型和本机订单数据。双击「打开Web.cmd」启动。
- [versions/Windows](versions/Windows/README.md)：Windows 客户便携交付包及构建输出。
- [versions/macOS](versions/macOS/README.md)、[versions/Android](versions/Android/README.md)、[versions/iOS](versions/iOS/README.md)：预留平台目录，尚未开发。

开发与测试在 `versions/Web` 中进行，Windows 构建从该目录读取源码并输出到 `versions/Windows/builds/`。根目录只保留仓库说明和 Git 配置。

本地服务运行在使用者自己的设备上，不需要运营者部署云服务器。网址快捷方式只打开页面，服务未启动时请使用 Web 启动脚本。

运行环境、模型、订单、构建缓存及大体积交付包仅保存在本地，不上传 GitHub。详细安装、构建和使用说明见 Web 目录 README。
