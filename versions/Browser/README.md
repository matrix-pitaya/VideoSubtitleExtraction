# 浏览器本地识别原型（阶段 A）

这是独立于 Streamlit 的 TypeScript 浏览器版本。音视频文件由设备读取，模型在 Worker 中推理；静态服务只提供页面、运行组件和模型。没有接入真实支付、兑换码或云端识别，也没有修改生产服务器。

当前 0.1.5 提供 **small / medium**，默认和最低为 small；固定 WASM，以文字显示计算模式，没有模式下拉框。tiny/base 和自动/WebGPU 仍禁用，不自动降级小模型。与 PC 使用相同模型规模，但量化、解码与 VAD 不同，不能保证所有音视频准确。大模型手机性能待实测。Word（DOCX）、Excel（XLSX）、TXT 和 SRT 在本机生成；Excel 只有编号/标题/文案三列，Word 标题与正文分段。无口播经确认可导出正文为空的 Word/Excel。Office 组件点导出时才加载；Excel 单元格超过 32767 字符会明确提示改用 Word/TXT，不截断交付文字。

0.1.3 默认将识别候选、手动校对及 TXT/SRT 转为简体中文，使用本地打包的 opencc-js 1.4.2 词典，不上传文字；繁简转换不修正识别错字。界面统一为原工作台风格：灰色设置侧栏、白色任务区、红色主按钮，手机纵向排列。这里只提供现有单文件能力，没有虚构订单、批量或链接入口。取消/后台中断后可直接重试；切换模型会清空当前任务并重新加载选中模型。用户导入自己的视频或音频后即可开始识别，不再要求先运行测试样例。

先运行免费中文样例，实际通过后再选择文件。0.1.2 支持单任务、单文件、100 MiB，没有固定时长上限；解码按 128 MiB 预计 PCM 内存预算预检，超过预算提示分段导入。模型和运行库占用另计，不能承诺任意长文件都能运行。并列的“图库”和“文件”按钮调用系统选择器，图库使用 `accept=video/*`，具体界面由系统决定。图库缺少扩展名时可按已知 MIME 解码。纯音乐不能可靠自动判定，候选文字必须校对，可“确认无口播，清空候选”。TXT 为带 BOM 的 UTF-8 和 CRLF 换行，SRT 为 UTF-8 毫秒时间码。

安卓和 iPhone 布局已有原型。红米 K50 / Android 12 / Chrome 151 的 tiny WASM 中文样例已由用户实测通过，用户也确认修复后的 TXT 中文正常。新版选择器、长音频和 small 模型待手机复验。iPhone 未验收。Windows WebKit 模拟无法解码本次 AAC 视频和 MP3 样例，不能当作 iPhone Safari 的结论。详见 [测试报告](reports/test-report.md)。原 Web 工作台和 Windows 构建继续使用原入口。

## 本机启动

开发需要 Node.js 24 和 Python 3.11+；买家使用部署后的浏览器页面不需要安装它们。首次准备模型需要访问 Hugging Face；浏览器运行时只访问本站，不访问 Hub。

在本目录执行 PowerShell 命令：

```powershell
npm.cmd ci
npm.cmd run prepare:runtime
python scripts/prepare-small.py
python scripts/prepare-extra-models.py medium
npm.cmd run build
npm.cmd run preview
```

打开 <http://127.0.0.1:5174/>。本机 Python 在 `../Web/.venv/Scripts/python.exe` 时，可用它代替 `python`。模型准备脚本固定提交及 SHA256，校验失败会中止，不自动更改摘要。模型、node_modules、dist 和原始自动化日志不入 Git。

修改源码后用 `npm.cmd run dev`，不要和 preview 同时占用 5174。`dist/` 是独立静态产物，不需要 Streamlit 或 Python 后端。Vite preview 仅供本机验证；正式托管须有可信 HTTPS 与安全响应头。

## 验证与手机测试

```powershell
npm.cmd test
npx.cmd playwright install webkit
npm.cmd run test:e2e
```

自动化使用已安装 Edge、Windows WebKit 和移动视口模拟，**没有模拟手机处理器、真实 Safari 或闲鱼 WebView**。测试服务器应先通过 preview 启动。样例由项目撰写的短中文文本合成，包含近静音、合成 BGM、跨分段、损坏媒体和无音轨测试；没有客户文件。

红米手机的 USB 本机测试步骤见 [Android 说明](../Android/README.md)。iPhone 需要独立可信 HTTPS 测试入口，见 [iOS 说明](../iOS/README.md)。页面可主动导出检测 JSON，不含导入文件名、媒体或识别文字；请手动填写设备信息，系统和浏览器版本单独记录。

## 实现范围

- 默认多语言 small q8，固定提交 `36050c46d777d46dc4b5f43f6d90574fc38f8732`，模型约 240 MiB，摘要见 `src/small-model-manifest.json`。首次加载及缓存读取均校验 SHA256；历史 tiny/base 测量保留在报告中。手机 small 性能尚未验证。浏览器为 ONNX q8、单线程 WASM、贪心解码，桌面为 faster-whisper int8、4 线程、beam_size=5 并启用 VAD，因此不能保证同等效果。歌曲质量需单独测试。
- 可选 medium q8，Xenova 固定提交 `8c5b90880ab9f79487ab33613413431bf661d595`，778,897,618 字节（742.8 MiB），配置及摘要见 `src/medium-model-manifest.json`。编码器移除多余注意力输出声明，保留全部节点和权重；原始/优化摘要及固定转换方法记录在 `scripts/extra-model-sources.json`。切换模型释放 Worker 并重新运行样例；选择本身不下载，运行时只加载选中模型。运行内存高于文件大小，手机性能待验收。
- large-v3 曾完成下载和校验，但浏览器实际加载连续失败；按用户要求暂缓，从界面和运行注册表移除，Worker 不接受此模型。研究脚本及摘要保留作失败记录，标准准备命令不下载它，本机权重移到忽略的 artifacts，不进入当前构建。PC 原版的 large-v3 不受影响。
- 固定 WASM，本版本无加速模式入口；运行真实短样例验证，不能按 UA 宣称兼容。
- IndexedDB 缓存，Cache API 后备；版本隔离。缓存丢失需重新下载，配额不足可在本次内存中运行，界面提示。清理方式为浏览器清除此测试站点的存储，勿清除原工作台的订单目录。
- WAV 直接 Worker 解码；MP4/MOV 优先轻量解复用 AAC-LC，遇到其他浏览器支持的音轨会回退系统音频解码，仍限制双声道以内、48kHz 以内。MP3 用系统解码。视频 HEVC 轨道本身不参与识别，真实 iPhone MOV/HEVC 尚未验证。不支持其他容器、加密或直播媒体。
- 单声道 16kHz，20 秒分段、2 秒重叠，处理时间偏移及边界重复；仍可能漏字。整文件解码有内存开销，分段不代表可接任意长视频。没有引入全量 FFmpeg WASM。
- 取消会终止 Worker；后台切换中断任务，保留本页已完成的设备验证，可直接重试。刷新不恢复任务。常亮申请拒绝及释放均提示。已显示分段可校对保存。
- 导出 Blob 下载/支持时文件分享。iPhone 保存到“文件”的实际行为待真机；无法自动跳出闲鱼时复制链接用系统浏览器重试。

共享数据规范见 [protocol](../../protocol/README.md)，模型及依赖摘要见 `src/*-manifest.json` 和 [许可清单](reports/licenses.md)。后续授权、发货、部署与回滚安排见 [分阶段说明](docs/stages-and-deployment.md)。
