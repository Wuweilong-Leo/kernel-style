#!/usr/bin/env python3
"""
kernel_style.py — Linux 内核编码风格修改器

自动将 C 代码修改为符合 Linux 内核编码风格。
支持递归目录扫描、dry-run 模式、差异输出。

用法:
    python kernel_style.py <directory> [options]

Linux 内核编码风格关键规则:
  - 缩进使用 Tab（Tab 宽度 = 8 列），不用空格
  - 函数定义的开括号独占一行
  - 控制语句（if/else/for/while/switch/do）的开括号在同一行
  - 关键字后要有空格：if (, while (, for (, switch (
  - 函数名后不加空格：func(
  - 指针声明：char *p 而非 char* p
  - 注释使用 /* */ 而非 //
  - 删除行尾空白
  - case 与 switch 同级缩进
"""

import argparse
import difflib
import os
import re
import shutil
import sys
from typing import List, Tuple

# ============================================================
# 常量
# ============================================================

TAB_WIDTH = 8
DEFAULT_EXTENSIONS = (".c", ".h")
C_KEYWORDS = frozenset({
    "if", "else", "while", "for", "switch", "do", "return",
    "case", "default", "sizeof", "typeof", "__typeof__",
    "alignof", "__alignof__", "offsetof",
})


# ============================================================
# 颜色输出
# ============================================================

class _C:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def _use_color():
    if os.name == "nt":
        return bool(os.environ.get("ANSICON") or os.environ.get("WT_SESSION")
                     or os.environ.get("TERM"))
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


HAS_COLOR = _use_color()


def cprint(text, color=""):
    if HAS_COLOR and color:
        try:
            print(f"{color}{text}{_C.RESET}")
        except UnicodeEncodeError:
            # Windows GBK 终端不支持某些 Unicode 字符，回退到 ASCII
            safe = text.replace("✓", "OK").replace("✗", "X").replace("⚠", "!")
            print(f"{color}{safe}{_C.RESET}")
    else:
        try:
            print(text)
        except UnicodeEncodeError:
            safe = text.replace("✓", "OK").replace("✗", "X").replace("⚠", "!")
            print(safe)


# ============================================================
# 辅助：字符串 / 注释保护
# ============================================================

