"""
Filesystem tool with safe, limited operations. This is intentionally conservative.
"""
from typing import Dict
from pathlib import Path
from tools.base import BaseTool, ToolResult

ALLOWED_ROOT = Path('C:\\Users\\nickk\\Documents\\CYNX-AI')


class FilesystemTool(BaseTool):
    name = 'filesystem'
    description = 'Read files within an allowed directory (read-only).'

    def call(self, args: Dict) -> ToolResult:
        path = args.get('path')
        if not path:
            return ToolResult(False, 'No path provided')
        target = Path(path).resolve()
        try:
            if not str(target).startswith(str(ALLOWED_ROOT.resolve())):
                return ToolResult(False, 'Access denied to that path')
            if not target.exists():
                return ToolResult(False, 'Path does not exist')
            if target.is_dir():
                return ToolResult(True, '\n'.join([p.name for p in target.iterdir()]))
            return ToolResult(True, target.read_text(encoding='utf-8'))
        except Exception as e:
            return ToolResult(False, f'Filesystem error: {e}')
