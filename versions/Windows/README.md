# Windows 版本

状态：已可用桌面试用版，支持 Windows 10 / 11 x64。现有 Web 界面显示在独立软件窗口中。

最新交付文件：`builds/20261011-desktop/VideoSubtitleExtraction-Windows-x64.zip`，同目录附 `SHA256.txt`。`20261011-project-name` 和旧中文名称 ZIP 是历史浏览器版本。

将 ZIP 发送给客户。客户完整解压后双击「VideoSubtitleExtraction.exe」，即可打开独立软件窗口，无需启动浏览器或操作 CMD。关闭窗口会结束这一份软件的后台，同一目录不会重复打开。

自带 Python 运行环境、处理依赖和 small 模型，支持抖音、B站、小红书链接，以及本地音视频。需要 Microsoft Edge WebView2 Runtime 和 .NET Framework 4.6.2 或更新版本；缺少时按包内使用说明安装微软官方组件。EXE 是入口，需要保留整个解压目录。

窗口启动不会识别视频，点击开始后才处理；处理过程中关闭窗口会中断当前任务。试用版尚未商业代码签名。

不依赖你的后台，不含你的订单或登录凭证。客户使用过程会在自己的解压目录生成数据。ZIP 大文件仅保存在本机，不加入 GitHub 源代码仓库。