def _split_line_safe(line: str) -> List[Tuple[str, str]]:
    """将一行拆分为 (类型, 内容) 片段列表。

    类型: 'code' | 'str' | 'char' | 'comment_c' | 'comment_cpp'
    只修改 'code' 片段中的内容。
    """
    parts = []
    i = 0
    n = len(line)
    buf = []

    def flush_code():
        nonlocal buf
        if buf:
            parts.append(("code", "".join(buf)))
            buf = []

    while i < n:
        ch = line[i]

        # C++ 注释
        if ch == "/" and i + 1 < n and line[i + 1] == "/":
            flush_code()
            parts.append(("comment_cpp", line[i:]))
            return parts

        # C 注释
        if ch == "/" and i + 1 < n and line[i + 1] == "*":
            flush_code()
            end = line.find("*/", i + 2)
            if end != -1:
                parts.append(("comment_c", line[i:end + 2]))
                i = end + 2
            else:
                parts.append(("comment_c", line[i:]))
                return parts
            continue

        # 字符串
        if ch == '"':
            flush_code()
            j = i + 1
            while j < n:
                if line[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if line[j] == '"':
                    j += 1
                    break
                j += 1
            parts.append(("str", line[i:j]))
            i = j
            continue

        # 字符字面量
        if ch == "'":
            flush_code()
            j = i + 1
            while j < n:
                if line[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if line[j] == "'":
                    j += 1
                    break
                j += 1
            parts.append(("char", line[i:j]))
            i = j
            continue

        buf.append(ch)
        i += 1

    flush_code()
    return parts


def _rejoin(parts: List[Tuple[str, str]]) -> str:
    """将片段列表重新组合为一行。"""
    return "".join(p[1] for p in parts)


def _transform_code_parts(parts: List[Tuple[str, str]], func) -> str:
    """对 parts 中的 code 片段应用转换函数 func，然后重新组合。"""
    new_parts = []
    for ptype, ptext in parts:
        if ptype == "code":
            new_parts.append((ptype, func(ptext)))
        else:
            new_parts.append((ptype, ptext))
    return _rejoin(new_parts)


# ============================================================
# 缩进检测
# ============================================================

def _detect_indent_unit(lines: List[str]) -> int:
    """检测文件使用的缩进单位（空格数）。

    统计最常见的前导空格增量，返回 2、4 或 8。
    """
    deltas = []
    prev_indent = 0
    for line in lines:
        stripped = line.lstrip(" ")
        if not stripped or stripped.startswith("\n"):
            continue
        leading = len(line) - len(stripped)
        if line[:leading] != " " * leading:
            continue  # 已有 tab，跳过
        delta = leading - prev_indent
        if delta > 0:
            deltas.append(delta)
        prev_indent = leading

    if not deltas:
        return 8  # 默认

    # 统计最常见的增量
    from collections import Counter
    counter = Counter(deltas)
    unit = counter.most_common(1)[0][0]

    # 归一化为 2/4/8
    for candidate in [2, 4, 8]:
        if unit <= candidate:
            return candidate
    return 8


# ============================================================
# 第 1 轮：逐行修复
# ============================================================

def fix_indentation(lines: List[str], indent_unit: int = 4) -> List[str]:
    """将前导空格转换为 Tab。

    indent_unit: 原文件中一级缩进使用的空格数（自动检测）。
    Linux 内核风格: 每一级缩进 = 1 个 Tab。
    """
    result = []
    for line in lines:
        # 只处理纯空格缩进的行
        stripped = line.lstrip(" ")
        if stripped == line or not stripped:
            result.append(line)
            continue

        leading_spaces = len(line) - len(stripped)
        if line[:leading_spaces] != " " * leading_spaces:
            result.append(line)
            continue

        # 跳过预处理器续行（# 后的空格）
        if stripped.startswith("#"):
            result.append(line)
            continue

        # 按 indent_unit 将空格转为 Tab
        num_tabs = leading_spaces // indent_unit
        remaining = leading_spaces % indent_unit
        new_line = "\t" * num_tabs + " " * remaining + stripped
        result.append(new_line)

    return result


def fix_trailing_whitespace(lines: List[str]) -> List[str]:
    """删除行尾空格和 Tab。"""
    result = []
    for line in lines:
        if line.endswith("\n"):
            # 去掉 \n，删除行尾空格/Tab，再加回 \n
            result.append(line[:-1].rstrip(" \t") + "\n")
        else:
            result.append(line.rstrip(" \t"))
    return result


def fix_keyword_spacing(lines: List[str]) -> List[str]:
    """关键字后添加空格：if( → if ("""
    kw_pat = re.compile(
        r'\b(' + '|'.join(re.escape(k) for k in sorted(C_KEYWORDS, key=len, reverse=True))
        + r')(\()'
    )

    def _fix(text):
        return kw_pat.sub(r'\1 \2', text)

    result = []
    for line in lines:
        parts = _split_line_safe(line)
        result.append(_transform_code_parts(parts, _fix))
    return result


def fix_function_call_spacing(lines: List[str]) -> List[str]:
    """删除函数调用名与左括号之间的空格：func ( → func("""
    func_pat = re.compile(r'\b([a-zA-Z_]\w*)\s+\(')

    def _fix(text):
        def replacer(m):
            name = m.group(1)
            if name in C_KEYWORDS:
                return m.group(0)  # 保留关键字的空格
            return name + "("
        return func_pat.sub(replacer, text)

    result = []
    for line in lines:
        parts = _split_line_safe(line)
        result.append(_transform_code_parts(parts, _fix))
    return result


def fix_pointer_style(lines: List[str]) -> List[str]:
    """修复指针声明风格：char* p → char *p"""
    # 匹配: type* var 但不匹配 type **var（多级指针格式已正确）
    ptr_pat = re.compile(
        r'\b((?:unsigned\s+|signed\s+|long\s+|short\s+|const\s+|static\s+|volatile\s+)*'
        r'(?:void|char|short|int|long|float|double|unsigned|signed|'
        r'size_t|ssize_t|u8|u16|u32|u64|s8|s16|s32|s64|bool|pid_t|atomic_t|'
        r'struct\s+\w+|enum\s+\w+))'
        r'(\*+)\s+(\w)'
    )

    def _fix(text):
        return ptr_pat.sub(r'\1 \2\3', text)

    result = []
    for line in lines:
        parts = _split_line_safe(line)
        result.append(_transform_code_parts(parts, _fix))
    return result


def fix_comma_spacing(lines: List[str]) -> List[str]:
    """逗号后添加空格：func(a,b) → func(a, b)"""
    def _fix(text):
        text = re.sub(r',(?!\s)', ', ', text)
        return text

    result = []
    for line in lines:
        parts = _split_line_safe(line)
        result.append(_transform_code_parts(parts, _fix))
    return result


def fix_brace_spacing(lines: List[str]) -> List[str]:
    """控制语句的 { 前加空格：if (x){ → if (x) {

    Linux 内核风格：控制语句的 { 与 ) 之间要有空格。
    """
    # 匹配 ) 后直接跟 { （无空格）的情况
    brace_pat = re.compile(r'\)\{')

    def _fix(text):
        # 只修复 ) 后直接跟 { 的情况
        text = brace_pat.sub(') {', text)
        return text

    result = []
    for line in lines:
        parts = _split_line_safe(line)
        result.append(_transform_code_parts(parts, _fix))
    return result


def fix_cpp_comments(lines: List[str]) -> List[str]:
    """将 C++ 风格注释 // 转换为 C 风格注释 /* */"""
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # 查找 // 注释起始位置（跳过字符串和 C 注释中的 //）
        parts = _split_line_safe(line)
        cpp_idx = -1
        code_before = ""
        comment_text = ""

        for idx, (ptype, ptext) in enumerate(parts):
            if ptype == "comment_cpp":
                cpp_idx = idx
                # 获取注释前的代码部分
                code_before = "".join(p[1] for p in parts[:idx]).rstrip()
                # 提取注释文本（去掉 // 前缀）
                raw_comment = ptext.lstrip("/")
                comment_text = raw_comment.strip()
                break

        if cpp_idx == -1:
            result.append(line)
            i += 1
            continue

        # 收集连续的 // 注释行
        comment_lines = []
        if comment_text:
            comment_lines.append(comment_text)

        # 获取代码部分的缩进
        indent = ""
        for ch in line:
            if ch in (" ", "\t"):
                indent += ch
            else:
                break

        j = i + 1
        while j < len(lines):
            next_stripped = lines[j].lstrip()
            if next_stripped.startswith("//"):
                next_text = next_stripped[2:].strip()
                if next_text:
                    comment_lines.append(next_text)
                j += 1
            else:
                break

        # 生成替换注释
        if code_before:
            # 行内注释：code /* comment */
            result.append(code_before + " /* " + " ".join(comment_lines) + " */\n")
        elif len(comment_lines) == 0:
            # 空 // 注释
            result.append("\n")
        elif len(comment_lines) == 1:
            # 单行注释
            result.append(indent + "/* " + comment_lines[0] + " */\n")
        else:
            # 多行注释块
            result.append(indent + "/*\n")
            for cl in comment_lines:
                result.append(indent + " * " + cl + "\n")
            result.append(indent + " */\n")

        i = j

    return result


def fix_multiple_blank_lines(lines: List[str]) -> List[str]:
    """合并连续多个空行为一个。"""
    result = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank
    return result


# ============================================================
# 第 2 轮：跨行修复
# ============================================================

def fix_function_braces(lines: List[str]) -> List[str]:
    """函数定义的开括号移到下一行。

    Linux 内核风格:
        int foo(int x)
        {
    而非:
        int foo(int x) {
    """
    result = []
    i = 0

    # 控制语句关键字（排除这些行）
    _CONTROL_KW = ("if", "else", "while", "for", "switch", "do")

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 只处理以 { 结尾的行
        if not stripped.endswith("{"):
            result.append(line)
            i += 1
            continue

        # 排除控制语句（if/else/while/for/switch/do）后跟 { 的情况
        # 控制语句的 { 应保留在同一行
        is_control = False
        for kw in _CONTROL_KW:
            # 检查 stripped 是否以关键字开头
            if re.match(r'^[{}]*\s*' + kw + r'\b', stripped):
                is_control = True
                break
            if re.match(r'^\s*' + kw + r'\b', stripped):
                is_control = True
                break

        if is_control:
            result.append(line)
            i += 1
            continue

        # 排除结构体/枚举/联合体的 { （它们也应在同一行或下一行）
        if re.match(r'^\s*(struct|enum|union)\s+\w+\s*\{\s*$', stripped):
            result.append(line)
            i += 1
            continue

        # 排除 do { 的情况（do-while 循环）
        if re.match(r'^\s*do\s*\{\s*$', stripped):
            result.append(line)
            i += 1
            continue

        # 尝试匹配函数定义模式
        # 必须有 返回类型 + 函数名(参数) { 的结构
        # 关键：前面不能是控制关键字
        func_def_re = re.compile(
            r'^(\s*)'                                     # 前导空白
            r'('                                          # --- 函数头 ---
            r'(?:static\s+|inline\s+|__init\s+|__exit\s+|'
            r'__initdata\s+|extern\s+|noinline\s+|'
            r'EXPORT_[A-Z_]+\s*\([^)]*\)\s+)*'             # 修饰符
            r'(?:const\s+|unsigned\s+|signed\s+|long\s+|'
            r'short\s+|volatile\s+|struct\s+|enum\s+)*'    # 类型修饰符
            r'\w+'                                        # 返回类型
            r'\s+\*?\s*'                                  # 空白 + 可选指针
            r'\w+'                                        # 函数名
            r'\s*\([^;]*?\)'                              # 参数列表（不含分号）
            r')'                                          # --- 函数头结束 ---
            r'\s*\{\s*$'                                  # 行尾的 {
        )

        m = func_def_re.match(line)
        if m:
            func_header = m.group(2).rstrip()
            result.append(func_header + "\n")
            result.append("{\n")
            i += 1
            continue

        result.append(line)
        i += 1

    return result


def fix_control_braces(lines: List[str]) -> List[str]:
    """控制语句的开括号移到同一行。

    Linux 内核风格:
        if (x) {
        } else {
    而非:
        if (x)
        {
        }
        else
        {
    """
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()

        # 模式 1: if/while/for/switch (condition) 后跟 { 在下一行
        if re.match(r'^\s*(?:if|while|for|switch)\s*\(.*\)\s*$', stripped):
            if i + 1 < len(lines) and lines[i + 1].strip() == "{":
                result.append(stripped + " {\n")
                i += 2
                continue

        # 模式 2: else if (condition) 后跟 { 在下一行
        if re.match(r'^\s*\}\s*else\s+if\s*\(.*\)\s*$', stripped):
            if i + 1 < len(lines) and lines[i + 1].strip() == "{":
                result.append(stripped + " {\n")
                i += 2
                continue

        # 模式 3: } else 后跟 { 在下一行 → 合并为 } else {
        if re.match(r'^\s*\}\s*else\s*$', stripped):
            if i + 1 < len(lines) and lines[i + 1].strip() == "{":
                result.append(stripped.rstrip() + " {\n")
                i += 2
                continue

        # 模式 4: else 后跟 { 在下一行
        if re.match(r'^\s*else\s*$', stripped):
            if i + 1 < len(lines) and lines[i + 1].strip() == "{":
                result.append(stripped.rstrip() + " {\n")
                i += 2
                continue

        # 模式 5: do 后跟 { 在下一行
        if re.match(r'^\s*do\s*$', stripped):
            if i + 1 < len(lines) and lines[i + 1].strip() == "{":
                result.append(stripped.rstrip() + " {\n")
                i += 2
                continue

        # 模式 6: } else if (condition) 拆分为两行的情况
        #   }
        #   else if (condition)
        #   {
        if re.match(r'^\s*\}\s*$', stripped):
            if i + 1 < len(lines):
                next_stripped = lines[i + 1].rstrip()
                # 检查下一行是否是 else 或 else if
                if re.match(r'^\s*else\s*$', next_stripped):
                    # } else 合并
                    if i + 2 < len(lines) and lines[i + 2].strip() == "{":
                        indent = line[:len(line) - len(line.lstrip())]
                        result.append(indent + "} else {\n")
                        i += 3
                        continue
                elif re.match(r'^\s*else\s+if\s*\(.*\)\s*$', next_stripped):
                    if i + 2 < len(lines) and lines[i + 2].strip() == "{":
                        result.append(indent + "} " + next_stripped.lstrip() + " {\n")
                        i += 3
                        continue

        result.append(line)
        i += 1

    return result


def fix_switch_case_indent(lines: List[str]) -> List[str]:
    """修正 switch/case 缩进，使 case 与 switch 同级。

    Linux 内核风格:
        switch (val) {
        case 1:
                do_something();
                break;
        }
    即 case 标签与 switch 同列，case 内的代码比 switch 多一级缩进。
    """
    result = []
    in_switch = False
    switch_indent = ""
    switch_level = 0  # switch 的 Tab 级别

    def _tab_level(line):
        """计算行的 Tab 缩进级别。"""
        level = 0
        for ch in line:
            if ch == "\t":
                level += 1
            elif ch == " ":
                pass  # 忽略对齐空格
            else:
                break
        return level

    for line in lines:
        stripped = line.lstrip()

        # 检测 switch 语句
        if re.match(r'switch\s*\(', stripped):
            in_switch = True
            switch_indent = line[:len(line) - len(stripped)]
            switch_level = _tab_level(line)
            result.append(line)
            continue

        if in_switch:
            # 检测 case/default 标签
            if re.match(r'(case\s+|default\s*:)', stripped):
                # case 与 switch 同级缩进
                content = stripped.rstrip()
                if content.endswith(":"):
                    result.append(switch_indent + content + "\n")
                    continue

            # 检测 switch 的结束 }
            if stripped.startswith("}"):
                in_switch = False
                result.append(line)
                continue

            # case 内的代码应比 switch 多一级缩进（switch_level + 1 个 Tab）
            # 但比 case 标签的代码需比 case 多一级，即 switch_level + 1
            current_level = _tab_level(line)
            if current_level > switch_level + 1:
                # 缩进过深，减少一级
                excess = current_level - (switch_level + 1)
                new_line = line.lstrip("\t")
                # 去掉 excess 个 tab
                for _ in range(excess):
                    if new_line.startswith("\t"):
                        new_line = new_line[1:]
                new_line = "\t" * (switch_level + 1) + new_line
                result.append(new_line)
                continue

        result.append(line)

    return result


# ============================================================
# 第 3 轮：全局修复
# ============================================================

def fix_eof_newline(lines: List[str]) -> List[str]:
    """确保文件末尾有换行符，移除末尾多余空行。"""
    if not lines:
        return lines

    # 确保每行以 \n 结尾
    lines = [l if l.endswith("\n") else l + "\n" for l in lines]

    # 移除文件末尾的空行（保留一个换行）
    while len(lines) > 1 and lines[-1].strip() == "":
        lines.pop()

    return lines


# ============================================================
# 警告检查器
# ============================================================

def check_line_length(lines: List[str], filename: str, max_len: int = 80) -> List[str]:
    """检查行长度。"""
    warnings = []
    for i, line in enumerate(lines, 1):
        visual_len = 0
        for ch in line.rstrip("\n"):
            visual_len += TAB_WIDTH if ch == "\t" else 1
        if visual_len > max_len:
            warnings.append(
                f"{filename}:{i}: line exceeds {max_len} columns "
                f"({visual_len} columns)")
    return warnings


def check_naming_convention(lines: List[str], filename: str) -> List[str]:
    """检查 CamelCase 标识符。"""
    warnings = []
    camel_re = re.compile(r'\b([a-z]+[A-Z][a-zA-Z0-9]*)\b')

    for i, line in enumerate(lines, 1):
        parts = _split_line_safe(line)
        code_text = "".join(p[1] for p in parts if p[0] == "code")
        for m in camel_re.finditer(code_text):
            name = m.group(1)
            if name in ("NULL", "EOF", "BUG", "WARN", "FIXME", "TODO", "GFP"):
                continue
            warnings.append(
                f"{filename}:{i}: CamelCase '{name}' found (use snake_case)")
    return warnings


# ============================================================
# 主处理流程
# ============================================================

def apply_fixes(content: str) -> str:
    """对文件内容应用所有修复器。"""
    lines = content.splitlines(True)

    # 确保每行以换行结尾
    lines = [l if l.endswith("\n") else l + "\n" for l in lines]

    # 自动检测缩进单位
    indent_unit = _detect_indent_unit(lines)

    # 第 1 轮：逐行修复
    lines = fix_indentation(lines, indent_unit)
    lines = fix_trailing_whitespace(lines)
    lines = fix_keyword_spacing(lines)
    lines = fix_function_call_spacing(lines)
    lines = fix_pointer_style(lines)
    lines = fix_comma_spacing(lines)
    lines = fix_brace_spacing(lines)
    lines = fix_cpp_comments(lines)
    lines = fix_multiple_blank_lines(lines)

    # 第 2 轮：跨行修复
    lines = fix_function_braces(lines)
    lines = fix_control_braces(lines)
    lines = fix_switch_case_indent(lines)

    # 第 3 轮：全局修复
    lines = fix_eof_newline(lines)

    return "".join(lines)


def process_file(filepath: str, args) -> bool:
    """处理单个文件，返回是否有修改。"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
    except Exception as e:
        cprint(f"  跳过 {filepath}: {e}", _C.YELLOW)
        return False

    ext = os.path.splitext(filepath)[1]
    if ext not in args.extensions:
        return False

    fixed = apply_fixes(original)

    # 警告检查
    warnings = []
    if args.verbose:
        warnings.extend(check_line_length(fixed.splitlines(True), filepath))
        warnings.extend(check_naming_convention(fixed.splitlines(True), filepath))

    changed = original != fixed
    if not changed and not warnings:
        if args.verbose:
            cprint(f"  ✓ {filepath} (无需修改)", _C.GREEN)
        return False

    # 显示差异
    if changed:
        diff = list(difflib.unified_diff(
            original.splitlines(True),
            fixed.splitlines(True),
            fromfile=f"a/{os.path.basename(filepath)}",
            tofile=f"b/{os.path.basename(filepath)}",
        ))
        if diff:
            cprint(f"\n  {filepath}:", _C.CYAN)
            for dline in diff:
                if dline.startswith("+") and not dline.startswith("+++"):
                    cprint(f"  {dline}", _C.GREEN)
                elif dline.startswith("-") and not dline.startswith("---"):
                    cprint(f"  {dline}", _C.RED)
                elif dline.startswith("@@"):
                    cprint(f"  {dline}", _C.CYAN)
                else:
                    print(f"  {dline}", end="")

    # 显示警告
    for w in warnings:
        cprint(f"  ⚠ {w}", _C.YELLOW)

    if args.dry_run or args.check:
        return changed

    # 写入文件
    if changed:
        # 创建备份
        if not args.no_backup:
            backup_path = filepath + ".bak"
            try:
                shutil.copy2(filepath, backup_path)
            except Exception as e:
                cprint(f"  警告: 无法创建备份 {backup_path}: {e}", _C.YELLOW)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(fixed)
            cprint(f"  ✓ 已修改 {filepath}", _C.GREEN)
        except Exception as e:
            cprint(f"  ✗ 无法写入 {filepath}: {e}", _C.RED)
            return False

    return changed


def find_c_files(directory: str, extensions: tuple, recursive: bool = True) -> List[str]:
    """查找目录中的 C 源文件。"""
    files = []
    if recursive:
        for root, _, filenames in os.walk(directory):
            for fn in filenames:
                if os.path.splitext(fn)[1] in extensions:
                    files.append(os.path.join(root, fn))
    else:
        for fn in os.listdir(directory):
            full = os.path.join(directory, fn)
            if os.path.isfile(full) and os.path.splitext(fn)[1] in extensions:
                files.append(full)
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(
        description="Linux 内核编码风格修改器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s ./src                    修改 src 目录下所有 .c/.h 文件
  %(prog)s ./src --dry-run          仅显示差异，不修改文件
  %(prog)s ./src --check            仅检查，退出码非零表示有风格问题
  %(prog)s ./src --no-backup        修改但不创建 .bak 备份
  %(prog)s ./src -e .c .h .cpp      指定文件扩展名
  %(prog)s ./src -v                 显示详细警告（行长度、命名风格）
        """,
    )
    parser.add_argument("directory", help="要处理的目录")
    parser.add_argument("-r", "--recursive", action="store_true", default=True,
                        help="递归处理子目录（默认开启）")
    parser.add_argument("--no-recursive", action="store_false", dest="recursive",
                        help="不递归处理子目录")
    parser.add_argument("-d", "--dry-run", action="store_true",
                        help="只显示差异，不修改文件")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="显示详细处理信息（行长度和命名警告）")
    parser.add_argument("-e", "--extensions", nargs="+",
                        default=list(DEFAULT_EXTENSIONS),
                        help=f"要处理的文件扩展名（默认: {' '.join(DEFAULT_EXTENSIONS)}）")
    parser.add_argument("--no-backup", action="store_true",
                        help="不创建 .bak 备份文件")
    parser.add_argument("--check", action="store_true",
                        help="仅检查风格问题，不修改文件（退出码非零表示有问题）")

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        cprint(f"错误: '{args.directory}' 不是有效目录", _C.RED)
        sys.exit(1)

    args.extensions = tuple(e if e.startswith(".") else f".{e}" for e in args.extensions)

    files = find_c_files(args.directory, args.extensions, args.recursive)
    if not files:
        cprint(f"在 '{args.directory}' 中未找到匹配的文件 "
               f"(扩展名: {', '.join(args.extensions)})", _C.YELLOW)
        sys.exit(0)

    mode = "dry-run" if args.dry_run else ("check" if args.check else "修改")
    backup_info = "" if args.no_backup else " (带备份)"

    print()
    cprint("Linux 内核风格修改器", _C.BOLD + _C.CYAN)
    cprint("━" * 40, _C.CYAN)
    cprint(f"目录: {os.path.abspath(args.directory)}", _C.CYAN)
    cprint(f"文件数: {len(files)}", _C.CYAN)
    cprint(f"模式: {mode}{backup_info}", _C.YELLOW if args.dry_run or args.check else _C.GREEN)
    print()

    changed_count = 0
    for filepath in files:
        if process_file(filepath, args):
            changed_count += 1

    print()
    cprint("━" * 40, _C.CYAN)
    cprint(f"已处理: {len(files)} 个文件", _C.CYAN)
    if changed_count:
        cprint(f"已修改: {changed_count} 个文件", _C.GREEN)
    cprint(f"无需修改: {len(files) - changed_count} 个文件", _C.CYAN)

    if args.check and changed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
