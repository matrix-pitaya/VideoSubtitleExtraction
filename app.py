from pathlib import Path
import streamlit as st
from core import ROOT, MEDIA_EXTENSIONS, FINISHED_STATUSES, transcript_paragraphs, add_item, create_order, extract_links, load_orders, process_item, save_order, export_order

st.set_page_config(page_title="视频文案工作台", page_icon="🎬", layout="wide")
st.title("🎬 视频文案工作台")
st.caption("接单 → 批量导入 → 口播转写 → 校对 → Excel / Word / SRT 交付")

@st.cache_resource
def get_model(name, device):
    from faster_whisper import WhisperModel
    model_dir = Path(__file__).resolve().parent / "models" / name
    ready = all((model_dir / f).is_file() for f in ["model.bin", "config.json", "tokenizer.json"])
    return WhisperModel(str(model_dir) if ready else name, device=device,
                        compute_type="int8" if device == "cpu" else "float16",
                        local_files_only=ready)

with st.sidebar:
    st.header("订单管理")
    with st.form("new_order"):
        name = st.text_input("订单名称", placeholder="客户名称")
        if st.form_submit_button("创建订单"):
            st.session_state.order_id = create_order(name)["id"]
            st.rerun()
    orders = load_orders()
    if not orders:
        st.info("先创建一个订单。")
        st.stop()
    ids = [o["id"] for o in orders]
    selected = st.selectbox("选择订单", ids, index=ids.index(st.session_state.get("order_id")) if st.session_state.get("order_id") in ids else 0,
                            format_func=lambda v: next(o["name"] + " · " + v for o in orders if o["id"] == v))
    model_name = st.selectbox("识别模型", ["small", "medium", "large-v3", "tiny"], help="small 适合 CPU 起步；更大的模型占用更多内存，首次使用需下载。")
    device = st.selectbox("计算设备", ["cpu", "cuda"], help="CUDA 需要兼容的 NVIDIA 显卡和运行库。")
    language = st.selectbox("音频语言", ["中文", "自动检测", "英语"])
    extraction_mode = st.selectbox("提取方式", ["口播文案（默认，无口播留空）", "画面文字 OCR（手动选择）"])
    cookie_path = st.text_input("Cookies 文件路径（可选）", type="password", help="本机 Netscape 格式文件路径，用于你有权访问的登录内容。不会加入交付包。")

order = next(o for o in orders if o["id"] == selected)
st.subheader(order["name"])
with st.expander("导入视频或链接", expanded=not order["items"]):
    with st.form("import"):
        uploads = st.file_uploader("批量选择视频 / 音频", accept_multiple_files=True, type=[e[1:] for e in MEDIA_EXTENSIONS])
        folder_input = st.text_input("或本地文件夹路径", placeholder=r"D:\客户视频", help="适合大文件；扫描此文件夹顶层的音视频。")
        links_text = st.text_area("粘贴分享文案或视频链接", placeholder="支持一次粘贴多条分享文案，自动提取 http/https 链接。")
        submitted = st.form_submit_button("加入订单")
    if submitted:
        existing = {i["source"] for i in order["items"]}
        for upload in uploads:
            source = "上传：" + upload.name
            if source in existing:
                continue
            item = add_item(order, source, upload.name)
            path = ROOT / order["id"] / "media" / item["id"] / ("upload" + Path(upload.name).suffix.lower())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(upload.getbuffer())
            item["path"] = str(path)
            existing.add(source)
        if folder_input:
            folder = Path(folder_input.strip().strip('"'))
            if not folder.is_dir():
                st.error("本地文件夹不存在。")
            else:
                for path in sorted(folder.iterdir()):
                    if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS and str(path.resolve()) not in existing:
                        add_item(order, str(path.resolve()), path.name, str(path.resolve()))
                        existing.add(str(path.resolve()))
        for url in extract_links(links_text):
            if url not in existing:
                add_item(order, url, url)
                existing.add(url)
        save_order(order)
        st.rerun()

st.info("默认只提取口播文案。仅 BGM / 无口播的视频会留空，不自动把画面或商品包装上的文字当作文案。客户 Excel 仅含编号、标题、文案；Word 按标题和正文分段。")
if extraction_mode.startswith("画面"):
    st.warning("画面文字 OCR 可能包含包装、水印或重复文字，需要人工校对；时间轴按 1 秒采样估算。")
