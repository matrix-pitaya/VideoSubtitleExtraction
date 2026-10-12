# 模型与依赖来源

版本由 package-lock.json 固定，安装使用 npm ci；包下载完整性由 lockfile 的 integrity 校验。`dependency-licenses.json` 列出本机安装包（含开发工具）及许可文件摘要，`public/licenses/` 保留可取得的原文。开发依赖不等于全部被送入浏览器。

| 组件 | 固定版本/来源 | 标示许可 |
| --- | --- | --- |
| Transformers.js | 3.8.1 | Apache-2.0 |
| ONNX Runtime Web | 1.22.0-dev.20250409-89f8206ba4 | MIT |
| mp4box | 2.4.1 | BSD-3-Clause |
| TypeScript | 5.9.3 | Apache-2.0 |
| Vite | 6.4.1 | MIT |
| Playwright | 1.63.0 | Apache-2.0 |
| 原始 OpenAI Whisper | OpenAI whisper-tiny 多语言系列 | MIT；许可原文已保留 |

ONNX 转换模型来自 `onnx-community/whisper-tiny` 固定提交 `ff4177021cc41f7db950912b73ea4fdf7d01d8e7`。该提交的模型卡标示基础模型 `openai/whisper-tiny`，未见单独 license 字段；此处记录来源和原模型许可，不把它表述为转换发布者另行作出的授权保证。商用发布前仍需核对转换权重的再分发及完整通知要求。模型 SHA256、尺寸见 `src/model-manifest.json`，运行组件见 `src/runtime-manifest.json`。

样例文本为项目原创，用本机 Microsoft Huihui Desktop 合成，原文及生成脚本保留。没有打包系统语音引擎或客户素材；合成语音仅作为研发测试样例，商业宣传或再分发样例时另行确认系统语音输出相关条款。无外部音乐：BGM 样例由两组正弦波合成。

本项目原有源码的授权状态未由此次任务变更；第三方 MIT/Apache/BSD 不自动成为本项目的许可证。发布者仍应明确自身源码和客户交付的许可。公开 GitHub 源码与客户端下载的代码、模型不能声称保密或完全防复制。

安装清单另含 `@img/sharp-win32-x64 0.34.5`，标示 `Apache-2.0 AND LGPL-3.0-or-later`（Node 侧原生图像组件）。Browser 只交付构建后的静态 dist，不交付 node_modules 或这个 Windows 原生运行库，仍保留其安装清单及可取得通知；未来若打包 Node/原生运行环境，需重新核对 LGPL 等再分发要求，不能把全部依赖概括为 MIT。

来源：[Whisper](https://github.com/openai/whisper)、[转换模型](https://huggingface.co/onnx-community/whisper-tiny/tree/ff4177021cc41f7db950912b73ea4fdf7d01d8e7)、[Transformers.js](https://github.com/huggingface/transformers.js)、[ONNX Runtime](https://github.com/microsoft/onnxruntime)、[MP4Box.js](https://github.com/gpac/mp4box.js)。

新增 base 转换权重来自 `onnx-community/whisper-base` 固定提交 `1846881b6b3a3024392c1eea3ad983695bc23925`，沿用原模型及转换来源核对要求；商用再分发仍需核对转换者声明。SHA256、尺寸见 `src/base-model-manifest.json`。

新增 small 转换权重来自 `onnx-community/whisper-small` 固定提交 `36050c46d777d46dc4b5f43f6d90574fc38f8732`，同样保留原模型和转换来源核对项。SHA256、尺寸见 `src/small-model-manifest.json`。

0.1.3 新增 opencc-js 1.4.2，代码 MIT、内置 opencc-data 转换词典 Apache-2.0；LICENSE、第三方通知及 Apache 原文已随静态文件保留。采用 t2cn 构建，词典随包加载，无远程文字转换服务。来源：[opencc-js](https://github.com/nk2028/opencc-js)。

0.1.4 新增 docx 9.10.0 与 ExcelJS 4.4.0（均 MIT），用于浏览器本地 Word/Excel 导出，按需加载打包的组件。更新后的安装许可清单含 268 个包（含开发、Node 侧和可选依赖，不等于浏览器全部交付组件），现有脚本保留可取得的许可原文。来源：[docx Packer](https://docx.js.org/api/classes/index.Packer.html)、[ExcelJS](https://github.com/exceljs/exceljs)。

0.1.5 新增 Xenova/whisper-medium（提交 `8c5b90880ab9f79487ab33613413431bf661d595`）与 Xenova/whisper-large-v3（提交 `67bf02d92b7754a1ff82a7f8545f8b8c378b2ef0`）ONNX q8 权重，读取的模型卡均标示 Apache-2.0。保留 Apache 原文与 OpenAI 原始 Whisper MIT 通知；固定文件摘要及来源见对应模型 manifest 和 extra-model-sources.json。模型卡声明与基础模型许可应在商用分发时共同核对。来源：[medium](https://huggingface.co/Xenova/whisper-medium)、[large-v3](https://huggingface.co/Xenova/whisper-large-v3)。

修改通知（0.1.5）：两个编码器 ONNX 文件均由项目的 `scripts/encoder-graph.py` 移除未用于口播转写的 encoder_attentions 输出声明，以减少浏览器运行内存；节点和权重张量字节保持原样。它们是经过修改的转换文件，不是原始下载文件。源提交、原始 SHA256、派生 SHA256 和确定性转换步骤保留在 `scripts/extra-model-sources.json` 和模型 manifest；维护者准备脚本校验原始文件后转换，并再次校验派生摘要。
