"""Download models once for subsequent offline use by the workbench."""
import argparse
from pathlib import Path
from faster_whisper.utils import download_model

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="下载视频文案工作台的本地模型")
    parser.add_argument("--model", choices=["tiny", "small", "medium", "large-v3"], default="small")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent / "models" / args.model
    download_model(args.model, output_dir=str(folder))
    print(f"模型下载完成：{folder}")
