import subprocess
import sys
from pathlib import Path

# 此腳本在已啟用的 .venv 中執行，負責安裝 TripoSR 相關相依
# - 暫時切換為 CPU 版 torch/vision/audio 以便編譯 torchmcubes
# - 放寬 transformers 版本，確保 Python 3.12 有可用的 tokenizers 輪檔
# - 安裝 requirements.txt 中的其餘相依
# - 確保 gradio 存在（GUI 介面用）
# - 最後再將 torch/vision/audio 切換回 CUDA 版，供推論使用

PROJECT_DIR = Path(__file__).resolve().parent
TRIPOSR_DIR = PROJECT_DIR / "vendor" / "TripoSR"
REQ_FILE = TRIPOSR_DIR / "requirements.txt"
TORCHMCUBES_MARKER = PROJECT_DIR / ".torchmcubes_built"


def run(cmd: list[str]) -> int:
    """以目前 Python 進程執行子命令，直接轉印輸出。"""
    return subprocess.call(cmd)


def patch_requirements() -> None:
    """調整上游 TripoSR 的 requirements.txt，避免不相容的版本限制。

    目前主要處理：
    - 若存在 transformers==4.35.0，改為 transformers>=4.39.0，
      以避免拉到需要 Rust/Cargo 的舊 tokenizers 版本。
    """
    if not REQ_FILE.exists():
        return

    try:
        text = REQ_FILE.read_text(encoding="utf-8")
    except Exception:
        # 若讀取失敗就略過，維持上游原樣，避免阻斷安裝流程
        return

    original = text
    text = text.replace("transformers==4.35.0", "transformers>=4.39.0")

    if text != original:
        try:
            REQ_FILE.write_text(text, encoding="utf-8")
            print("[INFO] Patched requirements.txt to use transformers>=4.39.0 instead of 4.35.0.")
        except Exception:
            # 寫入失敗時也不終止流程，只是保留原設定
            print("[WARN] Failed to patch requirements.txt; using upstream transformers pin.")


def main() -> int:
    if not REQ_FILE.exists():
        print(f"[ERROR] requirements.txt not found at {REQ_FILE}")
        return 1

    # 先修正上游 requirements 中已知會造成安裝問題的版本限制
    patch_requirements()

    # 若已經成功編譯並可匯入 torchmcubes，則跳過之後昂貴的 torch 重安裝步驟
    skip_torch_reinstall = False
    if TORCHMCUBES_MARKER.exists():
        skip_torch_reinstall = True
        print("[INFO] torchmcubes marker found; skipping torch CPU/CUDA reinstall steps.")

    if not skip_torch_reinstall:
        # 先安裝 CPU 版 torch/vision/audio，避免 torchmcubes 受到 CUDA 版 torch 影響
        # 使用 --force-reinstall 與 --no-deps，強制覆蓋現有 CUDA 版本但不動其餘相依。
        print("[INFO] Installing CPU build of torch/vision/audio to build torchmcubes (force reinstall)...")
        rc = run([
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-deps",
            "torch",
            "torchvision",
            "torchaudio",
            "--index-url",
            "https://download.pytorch.org/whl/cpu",
        ])
        if rc != 0:
            print("[ERROR] Failed to install CPU build of torch/vision/audio.")
            return rc

    # 安裝相容於 Python 3.12 的 transformers/tokenizers
    print("[INFO] Installing compatible transformers/tokenizers for Python 3.12...")
    rc = run([sys.executable, "-m", "pip", "install", "transformers>=4.39.0", "tokenizers>=0.15.0"])
    if rc != 0:
        print("[WARN] Failed to pre-install transformers/tokenizers; continuing anyway.")

    # 安裝 TripoSR 其餘 requirements
    print("[INFO] Installing requirements from requirements.txt...")
    rc = run([sys.executable, "-m", "pip", "install", "-r", str(REQ_FILE)])
    if rc != 0:
        print("[ERROR] Failed to install TripoSR dependencies from requirements.txt.")
        return rc

    # 若 torchmcubes 可成功匯入，寫入 marker 檔，避免之後重跑時一再重裝 torch
    try:
        import torchmcubes  # type: ignore

        TORCHMCUBES_MARKER.write_text("ok", encoding="utf-8")
        print("[INFO] torchmcubes import successful; marker file created.")
    except Exception:
        print("[WARN] torchmcubes import failed after installation; fallback implementation may be used.")

    # rembg 需要 onnxruntime 作為推論 backend
    print("[INFO] Ensuring onnxruntime is installed for rembg...")
    rc = run([sys.executable, "-m", "pip", "install", "onnxruntime"])
    if rc != 0:
        print("[WARN] Failed to install onnxruntime; rembg may not work correctly.")

    # 確保 gradio 安裝完成
    print("[INFO] Ensuring gradio is installed...")
    rc = run([sys.executable, "-m", "pip", "install", "gradio"])
    if rc != 0:
        print("[ERROR] Failed to install gradio.")
        return rc

    # 最後將 torch/vision/audio 切回 CUDA 版，供推論使用
    # 同樣使用 --force-reinstall 與 --no-deps，確保最終為 CUDA 版。
    if not skip_torch_reinstall:
        print("[INFO] Re-installing CUDA (cu121) build of torch/vision/audio for GPU inference (force reinstall)...")
        rc = run([
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-deps",
            "torch",
            "torchvision",
            "torchaudio",
            "--index-url",
            "https://download.pytorch.org/whl/cu121",
        ])
        if rc != 0:
            print("[WARN] Failed to install CUDA build of torch/vision/audio. CPU build will be used.")

    # 最後一步：強制安裝與 trimesh 相容的 NumPy 版本，避免被其他套件升級到 2.x
    print("[INFO] Force-reinstalling NumPy (<2.0) for trimesh compatibility (no deps)...")
    rc = run([
        sys.executable,
        "-m",
        "pip",
        "install",
        "--force-reinstall",
        "--no-deps",
        "numpy<2.0",
    ])
    if rc != 0:
        print("[ERROR] Failed to force-reinstall compatible NumPy (<2.0).")
        return rc

    print("[INFO] Dependency setup completed by tr_setup_deps.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
