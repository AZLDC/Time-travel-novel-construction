import json
import math
import os
import subprocess
import sys
import threading
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

# 以 2 的指數控制範圍，方便後續統一管理滑桿與 clamp 邏輯
MC_RES = [6, 9]      # 對應 mc-resolution 最小/最大值（2^6~2^9）
CH_SIZE = [4, 13]    # 對應 chunk_size 最小/最大值（2^4~2^13）
TX_RES = [8, 12]     # 對應 texture_resolution 最小/最大值（2^8~2^12）

# 預設值對應各範圍的較保守高值
DEFAULT_MC_RES = 2 ** MC_RES[1]
DEFAULT_CHUNK_SIZE = 2 ** CH_SIZE[0]  # chunk 預設偏保守，避免一開始過度吃記憶體
DEFAULT_TEXTURE_RES = 2 ** 10         # 1024，介於 TX_RES 範圍中間


def _detect_total_vram() -> int:
    try:
        import torch

        if not torch.cuda.is_available():
            return 0
        try:
            props = torch.cuda.get_device_properties(0)
            return int(getattr(props, "total_memory", 0))
        except Exception:
            return 0
    except Exception:
        return 0


def _collect_images(input_path: Path) -> list[str]:
    """收集要送給 TripoSR 的影像路徑清單。"""
    if input_path.is_file():
        return [str(input_path)]
    if input_path.is_dir():
        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        files = [str(p) for p in sorted(input_path.iterdir()) if p.suffix.lower() in exts]
        return files
    return []


