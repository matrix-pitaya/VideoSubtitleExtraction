# Android 版本

状态：尚未开发，没有 APK 或 AAB。

新增 [Browser 浏览器识别原型](../Browser/README.md)，无需 APK，但须先通过实际样例检测。已完成桌面安卓视口模拟，并收到真实 Redmi K50（22041211AC）、Android 12、Chrome 151.0.7922.71 的 tiny WASM 样例报告：首次约 10.49 秒、已加载模型后约 4.04 秒。用户已确认修复后的 TXT 中文正常。0.1.2 使用并列图库/文件入口、100 MiB 文件上限和预计解码内存预算，取消固定 60 秒上限；增加可选 small 模型。新版 UI、长音频和 small 的手机性能待复验，没有证据证明全格式、全部手机或歌曲效果达标。

## 红米手机本机测试

电脑先启动 Browser 的 5174 测试服务。手机上的 `127.0.0.1` 指向手机自身，不能直接打开电脑本机网址；开发阶段可使用 USB 转发，不改生产服务器。

1. 使用数据线连接手机，在开发者选项开启 USB 调试，只授权自己的电脑。
2. 电脑安装 Android 官方 Platform Tools，在其目录执行以下命令（多台设备时用 `adb -s 设备序列号` 指定）：

```powershell
./adb.exe devices
./adb.exe reverse tcp:5174 tcp:5174
```

3. 手机 Chrome 打开 `http://127.0.0.1:5174/`，确认页面“安全连接：是”，运行免费中文短样例；再尝试本地短 MP4、WAV、无口播视频并校对。
4. 当前 0.1.5 固定本地 WASM，无计算模式下拉框；默认 small，可选 medium。先验证 small，再按设备内存试更大模型，记录首次及刷新后缓存加载、取消/后台中断、图库/文件选择和 TXT/SRT/DOCX/XLSX 实际保存。填设备型号并下载检测报告 JSON，另外记下系统版本、Chrome 版本及是否发热、退出或卡顿。历史 tiny 成功不代表新版两个模型已在手机通过。
5. 测试后撤销转发：`./adb.exe reverse --remove tcp:5174`，可关闭 USB 调试。USB 转发仅用于开发测试，不能作为买家正式使用方式。

闲鱼内置浏览器仍需可信 HTTPS 的独立测试链接；电脑 USB/Chrome 的结果不能证明闲鱼 WebView 可用。低配置安卓也需另测。没有真实结果前不标注“安卓已兼容”。

参考：[Android ADB](https://developer.android.com/tools/adb)、[Platform Tools 下载](https://developer.android.com/tools/releases/platform-tools)、[安全上下文](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts)。

预留本目录存放手机应用工程和交付文件。目标为手机本地识别，不依赖运营者云服务器。

需要开发移动界面、移植链接解析、接入本机识别引擎，并适配文件选择、分享、任务暂停恢复和设备性能。现有 Windows 程序不能直接安装到手机。
