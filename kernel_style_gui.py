#!/usr/bin/env python3
"""
kernel_style_gui.py — Linux 内核编码风格修改器 (GUI 版本)

基于 tkinter 的图形界面，支持目录选择、预览差异、一键修复。
可由 PyInstaller 打包为独立 .exe 文件。

用法:
    python kernel_style_gui.py
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

# 导入核心修复逻辑
from kernel_style import apply_fixes, find_c_files, check_line_length, check_naming_convention


# ============================================================
# 颜色主题
# ============================================================

THEME = {
    "bg":          "#1e1e2e",    # 主背景
    "surface":     "#313244",    # 卡片/面板背景
    "text":        "#cdd6f4",    # 主文字
    "text_dim":    "#6c7086",    # 次要文字
    "accent":      "#89b4fa",    # 主题色（蓝）
    "green":       "#a6e3a1",    # 成功/添加
    "red":         "#f38ba8",    # 错误/删除
    "yellow":      "#f9e2af",    # 警告
    "peach":       "#fab387",    # 次要按钮
    "overlay":     "#45475a",    # 边框/分隔线
    "input_bg":    "#45475a",    # 输入框背景
}


class KernelStyleGUI:
    """主窗口。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Linux 内核编码风格修改器")
        self.root.geometry("960x720")
        self.root.minsize(800, 600)
        self.root.configure(bg=THEME["bg"])

        # 设置图标（如果有）
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self._running = False  # 防止重复执行
        self._build_ui()

    # ============================================================
    # UI 构建
    # ============================================================

    def _build_ui(self):
        """构建整个界面。"""
        self._build_title()
        self._build_directory_panel()
        self._build_options_panel()
        self._build_buttons()
        self._build_log_area()
        self._build_status_bar()

    def _build_title(self):
        """标题栏。"""
        frame = tk.Frame(self.root, bg=THEME["bg"])
        frame.pack(fill="x", padx=20, pady=(16, 4))

        tk.Label(
            frame, text="🐧 Linux 内核编码风格修改器",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg=THEME["accent"], bg=THEME["bg"],
        ).pack(side="left")

        tk.Label(
            frame, text="v1.0",
            font=("Consolas", 10),
            fg=THEME["text_dim"], bg=THEME["bg"],
        ).pack(side="left", padx=(8, 0), pady=(8, 0))

    def _build_directory_panel(self):
        """目录选择面板。"""
        frame = tk.Frame(self.root, bg=THEME["surface"], padx=12, pady=10)
        frame.pack(fill="x", padx=20, pady=(8, 4))

        tk.Label(
            frame, text="📁 目标目录",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg=THEME["text"], bg=THEME["surface"],
        ).pack(anchor="w")

        row = tk.Frame(frame, bg=THEME["surface"])
        row.pack(fill="x", pady=(6, 0))

        self.dir_var = tk.StringVar()
        entry = tk.Entry(
            row, textvariable=self.dir_var,
            font=("Consolas", 11),
            fg=THEME["text"], bg=THEME["input_bg"],
            insertbackground=THEME["text"],
            relief="flat", bd=0,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=5)

        btn = tk.Button(
            row, text="浏览...", font=("Microsoft YaHei UI", 10),
            fg=THEME["text"], bg=THEME["overlay"],
            activebackground=THEME["accent"], activeforeground=THEME["bg"],
            relief="flat", cursor="hand2", padx=16, pady=4,
            command=self._browse_directory,
        )
        btn.pack(side="right", padx=(8, 0))

    def _build_options_panel(self):
        """选项面板。"""
        frame = tk.Frame(self.root, bg=THEME["surface"], padx=12, pady=10)
        frame.pack(fill="x", padx=20, pady=4)

        tk.Label(
            frame, text="⚙ 选项",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg=THEME["text"], bg=THEME["surface"],
        ).pack(anchor="w")

        opts_frame = tk.Frame(frame, bg=THEME["surface"])
        opts_frame.pack(fill="x", pady=(6, 0))

        # 左列
        left = tk.Frame(opts_frame, bg=THEME["surface"])
        left.pack(side="left", fill="y")

        self.var_recursive = tk.BooleanVar(value=True)
        self._make_check(left, "递归子目录", self.var_recursive)

        self.var_backup = tk.BooleanVar(value=True)
        self._make_check(left, "创建 .bak 备份", self.var_backup)

        self.var_verbose = tk.BooleanVar(value=False)
        self._make_check(left, "详细模式（行长度/命名警告）", self.var_verbose)

        # 右列
        right = tk.Frame(opts_frame, bg=THEME["surface"])
        right.pack(side="left", padx=(40, 0), fill="y")

        tk.Label(
            right, text="文件扩展名:",
            font=("Microsoft YaHei UI", 10),
            fg=THEME["text_dim"], bg=THEME["surface"],
        ).pack(anchor="w")

        self.var_extensions = tk.StringVar(value=".c .h")
        ext_entry = tk.Entry(
            right, textvariable=self.var_extensions,
            font=("Consolas", 10),
            fg=THEME["text"], bg=THEME["input_bg"],
            insertbackground=THEME["text"],
            relief="flat", bd=0, width=20,
        )
        ext_entry.pack(anchor="w", ipady=3, pady=(2, 0))

    def _build_buttons(self):
        """操作按钮。"""
        frame = tk.Frame(self.root, bg=THEME["bg"])
        frame.pack(fill="x", padx=20, pady=8)

        buttons = [
            ("👁 预览差异", self._on_preview, THEME["accent"]),
            ("🔧 一键修复", self._on_fix, THEME["green"]),
            ("✅ 风格检查", self._on_check, THEME["peach"]),
            ("🗑 清空日志", self._on_clear, THEME["overlay"]),
        ]

        for text, cmd, color in buttons:
            btn = tk.Button(
                frame, text=text,
                font=("Microsoft YaHei UI", 11, "bold"),
                fg=THEME["bg"], bg=color,
                activebackground=THEME["text_dim"],
                relief="flat", cursor="hand2",
                padx=20, pady=6,
                command=cmd,
            )
            btn.pack(side="left", padx=(0, 10))

        # 进度指示
        self.progress_var = tk.StringVar(value="")
        tk.Label(
            frame, textvariable=self.progress_var,
            font=("Consolas", 10),
            fg=THEME["yellow"], bg=THEME["bg"],
        ).pack(side="right")

    def _build_log_area(self):
        """日志输出区域。"""
        frame = tk.Frame(self.root, bg=THEME["bg"])
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 4))

        tk.Label(
            frame, text="📋 输出",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg=THEME["text"], bg=THEME["bg"],
        ).pack(anchor="w", pady=(0, 4))

        self.log = scrolledtext.ScrolledText(
            frame,
            font=("Consolas", 10),
            fg=THEME["text"], bg=THEME["surface"],
            insertbackground=THEME["text"],
            relief="flat", bd=0,
            wrap="none",  # 水平滚动
            state="disabled",
        )
        self.log.pack(fill="both", expand=True, ipady=4)

        # 配置颜色标签
        self.log.tag_configure("header", foreground=THEME["accent"], font=("Consolas", 10, "bold"))
        self.log.tag_configure("add", foreground=THEME["green"])
        self.log.tag_configure("del", foreground=THEME["red"])
        self.log.tag_configure("warn", foreground=THEME["yellow"])
        self.log.tag_configure("info", foreground=THEME["text_dim"])
        self.log.tag_configure("ok", foreground=THEME["green"], font=("Consolas", 10, "bold"))
        self.log.tag_configure("err", foreground=THEME["red"], font=("Consolas", 10, "bold"))

    def _build_status_bar(self):
        """底部状态栏。"""
        frame = tk.Frame(self.root, bg=THEME["overlay"], pady=3)
        frame.pack(fill="x", side="bottom")

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(
            frame, textvariable=self.status_var,
            font=("Microsoft YaHei UI", 9),
            fg=THEME["text_dim"], bg=THEME["overlay"],
        ).pack(side="left", padx=8)

    # ============================================================
    # 辅助 UI 方法
    # ============================================================

    def _make_check(self, parent, text, variable):
        """创建复选框。"""
        cb = tk.Checkbutton(
            parent, text=text, variable=variable,
            font=("Microsoft YaHei UI", 10),
            fg=THEME["text"], bg=THEME["surface"],
            selectcolor=THEME["input_bg"],
            activebackground=THEME["surface"],
            activeforeground=THEME["text"],
            cursor="hand2",
        )
        cb.pack(anchor="w", pady=1)

    def _browse_directory(self):
        """浏览选择目录。"""
        path = filedialog.askdirectory(title="选择要处理的目录")
        if path:
            self.dir_var.set(path)

    def _log_clear(self):
        """清空日志。"""
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _log_write(self, text, tag=""):
        """写入日志。"""
        self.log.config(state="normal")
        if tag:
            self.log.insert("end", text, tag)
        else:
            self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")

    def _log_line(self, text, tag=""):
        """写入一行日志。"""
        self._log_write(text + "\n", tag)

    # ============================================================
    # 获取选项
    # ============================================================

    def _get_extensions(self) -> tuple:
        """解析扩展名输入。"""
        raw = self.var_extensions.get().strip()
        exts = []
        for e in raw.split():
            e = e.strip()
            if e:
                exts.append(e if e.startswith(".") else f".{e}")
        return tuple(exts) if exts else (".c", ".h")

    def _get_directory(self) -> str:
        """获取并验证目录路径。"""
        path = self.dir_var.get().strip()
        if not path:
            messagebox.showwarning("提示", "请先选择目标目录")
            return ""
        if not os.path.isdir(path):
            messagebox.showerror("错误", f"目录不存在: {path}")
            return ""
        return path

    # ============================================================
    # 核心操作
    # ============================================================

    def _run_in_thread(self, func):
        """在后台线程中运行，防止 UI 冻结。"""
        if self._running:
            messagebox.showinfo("提示", "已有任务正在运行，请等待完成")
            return

        def wrapper():
            self._running = True
            try:
                func()
            finally:
                self._running = False
                self.root.after(0, lambda: self.progress_var.set(""))
                self.root.after(0, lambda: self.status_var.set("就绪"))

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()

    def _process_files(self, mode: str):
        """处理文件的核心逻辑。

        mode: "preview" | "fix" | "check"
        """
        directory = self._get_directory()
        if not directory:
            return

        extensions = self._get_extensions()
        recursive = self.var_recursive.get()
        verbose = self.var_verbose.get()
        backup = self.var_backup.get()

        # 查找文件
        files = find_c_files(directory, extensions, recursive)
        if not files:
            self.root.after(0, lambda: self._log_line(
                f"在 '{directory}' 中未找到匹配的文件 "
                f"(扩展名: {', '.join(extensions)})", "warn"))
            return

        self.root.after(0, lambda: self._log_line(
            f"{'━' * 50}", "header"))
        self.root.after(0, lambda: self._log_line(
            f"目录: {os.path.abspath(directory)}", "header"))
        self.root.after(0, lambda: self._log_line(
            f"文件数: {len(files)}", "header"))
        mode_text = {"preview": "预览（不修改）", "check": "检查", "fix": "修复"}
        self.root.after(0, lambda: self._log_line(
            f"模式: {mode_text[mode]}", "header"))
        self.root.after(0, lambda: self._log_line(""))

        changed_count = 0
        total = len(files)

        for idx, filepath in enumerate(files):
            # 更新进度
            self.root.after(0, lambda i=idx, t=total: self.progress_var.set(
                f"处理中... {i + 1}/{t}"))
            self.root.after(0, lambda: self.status_var.set(
                f"正在处理: {os.path.basename(filepath)}"))

            # 读取文件
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    original = f.read()
            except Exception as e:
                self.root.after(0, lambda e=e: self._log_line(
                    f"  跳过 {filepath}: {e}", "warn"))
                continue

            # 应用修复
            fixed = apply_fixes(original)
            changed = original != fixed

            if not changed:
                if verbose:
                    self.root.after(0, lambda fp=filepath: self._log_line(
                        f"  OK {fp} (无需修改)", "ok"))
                continue

            changed_count += 1

            # 生成 diff
            import difflib
            diff_lines = list(difflib.unified_diff(
                original.splitlines(True),
                fixed.splitlines(True),
                fromfile=f"a/{os.path.basename(filepath)}",
                tofile=f"b/{os.path.basename(filepath)}",
            ))

            # 输出 diff
            self.root.after(0, lambda fp=filepath: self._log_line(
                f"\n  {fp}:", "header"))

            for dline in diff_lines:
                if dline.startswith("+") and not dline.startswith("+++"):
                    self.root.after(0, lambda l=dline: self._log_line(
                        f"  {l.rstrip()}", "add"))
                elif dline.startswith("-") and not dline.startswith("---"):
                    self.root.after(0, lambda l=dline: self._log_line(
                        f"  {l.rstrip()}", "del"))
                elif dline.startswith("@@"):
                    self.root.after(0, lambda l=dline: self._log_line(
                        f"  {l.rstrip()}", "info"))
                else:
                    self.root.after(0, lambda l=dline: self._log_line(
                        f"  {l.rstrip()}"))

            # 警告
            if verbose:
                warnings = check_line_length(fixed.splitlines(True), filepath)
                warnings += check_naming_convention(fixed.splitlines(True), filepath)
                for w in warnings:
                    self.root.after(0, lambda w=w: self._log_line(
                        f"  ! {w}", "warn"))

            # 写入文件（仅 fix 模式）
            if mode == "fix":
                if backup:
                    import shutil
                    backup_path = filepath + ".bak"
                    try:
                        shutil.copy2(filepath, backup_path)
                    except Exception:
                        pass

                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(fixed)
                    self.root.after(0, lambda fp=filepath: self._log_line(
                        f"  OK 已修改 {fp}", "ok"))
                except Exception as e:
                    self.root.after(0, lambda fp=filepath, e=e: self._log_line(
                        f"  X 无法写入 {fp}: {e}", "err"))

        # 汇总
        self.root.after(0, lambda: self._log_line(""))
        self.root.after(0, lambda: self._log_line(
            f"{'━' * 50}", "header"))
        self.root.after(0, lambda: self._log_line(
            f"已处理: {total} 个文件", "header"))
        self.root.after(0, lambda cc=changed_count: self._log_line(
            f"已修改: {cc} 个文件", "ok" if changed_count > 0 else "info"))
        self.root.after(0, lambda t=total, cc=changed_count: self._log_line(
            f"无需修改: {t - cc} 个文件", "info"))

        if mode == "check" and changed_count > 0:
            self.root.after(0, lambda: self._log_line(
                "\n⚠ 存在风格问题！请使用「预览差异」查看详情。", "warn"))

    # ============================================================
    # 按钮事件
    # ============================================================

    def _on_preview(self):
        """预览差异。"""
        self._log_clear()
        self._run_in_thread(lambda: self._process_files("preview"))

    def _on_fix(self):
        """一键修复。"""
        self._log_clear()

        directory = self._get_directory()
        if not directory:
            return

        if not messagebox.askyesno(
            "确认",
            f"即将修改 {directory} 下的 C 源文件。\n"
            f"{'已启用 .bak 备份。' if self.var_backup.get() else '未启用备份！修改不可逆！'}\n\n"
            f"是否继续？",
        ):
            return

        self._run_in_thread(lambda: self._process_files("fix"))

    def _on_check(self):
        """风格检查。"""
        self._log_clear()
        self._run_in_thread(lambda: self._process_files("check"))

    def _on_clear(self):
        """清空日志。"""
        self._log_clear()


# ============================================================
# 入口
# ============================================================

def main():
    root = tk.Tk()

    # 尝试设置 DPI 感知（Windows）
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = KernelStyleGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