def run_triposr(
    input_path: str,
    output_dir: str,
    mc_resolution: int,
    bake_texture: bool,
    chunk_size: int,
    texture_resolution: int,
    preview_mode: str,
    render_flag: bool,
    status_callback=None,
) -> int:
    """呼叫 TripoSR 的 CLI 腳本執行推論。

    若提供 status_callback，會在偵測到特定日誌訊息時呼叫它，以便更新 GUI 狀態。
    """
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
        "--output-dir", output_dir,
        "--mc-resolution", str(mc_resolution),
    ]

    # 僅在未啟用烘焙貼圖時使用 glb 輸出，避免與 xatlas.export 產生不相容格式
    if not bake_texture:
        cmd.extend(["--model-save-format", "glb"])

    # 調整 chunk-size 以在速度與記憶體用量之間取得平衡
    if chunk_size > 0:
        cmd.extend(["--chunk-size", str(chunk_size)])

    if bake_texture:
        # 為避免烘焙貼圖時 GPU/CPU 混用導致 device mismatch，強制使用 CPU 裝置
        cmd.append("--bake-texture")
        cmd.extend(["--device", "cpu"])
        cmd.extend(["--texture-resolution", str(texture_resolution)])

    # 控制是否輸出 NeRF 預覽渲染與影片 (--render)
    if render_flag:
        cmd.append("--render")

    # 若有提供狀態回呼，串流讀取 stdout 並轉發關鍵狀態文字
    env = os.environ.copy()
    # 將專案目錄加入 PYTHONPATH 最前端，確保優先載入本地的 torchmcubes.py wrapper
    env["PYTHONPATH"] = str(PROJECT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    
    if status_callback is not None:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        if proc.stdout is not None:
            for raw_line in proc.stdout:
                # 先將原始輸出直接印到終端機，方便偵錯與查看完整錯誤訊息
                print(raw_line, end="")

                line = raw_line.strip()
                if "Processing images ..." in line:
                    status_callback("Processing images ...")
                elif "Running image" in line and "..." in line:
                    status_callback("Running image 1/1 ...")
                elif "Running model ..." in line:
                    status_callback("Running model ...")
                elif "Extracting mesh ..." in line:
                    status_callback("Extracting mesh ...")
                elif "Baking texture ..." in line:
                    status_callback("Baking texture ...")
                elif "Exporting mesh and texture finished" in line:
                    status_callback(line)
                elif "Exporting mesh and texture ..." in line:
                    status_callback("Exporting mesh and texture ...")
        return proc.wait()

    # 未提供回呼時維持原本行為
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(cmd, env=env)
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


def _save_prefs(
    input_path: str,
    output_dir: str,
    mc_resolution: int,
    bake_texture: bool,
    chunk_size: int,
    texture_resolution: int,
    preview_delete: bool,
    render_flag: bool,
    safe_mode: bool,
) -> None:
    """儲存這次使用的參數設定到 mem.sav。"""
    data = {
        "input_path": input_path,
        "output_dir": output_dir,
        "mc_resolution": mc_resolution,
        "bake_texture": bake_texture,
        "chunk_size": chunk_size,
        "texture_resolution": texture_resolution,
        "preview_delete": preview_delete,
        "render": render_flag,
        "safe_mode": safe_mode,
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
        self.geometry("760x340")

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.bake_texture_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="待命中")
        # 是否在處理完成後自動刪除預覽圖 input.png
        self.preview_delete_var = tk.BooleanVar(value=False)
        # 是否輸出 NeRF 渲染與旋轉影片 (--render)
        self.render_var = tk.BooleanVar(value=False)
        # 低記憶體安全模式：啟用時會強制採用保守參數組合
        self.safe_mode_var = tk.BooleanVar(value=False)
        # mc-resolution 以 2 的指數形式控制：exp in [MC_RES[0], MC_RES[1]]
        self.mc_exp_var = tk.IntVar(value=int(math.log2(DEFAULT_MC_RES)))
        self.mc_res_var = tk.IntVar(value=DEFAULT_MC_RES)
        # chunk-size 以 2 的指數形式控制：exp in [CH_SIZE[0], CH_SIZE[1]]
        self.chunk_exp_var = tk.IntVar(value=int(math.log2(DEFAULT_CHUNK_SIZE)))
        self.chunk_size_var = tk.IntVar(value=DEFAULT_CHUNK_SIZE)
        # texture-resolution 以 2 的指數形式控制：exp in [TX_RES[0], TX_RES[1]]
        self.tex_exp_var = tk.IntVar(value=int(math.log2(DEFAULT_TEXTURE_RES)))
        self.texture_res_var = tk.IntVar(value=DEFAULT_TEXTURE_RES)

        # 嘗試載入上次的設定
        prefs = _load_prefs()
        if "input_path" in prefs:
            self.input_var.set(str(prefs.get("input_path", "")))
        if "output_dir" in prefs:
            self.output_var.set(str(prefs.get("output_dir", "")))
        if "bake_texture" in prefs:
            self.bake_texture_var.set(bool(prefs.get("bake_texture", True)))
        if "mc_resolution" in prefs:
            try:
                loaded_mc = int(prefs.get("mc_resolution", DEFAULT_MC_RES))
                self.mc_res_var.set(loaded_mc)
                if loaded_mc > 0:
                    mc_exp = int(round(math.log2(loaded_mc)))
                    mc_exp = max(MC_RES[0], min(MC_RES[1], mc_exp))
                    self.mc_exp_var.set(mc_exp)
                else:
                    self.mc_exp_var.set(int(math.log2(DEFAULT_MC_RES)))
            except Exception:
                self.mc_res_var.set(DEFAULT_MC_RES)
                self.mc_exp_var.set(int(math.log2(DEFAULT_MC_RES)))
        if "chunk_size" in prefs:
            try:
                loaded_chunk = int(prefs.get("chunk_size", DEFAULT_CHUNK_SIZE))
                self.chunk_size_var.set(loaded_chunk)
                # 嘗試從實際值反推回指數，限制在 CH_SIZE 範圍內
                if loaded_chunk > 0:
                    exp = int(round(math.log2(loaded_chunk)))
                    exp = max(CH_SIZE[0], min(CH_SIZE[1], exp))
                    self.chunk_exp_var.set(exp)
                else:
                    self.chunk_exp_var.set(int(math.log2(DEFAULT_CHUNK_SIZE)))
            except Exception:
                self.chunk_size_var.set(DEFAULT_CHUNK_SIZE)
                self.chunk_exp_var.set(int(math.log2(DEFAULT_CHUNK_SIZE)))
        if "texture_resolution" in prefs:
            try:
                loaded_tex = int(prefs.get("texture_resolution", DEFAULT_TEXTURE_RES))
                self.texture_res_var.set(loaded_tex)
                if loaded_tex > 0:
                    tex_exp = int(round(math.log2(loaded_tex)))
                    tex_exp = max(TX_RES[0], min(TX_RES[1], tex_exp))
                    self.tex_exp_var.set(tex_exp)
                else:
                    self.tex_exp_var.set(int(math.log2(DEFAULT_TEXTURE_RES)))
            except Exception:
                self.texture_res_var.set(DEFAULT_TEXTURE_RES)
                self.tex_exp_var.set(int(math.log2(DEFAULT_TEXTURE_RES)))
        if "preview_delete" in prefs:
            try:
                self.preview_delete_var.set(bool(prefs.get("preview_delete", False)))
            except Exception:
                self.preview_delete_var.set(False)
        if "render" in prefs:
            try:
                self.render_var.set(bool(prefs.get("render", False)))
            except Exception:
                self.render_var.set(False)
        if "safe_mode" in prefs:
            try:
                self.safe_mode_var.set(bool(prefs.get("safe_mode", False)))
            except Exception:
                self.safe_mode_var.set(False)

        # 來源路徑
        tk.Label(self, text="來源路徑 (圖片或資料夾)：").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        tk.Entry(self, textvariable=self.input_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(self, text="瀏覽...", command=self.browse_input).grid(row=0, column=2, padx=5, pady=5)

        # 輸出路徑
        tk.Label(self, text="輸出資料夾：").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        tk.Entry(self, textvariable=self.output_var, width=50).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(self, text="瀏覽...", command=self.browse_output).grid(row=1, column=2, padx=5, pady=5)

        # 網格解析度 (mc-resolution)，使用 2 的指數滑桿控制實際值
        tk.Label(self, text="網格解析度 (mc-resolution)：").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.mc_display_var = tk.StringVar()
        self.mc_scale = tk.Scale(
            self,
            from_=MC_RES[0],
            to=MC_RES[1],
            orient=tk.HORIZONTAL,
            resolution=1,
            length=260,
            variable=self.mc_exp_var,
            command=self._on_mc_exp_changed,
        )
        self.mc_scale.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        tk.Label(self, textvariable=self.mc_display_var).grid(
            row=2, column=2, sticky="w", padx=5, pady=5
        )

        # 運算切塊大小 (chunk-size)，使用 2 的指數滑桿控制實際值
        tk.Label(self, text="運算切塊 (chunk-size)：越小越省記憶體但較慢").grid(
            row=3, column=0, sticky="w", padx=10, pady=5
        )
        self.chunk_display_var = tk.StringVar()
        self.chunk_scale = tk.Scale(
            self,
            from_=CH_SIZE[0],
            to=CH_SIZE[1],
            orient=tk.HORIZONTAL,
            resolution=1,
            length=260,
            variable=self.chunk_exp_var,
            command=self._on_chunk_exp_changed,
        )
        self.chunk_scale.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        tk.Label(self, textvariable=self.chunk_display_var).grid(
            row=3, column=2, sticky="w", padx=5, pady=5
        )

        # 貼圖解析度 (texture-resolution)，使用 2 的指數滑桿控制實際值
        tk.Label(self, text="貼圖解析度 (texture-resolution)：越小越省記憶體").grid(
            row=4, column=0, sticky="w", padx=10, pady=5
        )
        self.tex_display_var = tk.StringVar()
        self.tex_scale = tk.Scale(
            self,
            from_=TX_RES[0],
            to=TX_RES[1],
            orient=tk.HORIZONTAL,
            resolution=1,
            length=260,
            variable=self.tex_exp_var,
            command=self._on_tex_exp_changed,
        )
        self.tex_scale.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        tk.Label(self, textvariable=self.tex_display_var).grid(
            row=4, column=2, sticky="w", padx=5, pady=5
        )

        # 是否烘焙貼圖與預覽圖刪除控制，包在同一個水平置中 Frame 中
        options_frame = tk.Frame(self)
        options_frame.grid(row=5, column=0, columnspan=3, pady=5)

        tk.Checkbutton(
            options_frame,
            text="烘焙貼圖 (bake texture)",
            variable=self.bake_texture_var,
            onvalue=True,
            offvalue=False,
        ).pack(side="left", padx=10)

        tk.Checkbutton(
            options_frame,
            text="處理完成後自動刪除預覽圖",
            variable=self.preview_delete_var,
            onvalue=True,
            offvalue=False,
        ).pack(side="left", padx=10)

        tk.Checkbutton(
            options_frame,
            text="輸出預覽渲染與影片 (--render)",
            variable=self.render_var,
            onvalue=True,
            offvalue=False,
        ).pack(side="left", padx=10)

        tk.Checkbutton(
            options_frame,
            text="低記憶體安全模式",
            variable=self.safe_mode_var,
            onvalue=True,
            offvalue=False,
        ).pack(side="left", padx=10)

        # 狀態顯示與執行按鈕，包在同一個水平置中 Frame 中
        actions_frame = tk.Frame(self)
        actions_frame.grid(row=6, column=0, columnspan=3, pady=15)

        tk.Label(actions_frame, textvariable=self.status_var).pack(side="left", padx=10)
        tk.Button(actions_frame, text="開始生成", command=self.on_run, width=20).pack(side="left", padx=10)

        # 初始化一次指數滑桿顯示文字
        self._on_mc_exp_changed(str(self.mc_exp_var.get()))
        self._on_chunk_exp_changed(str(self.chunk_exp_var.get()))
        self._on_tex_exp_changed(str(self.tex_exp_var.get()))

        self._auto_adjust_scales_by_vram()

    def _on_mc_exp_changed(self, value: str) -> None:
        """當 mc-resolution 的指數滑桿變動時，同步更新實際值與顯示文字。"""
        try:
            exp = int(float(value))
        except ValueError:
            exp = int(math.log2(DEFAULT_MC_RES))
        exp = max(MC_RES[0], min(MC_RES[1], exp))
        actual = 1 << exp
        self.mc_res_var.set(actual)
        self.mc_display_var.set(f"{actual} (2^{exp})")

    def _on_chunk_exp_changed(self, value: str) -> None:
        """當 chunk-size 的指數滑桿變動時，同步更新實際值與顯示文字。"""
        try:
            exp = int(float(value))
        except ValueError:
            exp = int(math.log2(DEFAULT_CHUNK_SIZE))
        exp = max(CH_SIZE[0], min(CH_SIZE[1], exp))
        actual = 1 << exp
        self.chunk_size_var.set(actual)
        self.chunk_display_var.set(f"{actual} (2^{exp})")

    def _on_tex_exp_changed(self, value: str) -> None:
        """當 texture-resolution 的指數滑桿變動時，同步更新實際值與顯示文字。"""
        try:
            exp = int(float(value))
        except ValueError:
            exp = int(math.log2(DEFAULT_TEXTURE_RES))
        exp = max(TX_RES[0], min(TX_RES[1], exp))
        actual = 1 << exp
        self.texture_res_var.set(actual)
        self.tex_display_var.set(f"{actual} (2^{exp})")

    def _auto_adjust_scales_by_vram(self) -> None:
        total_vram = _detect_total_vram()

        if total_vram <= 0:
            # 未偵測到 GPU 或查詢失敗，視為低資源環境
            new_mc_max = min(int(self.mc_scale["to"]), 8)
            new_chunk_max = min(int(self.chunk_scale["to"]), 11)
            new_tex_max = min(int(self.tex_scale["to"]), 10)
        elif total_vram <= 4 * 1024 ** 3:
            # 約 4GB 顯存：略微放寬貼圖，但仍限制網格與切塊
            new_mc_max = min(int(self.mc_scale["to"]), 8)
            new_chunk_max = min(int(self.chunk_scale["to"]), 11)
            new_tex_max = min(int(self.tex_scale["to"]), 11)
        else:
            # 大於 4GB 顯存一律視為中高階，但仍採較保守上限，避免隨意拉滿
            new_mc_max = min(int(self.mc_scale["to"]), 9)
            new_chunk_max = min(int(self.chunk_scale["to"]), 12)
            new_tex_max = min(int(self.tex_scale["to"]), 12)

        self.mc_scale.config(to=new_mc_max)
        self.chunk_scale.config(to=new_chunk_max)
        self.tex_scale.config(to=new_tex_max)

        if self.mc_exp_var.get() > new_mc_max:
            self.mc_exp_var.set(new_mc_max)
            self._on_mc_exp_changed(str(new_mc_max))
        if self.chunk_exp_var.get() > new_chunk_max:
            self.chunk_exp_var.set(new_chunk_max)
            self._on_chunk_exp_changed(str(new_chunk_max))
        if self.tex_exp_var.get() > new_tex_max:
            self.tex_exp_var.set(new_tex_max)
            self._on_tex_exp_changed(str(new_tex_max))

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

        # 從滑桿與輸入取得解析度與資源相關參數
        # 這三個變數已由指數滑桿回呼函式換算為實際值
        mc_res = int(self.mc_res_var.get())
        bake_tex = bool(self.bake_texture_var.get())
        chunk_size = int(self.chunk_size_var.get())
        texture_res = int(self.texture_res_var.get())
        preview_delete = bool(self.preview_delete_var.get())
        render_flag = bool(self.render_var.get())
        safe_mode = bool(self.safe_mode_var.get())

        # 單一勾選：未勾選時保持原行為 (keep)，勾選時改為 delete
        preview_mode = "delete" if preview_delete else "keep"

        # 若啟用低記憶體安全模式，先將參數壓到更保守的範圍，並關閉 render
        if safe_mode:
            # 這組參數偏向避免資源尖峰，而非追求速度與品質
            mc_res = min(mc_res, 96)
            chunk_size = min(chunk_size, 128)
            texture_res = min(texture_res, 512)
            render_flag = False
            # 回寫到變數與 UI，以便使用者看到實際生效值
            self.mc_res_var.set(mc_res)
            self.chunk_size_var.set(chunk_size)
            self.texture_res_var.set(texture_res)
            self.render_var.set(False)

        total_vram = _detect_total_vram()
        adjusted = False

        if total_vram <= 0:
            if chunk_size > 4096:
                chunk_size = 4096
                adjusted = True
            if mc_res > 256:
                mc_res = 256
                adjusted = True
            if texture_res > 1024:
                texture_res = 1024
                adjusted = True
        elif total_vram <= 4 * 1024 ** 3:
            if chunk_size > 4096:
                chunk_size = 4096
                adjusted = True
            if mc_res > 256:
                mc_res = 256
                adjusted = True
            if texture_res > 2048:
                texture_res = 2048
                adjusted = True
        elif total_vram <= 8 * 1024 ** 3:
            if chunk_size > 8192:
                chunk_size = 8192
                adjusted = True
            if mc_res > 512:
                mc_res = 512
                adjusted = True

        if adjusted:
            self.mc_res_var.set(mc_res)
            self.chunk_size_var.set(chunk_size)
            self.texture_res_var.set(texture_res)

            confirm = messagebox.askyesno(
                "參數已自動調整",
                "偵測到可用顯示記憶體較低，系統已自動將解析度與切塊大小下修為較安全的數值，\n\n"
                f"mc-resolution: {mc_res}\n"
                f"chunk-size: {chunk_size}\n"
                f"texture-resolution: {texture_res}\n\n"
                "是否仍要以這些設定繼續執行？",
            )
            if not confirm:
                # 使用者選擇取消這次執行，直接中止流程
                self.status_var.set("已取消：使用者中止本次執行。")
                return

        # 綜合負載檢查：避免三個高值相乘導致 GPU 過載
        # 以較安全的基準組合做相對倍率估算，超過一定倍數就提示高風險
        base_mc = 128
        base_chunk = 512
        base_tex = 512

        load_score = (
            (mc_res / base_mc)
            * (max(chunk_size, 1) / base_chunk)
            * (max(texture_res, base_tex) / base_tex)
        )

        if load_score > 4.0:
            high_risk = messagebox.askyesno(
                "高風險設定警告",
                "目前的 mc-resolution、chunk-size、texture-resolution 組合推估 GPU 負載遠高於建議值，\n"
                "有可能導致系統長時間無回應或當機。\n\n"
                f"mc-resolution: {mc_res}\n"
                f"chunk-size: {chunk_size}\n"
                f"texture-resolution: {texture_res}\n\n"
                "建議先下修參數後再執行。是否仍要強制繼續？",
            )
            if not high_risk:
                self.status_var.set("已取消：偵測到高風險設定，使用者中止本次執行。")
                return

        # 在開始執行前就先儲存目前設定，避免後續卡住時遺失輸入
        _save_prefs(
            input_path,
            output_dir,
            mc_res,
            bake_tex,
            chunk_size,
            texture_res,
            preview_delete,
            render_flag,
            safe_mode,
        )

        # 更新狀態為執行中
        if bake_tex:
            self.status_var.set("執行中：可能正在前處理、推論、mesh 抽取或烘焙貼圖...")
        else:
            self.status_var.set("執行中：可能正在前處理、推論或 mesh 抽取...")

        self.disable_ui()
        self.after(
            100,
            self._run_triposr_async,
            input_path,
            output_dir,
            mc_res,
            bake_tex,
            chunk_size,
            texture_res,
            preview_mode,
            render_flag,
        )

    def _run_triposr_async(
        self,
        input_path: str,
        output_dir: str,
        mc_resolution: int,
        bake_texture: bool,
        chunk_size: int,
        texture_resolution: int,
        preview_mode: str,
        render_flag: bool,
    ) -> None:
        """在背景執行緒中呼叫 TripoSR，避免卡住主執行緒。"""

        def worker() -> None:
            def status_cb(msg: str) -> None:
                # 依照日誌訊息轉換為較易懂的步驟說明，並排回主執行緒更新
                text = msg
                print(msg)
                if msg.startswith("Processing images"):
                    text = "Step 1 圖片前處理中..."
                elif msg.startswith("Running image"):
                    text = "Step 2 正在準備 3D 場景 (Running image 1/1)..."
                elif msg.startswith("Running model"):
                    text = "Step 3 模型推論中 (Running model)..."
                elif msg.startswith("Extracting mesh"):
                    text = "Step 4 正在抽取 mesh..."
                elif msg.startswith("Baking texture"):
                    text = "Step 5 正在烘焙貼圖..."
                elif msg.startswith("Exporting mesh and texture finished"):
                    text = f"Step 7 匯出完成：{msg}"
                elif msg.startswith("Exporting mesh and texture"):
                    text = "Step 6 正在匯出 mesh 與貼圖..."

                self.after(0, lambda: self.status_var.set(text))

            rc = run_triposr(
                input_path,
                output_dir,
                mc_resolution,
                bake_texture,
                chunk_size,
                texture_resolution,
                preview_mode,
                render_flag,
                status_callback=status_cb,
            )

            def on_done() -> None:
                if rc == 0:
                    # 若使用者選擇刪除預覽圖，於本地輸出資料夾中清理 input.png
                    if preview_mode == "delete":
                        try:
                            out_root = Path(output_dir)
                            # 單一影像輸出路徑下可能直接有 input.png
                            single_preview = out_root / "input.png"
                            if single_preview.is_file():
                                try:
                                    single_preview.unlink()
                                except OSError:
                                    pass

                            # 多張影像時，TripoSR 會在 output_dir/索引 底下寫入 input.png
                            for sub in out_root.iterdir():
                                if not sub.is_dir():
                                    continue
                                p = sub / "input.png"
                                if p.is_file():
                                    try:
                                        p.unlink()
                                    except OSError:
                                        # 刪除失敗不影響主流程
                                        continue
                        except Exception:
                            # 任何刪除錯誤皆不影響主流程
                            pass

                    self.status_var.set("完成：TripoSR 處理完成。")
                    messagebox.showinfo("完成", "TripoSR 處理完成。")
                else:
                    self.status_var.set(f"發生錯誤：代碼 {rc}")
                    messagebox.showerror("錯誤", f"TripoSR 執行失敗，代碼: {rc}")
                self.enable_ui()

            # 將 UI 更新排回主執行緒
            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def disable_ui(self) -> None:
        for child in self.winfo_children():
            # 僅對支援 state 選項的元件進行啟用/停用
            try:
                if "state" in child.keys():
                    child.configure(state="disabled")
            except Exception:
                # 某些自訂或特殊元件可能不支援 keys()/configure，略過即可
                continue

    def enable_ui(self) -> None:
        for child in self.winfo_children():
            try:
                if "state" in child.keys():
                    child.configure(state="normal")
            except Exception:
                continue


if __name__ == "__main__":
    app = SimpleGUI()
    app.mainloop()
