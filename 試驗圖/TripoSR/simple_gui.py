import json
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

# 簡易 TripoSR GUI 工具
# - 只選擇來源圖片資料夾或單一圖片
# - 選擇輸出資料夾
# - 按一下按鈕後呼叫 vendor/TripoSR/run.py 執行推論

PROJECT_DIR = Path(__file__).resolve().parent
TRIPOSR_RUN = PROJECT_DIR / "vendor" / "TripoSR" / "run.py"
PREF_PATH = PROJECT_DIR / "mem.sav"
DEFAULT_MC_RES = 256


def _collect_images(input_path: Path) -> list[str]:
    """收集要送給 TripoSR 的影像路徑清單。"""
    if input_path.is_file():
        return [str(input_path)]
    if input_path.is_dir():
        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        files = [str(p) for p in sorted(input_path.iterdir()) if p.suffix.lower() in exts]
        return files
    return []


def run_triposr(input_path: str, output_dir: str, mc_resolution: int, bake_texture: bool) -> int:
    """呼叫 TripoSR 的 CLI 腳本執行推論。"""
    if not TRIPOSR_RUN.is_file():
        messagebox.showerror("Error", f"TripoSR run.py not found: {TRIPOSR_RUN}")
        return 1

    images = _collect_images(Path(input_path))
    if not images:
        messagebox.showerror("Error", "來源路徑中沒有找到可用的圖片檔案。")
        return 1

    cmd = [
        sys.executable,
        str(TRIPOSR_RUN),
        *images,
        "--output-dir",
        output_dir,
        "--mc-resolution",
        str(mc_resolution),
    ]

    if bake_texture:
        # 為避免烘焙貼圖時 GPU/CPU 混用導致 device mismatch，強制使用 CPU 裝置
        cmd.append("--bake-texture")
        cmd.extend(["--device", "cpu"])

    proc = subprocess.Popen(cmd)
    return proc.wait()


def _load_prefs() -> dict:
    """載入上次使用的參數設定。"""
    if not PREF_PATH.is_file():
        return {}
    try:
        data = json.loads(PREF_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_prefs(input_path: str, output_dir: str, mc_resolution: int, bake_texture: bool) -> None:
    """儲存這次使用的參數設定到 mem.sav。"""
    data = {
        "input_path": input_path,
        "output_dir": output_dir,
        "mc_resolution": mc_resolution,
        "bake_texture": bake_texture,
    }
    try:
        PREF_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # 儲存偏好失敗不影響主流程
        pass


class SimpleGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("TripoSR Simple GUI")
        self.geometry("610x230")

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.bake_texture_var = tk.BooleanVar(value=True)

        # 嘗試載入上次的設定
        prefs = _load_prefs()
        if "input_path" in prefs:
            self.input_var.set(str(prefs.get("input_path", "")))
        if "output_dir" in prefs:
            self.output_var.set(str(prefs.get("output_dir", "")))
        if "bake_texture" in prefs:
            self.bake_texture_var.set(bool(prefs.get("bake_texture", True)))

        # 來源路徑
        tk.Label(self, text="來源路徑 (圖片或資料夾)：").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        tk.Entry(self, textvariable=self.input_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(self, text="瀏覽...", command=self.browse_input).grid(row=0, column=2, padx=5, pady=5)

        # 輸出路徑
        tk.Label(self, text="輸出資料夾：").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        tk.Entry(self, textvariable=self.output_var, width=50).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(self, text="瀏覽...", command=self.browse_output).grid(row=1, column=2, padx=5, pady=5)

        # 網格解析度 (mc-resolution) 使用滑桿選擇，避免輸入錯誤
        tk.Label(self, text="網格解析度 (mc-resolution)：").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.mc_res_scale = tk.Scale(
            self,
            from_=64,
            to=512,
            orient=tk.HORIZONTAL,
            resolution=32,
            length=260,
        )
        # 若有記錄上次解析度則套用，否則使用預設值
        mc_res_pref = prefs.get("mc_resolution") if isinstance(prefs, dict) else None
        if isinstance(mc_res_pref, int) and 64 <= mc_res_pref <= 512:
            self.mc_res_scale.set(mc_res_pref)
        else:
            self.mc_res_scale.set(DEFAULT_MC_RES)
        self.mc_res_scale.grid(row=2, column=1, columnspan=2, sticky="w", padx=5, pady=5)

        # 是否烘焙貼圖 (bake texture)
        tk.Checkbutton(
            self,
            text="烘焙貼圖 (bake texture)",
            variable=self.bake_texture_var,
            onvalue=True,
            offvalue=False,
        ).grid(row=3, column=1, columnspan=2, sticky="w", padx=5, pady=5)

        # 執行按鈕
        tk.Button(self, text="開始生成", command=self.on_run, width=20).grid(row=4, column=1, pady=15)

    def browse_input(self) -> None:
        # 允許選擇單一圖片或整個資料夾
        path = filedialog.askopenfilename(title="選擇來源圖片")
        if not path:
            # 若未選擇檔案，可讓使用者改選整個資料夾
            dir_path = filedialog.askdirectory(title="或選擇來源資料夾")
            if dir_path:
                self.input_var.set(dir_path)
        else:
            self.input_var.set(path)

    def browse_output(self) -> None:
        path = filedialog.askdirectory(title="選擇輸出資料夾")
        if path:
            self.output_var.set(path)

    def on_run(self) -> None:
        input_path = self.input_var.get().strip()
        output_dir = self.output_var.get().strip()

        if not input_path:
            messagebox.showwarning("Warning", "請先選擇來源圖片路徑。")
            return
        if not output_dir:
            messagebox.showwarning("Warning", "請先選擇輸出資料夾。")
            return

        # 從滑桿取得網格解析度（已限制在安全範圍）
        mc_res = int(self.mc_res_scale.get())
        bake_tex = bool(self.bake_texture_var.get())

        # 在開始執行前就先儲存目前設定，避免後續卡住時遺失輸入
        _save_prefs(input_path, output_dir, mc_res, bake_tex)

        self.disable_ui()
        self.after(100, self._run_triposr_async, input_path, output_dir, mc_res, bake_tex)

    def _run_triposr_async(self, input_path: str, output_dir: str, mc_resolution: int, bake_texture: bool) -> None:
        rc = run_triposr(input_path, output_dir, mc_resolution, bake_texture)
        if rc == 0:
            messagebox.showinfo("完成", "TripoSR 處理完成。")
        else:
            messagebox.showerror("錯誤", f"TripoSR 執行失敗，代碼: {rc}")
        self.enable_ui()

    def disable_ui(self) -> None:
        for child in self.winfo_children():
            child.configure(state="disabled")

    def enable_ui(self) -> None:
        for child in self.winfo_children():
            child.configure(state="normal")


if __name__ == "__main__":
    app = SimpleGUI()
    app.mainloop()
