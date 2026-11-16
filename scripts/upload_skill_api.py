#!/usr/bin/env python3
"""
通过 Claude API 上传 .claude/skills 下的自定义 Skill。

需要环境变量 ANTHROPIC_API_KEY。
使用方式:
  Set ANTHROPIC_API_KEY in the environment before running this script.
  pip install requests
  python scripts/upload_skill_api.py [skill_dir]

默认上传 .claude/skills/code_verifier
"""

import os
import sys
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = ROOT / ".claude" / "skills"
API_BASE = "https://api.anthropic.com/v1"


def get_mime(path: Path) -> str:
    suf = path.suffix.lower()
    mime = {
        ".md": "text/markdown",
        ".py": "text/x-python",
        ".sh": "text/x-shellscript",
        ".txt": "text/plain",
    }
    return mime.get(suf, "application/octet-stream")


def get_skill_name_from_frontmatter(skill_dir: Path) -> str:
    """从 SKILL.md 的 YAML frontmatter 读取 name 字段，API 要求顶层文件夹名与之一致。"""
    skill_md = skill_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"SKILL.md 需包含 YAML frontmatter (name: ...): {skill_dir}")
    end = text.index("---", 3) if "---" in text[3:] else 0
    if not end:
        raise SystemExit(f"SKILL.md frontmatter 未闭合: {skill_dir}")
    import re
    m = re.search(r"^name:\s*['\"]?([a-z0-9-]+)['\"]?", text[4:end], re.MULTILINE | re.IGNORECASE)
    if not m:
        raise SystemExit(f"SKILL.md 中未找到 name 字段: {skill_dir}")
    return m.group(1).strip()


def collect_skill_files(skill_dir: Path):
    """收集 skill 目录下所有文件，返回 (relative_path, absolute_path) 列表。"""
    if not skill_dir.is_dir():
        raise SystemExit(f"目录不存在: {skill_dir}")
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise SystemExit(f"Skill 必须包含根目录下的 SKILL.md: {skill_dir}")
    files = []
    for p in sorted(skill_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(skill_dir)
            files.append((str(rel), p))
    # API 要求 SKILL.md 在顶层：按路径排序，保证 "SKILL.md" 在最前
    files.sort(key=lambda x: (x[0] != "SKILL.md", x[0]))
    return files


def upload_with_requests(api_key: str, skill_name: str, skill_dir: Path):
    import requests

    folder_name = get_skill_name_from_frontmatter(skill_dir)
    pairs = collect_skill_files(skill_dir)
    print(f"准备上传 skill: {skill_name} (frontmatter name={folder_name}, {len(pairs)} 个文件)")

    # multipart/form-data: display_title + 多个 files；顶层文件夹名必须与 SKILL.md 中 name 一致
    files = []
    fhs = []
    try:
        for rel_path, abs_path in pairs:
            fh = open(abs_path, "rb")
            fhs.append(fh)
            mime = get_mime(abs_path)
            full_rel = f"{folder_name}/{rel_path}"
            files.append(("files[]", (full_rel, fh, mime)))

        # multipart: display_title 用 (name, (None, value))，文件用 (name, (filename, fp, mime))
        form = [("display_title", (None, f"Lean4 / {skill_name}"))] + files
        resp = requests.post(
            f"{API_BASE}/skills?beta=true",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "skills-2025-10-02",
            },
            files=form,
            timeout=120,
        )
    finally:
        for fh in fhs:
            fh.close()

    if resp.status_code != 200:
        print(f"上传失败 HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        if resp.status_code == 404:
            print("提示: 404 可能表示当前账户未开通 Skills API beta，或需在 Anthropic Console 启用。", file=sys.stderr)
        sys.exit(1)

    out = resp.json()
    print("上传成功:")
    print(f"  id: {out.get('id')}")
    print(f"  display_title: {out.get('display_title')}")
    print(f"  latest_version: {out.get('latest_version')}")
    print(f"  created_at: {out.get('created_at')}")
    return out


def main():
    skill_name = sys.argv[1] if len(sys.argv) > 1 else "code_verifier"
    skill_dir = SKILLS_ROOT / skill_name

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("请设置环境变量 ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(1)

    try:
        import requests
    except ImportError:
        print("请先安装: pip install requests", file=sys.stderr)
        sys.exit(1)

    upload_with_requests(api_key, skill_name, skill_dir)


if __name__ == "__main__":
    main()
