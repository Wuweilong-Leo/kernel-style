# Linux 内核编码风格修改器

自动将 C 代码修改为符合 [Linux 内核编码风格](https://www.kernel.org/doc/html/latest/process/coding-style.html)。

提供 **命令行版**、**GUI 版** 和 **独立 exe 二进制**。

## 下载

| 文件 | 说明 | 大小 |
|------|------|------|
| `dist/kernel_style.exe` | 命令行版，无需 Python | ~9 MB |
| `dist/kernel_style_gui.exe` | GUI 版，双击即用 | ~12 MB |

## 功能

| 修复项 | 描述 | 示例 |
|--------|------|------|
| 缩进 | 空格 → Tab（8 列宽度） | `    code` → `\tcode` |
| 函数大括号 | 开括号独占一行 | `int foo() {` → `int foo()\n{` |
| 控制语句大括号 | 开括号在同一行 | `if (x)\n{` → `if (x) {` |
| 关键字空格 | 关键字后加空格 | `if(` → `if (` |
| 函数调用空格 | 函数名后不加空格 | `func (` → `func(` |
| 指针风格 | `*` 跟变量名 | `char* p` → `char *p` |
| 逗号空格 | 逗号后加空格 | `func(a,b)` → `func(a, b)` |
| 大括号空格 | `){` → `) {` | `if (x){` → `if (x) {` |
| 注释风格 | `//` → `/* */` | `// comment` → `/* comment */` |
| 行尾空白 | 删除行尾空格/Tab | `code   ` → `code` |
| 多余空行 | 合并连续空行 | 3 个空行 → 1 个空行 |
| switch/case | case 与 switch 同级 | 缩进的 `case` → 同级 `case` |
| 文件末尾 | 确保换行结尾 | 缺少 `\n` → 添加 `\n` |
| 行长度检查 | 超过 80 列警告 | （仅 `-v` 模式） |
| 命名检查 | CamelCase 警告 | （仅 `-v` 模式） |

## GUI 版本

直接双击 `kernel_style_gui.exe` 运行，或：

```bash
python kernel_style_gui.py
```

界面功能：
- 📁 选择目标目录
- ⚙ 勾选选项（递归、备份、扩展名、详细模式）
- 👁 预览差异（只看不改）
- 🔧 一键修复（带确认对话框）
- ✅ 风格检查
- 📋 彩色 diff 输出

## 命令行用法

```bash
# 基本用法 — 修改目录下所有 .c/.h 文件
python kernel_style.py ./src

# 预览模式 — 只显示差异，不修改文件
python kernel_style.py ./src --dry-run

# 检查模式 — 不修改，退出码非零表示有风格问题
python kernel_style.py ./src --check

# 详细模式 — 显示行长度和命名警告
python kernel_style.py ./src -v

# 不创建 .bak 备份
python kernel_style.py ./src --no-backup

# 指定文件扩展名
python kernel_style.py ./src -e .c .h .cpp

# 不递归子目录
python kernel_style.py ./src --no-recursive
```

使用 exe 版本时将 `python kernel_style.py` 替换为 `kernel_style.exe` 即可。

## 命令行选项

```
usage: kernel_style.py [-h] [-r] [--no-recursive] [-d] [-v] [-e EXTENSIONS]
                       [--no-backup] [--check]
                       directory

positional arguments:
  directory             要处理的目录

options:
  -h, --help            显示帮助信息
  -r, --recursive       递归处理子目录（默认开启）
  --no-recursive        不递归处理子目录
  -d, --dry-run         只显示差异，不修改文件
  -v, --verbose         显示详细处理信息（行长度和命名警告）
  -e, --extensions      要处理的文件扩展名（默认: .c .h）
  --no-backup           不创建 .bak 备份文件
  --check               仅检查风格问题，退出码非零表示有问题
```

## 在 CI 中使用

```bash
# 检查代码风格，有违规时 CI 失败
python kernel_style.py ./src --check --no-backup
```

## 自行打包

```bash
# 命令行版
pyinstaller --onefile --console --name kernel_style kernel_style.py

# GUI 版
pyinstaller --onefile --windowed --name kernel_style_gui kernel_style_gui.py
```

## 注意事项

- 修改前默认创建 `.bak` 备份文件，可用 `--no-backup` 关闭
- 缩进转换会自动检测原始代码的缩进单位（2/4/8 空格）并转为 Tab
- `//` 注释转换为 `/* */` 时，连续的 `//` 行会合并为块注释
- 函数定义检测基于正则匹配，极少数情况可能误判
- 运算符间距（如 `a==b` → `a == b`）未自动修复，因为风险较高
- 工具不会改变代码的缩进层级（如错误的嵌套层级），仅将空格转为 Tab