st.caption("链接下载的临时视频 / 音频在处理结束后自动删除（失败也清理）；保留文案和字幕。重试时重新下载。上传文件和本地原文件不受影响。")
items = order["items"]
cols = st.columns(3)
cols[0].metric("视频总数", len(items))
cols[1].metric("已处理", sum(i["status"] in FINISHED_STATUSES for i in items))
cols[2].metric("失败", sum(i["status"] == "失败" for i in items))
if items:
    for item in items:
        if item.get("cleanup_error"):
            st.warning(item["title"] + "：" + item["cleanup_error"])
    st.dataframe([{k: i[k] for k in ["title", "status", "error"]} for i in items], width="stretch")
    if st.button("开始 / 重试未完成视频", type="primary"):
        pending = [i for i in items if i["status"] not in FINISHED_STATUSES]
        if pending:
            try:
                with st.spinner("加载模型；首次运行需联网下载，请耐心等待…"):
                    model = None if extraction_mode.startswith("画面") else get_model(model_name, device)
                progress = st.progress(0)
                status = st.empty()
                for index, item in enumerate(pending):
                    status.write(f"正在处理 {index + 1}/{len(pending)}：{item['title']}")
                    process_item(order, item, model, {"中文": "zh", "英语": "en", "自动检测": None}[language], cookie_path,
                                 on_progress=lambda stage: status.write(f"{index + 1}/{len(pending)} · {stage}：{item['title']}"),
                                 mode="ocr" if extraction_mode.startswith("画面") else "audio")
                    progress.progress((index + 1) / len(pending))
                st.rerun()
            except Exception as exc:
                st.error(f"模型加载失败：{exc}")
                st.info("若包含 ConnectError / WinError 10013，表示模型下载连接被阻止，切换 CPU 无法解决。可在项目目录运行 .\\.venv\\Scripts\\python.exe download_models.py --model " + model_name + "，下载完成后重试。CUDA 运行库错误才需切换 CPU。")
    completed = [i for i in items if i["status"] in FINISHED_STATUSES]
    if completed:
        with st.expander("校对字幕和文案", expanded=True):
            edit_id = st.selectbox("选择视频", [i["id"] for i in completed], format_func=lambda v: next(i["title"] for i in completed if i["id"] == v))
            item = next(i for i in completed if i["id"] == edit_id)
            edited_title = st.text_input("交付标题", value=item["title"], key="title_" + edit_id)
            if item["status"] == "无口播":
                st.info("此视频未检测到口播，交付文案为空。")
            st.caption("提取方式：" + item.get("text_origin", "口播转写"))
            st.caption("逐句编辑会同时更新 Word、Excel、TXT 和 SRT。时间单位为秒。")
            import pandas as pd
            edited = st.data_editor(pd.DataFrame(item["segments"], columns=["start", "end", "text"]), key="segments_" + edit_id, num_rows="dynamic", width="stretch")
            if st.button("保存校对"):
                try:
                    clean = [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"] or "").strip()} for s in edited.to_dict("records")]
                    import math
                    if any(not math.isfinite(s["start"]) or not math.isfinite(s["end"]) or s["start"] < 0 or s["end"] <= s["start"] or not s["text"] for s in clean):
                        raise ValueError("每句需有文字，时间需满足 0 ≤ 开始 < 结束。")
                    if any(clean[n]["start"] < clean[n - 1]["end"] for n in range(1, len(clean))):
                        raise ValueError("字幕时间须按顺序且不重叠。")
                    item["title"] = edited_title.strip() or item["title"]
                    item["segments"] = clean
                    item["text"] = transcript_paragraphs(clean)
                    item["status"] = "完成" if clean else "无口播"
                    save_order(order)
                    st.session_state.pop("export_" + selected, None)
                    st.success("校对已保存。")
                except (TypeError, ValueError, KeyError) as exc:
                    st.error(str(exc))
            if item["segments"] and st.button("确认无口播，清空此视频文案"):
                item.update(status="无口播", text="", segments=[], note="人工确认无口播", text_origin="口播转写")
                save_order(order)
                st.session_state.pop("export_" + selected, None)
                st.rerun()
        if st.button("生成交付包"):
            try:
                archive = export_order(order)
                st.session_state["export_" + selected] = str(archive)
            except Exception as exc:
                st.error(f"导出失败：{exc}")
        archive_path = st.session_state.get("export_" + selected)
        if archive_path and Path(archive_path).is_file() and Path(archive_path).parent.name == "delivery":
            st.download_button("下载交付 ZIP（含 Excel / Word / SRT / TXT）", Path(archive_path).read_bytes(), file_name=Path(archive_path).name, mime="application/zip")
            st.caption("修改字幕或新增视频后，请重新生成交付包。")
