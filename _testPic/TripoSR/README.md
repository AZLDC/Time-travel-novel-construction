# TripoSR 本地封閉式專案（Windows）

此資料夾提供一鍵建立虛擬環境與執行 TripoSR 的腳本：
- `setup_env.bat`：建立 `.venv` 並安裝必要套件、下載 TripoSR 原始碼
- `run_gradio.bat`：啟動 TripoSR 官方 Gradio 介面（瀏覽器 GUI）
- `run_cli.bat`：以命令列對單張影像進行推論，輸出 3D 模型

> 預設安裝 PyTorch CPU 版，若你有支援 CUDA 的顯示卡，建議改為對應 CUDA 版本的 PyTorch 以加速。

## 需求
- Windows 10/11
- Python 3.8 ~ 3.11（建議 3.10/3.11）已加入 PATH
- Git（用於抓取 TripoSR 原始碼）
- （可選）NVIDIA GPU + 對應 CUDA（見下方說明）
- 可能需要 Microsoft C++ Build Tools（`torchmcubes` 需原生編譯）
  - 下載：https://visualstudio.microsoft.com/visual-cpp-build-tools/
  - 安裝「使用 C++ 的桌面開發」工作負載（含 MSVC、Windows SDK）

## 一鍵安裝
1. 先執行 `setup_env.bat`
   - 建立 `.venv` 虛擬環境
   - 下載 TripoSR 原始碼到 `vendor/TripoSR`
   - 安裝 PyTorch（CPU 版）與 TripoSR 依賴
2. 安裝成功後，執行下列任一：
   - `run_gradio.bat` 啟動瀏覽器 GUI
   - `run_cli.bat input\你的圖片.png` 以命令列推論

## CUDA（選用，加速）
- 預設腳本安裝的是 CPU 版 PyTorch。
- 若要改用 CUDA：
  1. 先解除安裝 CPU 版：
     ```bat
     .venv\Scripts\activate.bat
     pip uninstall -y torch torchvision torchaudio
     ```
  2. 依你的 CUDA 版本從官網安裝對應輪檔：https://pytorch.org/get-started/locally/
     例如（CUDA 12.x 範例）：
     ```bat
     pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
     ```
  3. 確保系統安裝的 CUDA 大版本與 PyTorch 封裝的 CUDA 大版本一致。

## 使用方式
- GUI：
  - 執行 `run_gradio.bat`
  - 依介面上傳單張圖片，等待輸出 3D（可選 `--bake-texture` 類功能已內建於介面）
- 命令列：
  - 範例（無參數會使用官方範例圖片）：
    ```bat
    run_cli.bat input\chair.png
    ```
  - 成功後模型輸出在 `output/`

## 常見問題
- `torchmcubes` 安裝失敗
  - 安裝 Microsoft C++ Build Tools（見上方連結），並重試 `setup_env.bat`
  - 確保 Python 與 pip 為 64 位元
- 速度慢
  - 改用 CUDA 版 PyTorch（見上方 CUDA 區段）
- 需要離線
  - 第一次執行會從 Hugging Face 下載模型權重，完成後可離線重複使用

## 結構
```
TripoSR/
  setup_env.bat
  run_gradio.bat
  run_cli.bat
  README.md
  vendor/
    TripoSR/  (自動下載的上游原始碼)
  input/      (可自建，放輸入影像)
  output/     (輸出 3D 模型)
  .venv/      (本地虛擬環境)
```
