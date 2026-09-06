import json

from rich.console import Console
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text

from ai.terminal_ui.colors import (
    ACCENT,
    AVAILABLE_TOOLS,
    DIM,
    ERROR,
    EXECUTE,
    FINAL_PROMPT,
    INFO,
    MEMORY,
    MEMORY_ERROR,
    MODEL,
    OLLAMA,
    PRIMARY,
    PROMPT,
    RESULT,
    TOOL,
    TOOL_ARGS,
    USER,
    WARNING,
)


class CYNXTerminal:
    def __init__(self):
        self.console = Console(
            highlighter=None,
            highlight=False,
            soft_wrap=True,
            stderr=False,
            markup=False,
        )

    def _print_label(self, label, value=None, *, style, value_style="white"):
        text = Text()
        rendered_label = label if label.startswith("[") else f"[{label}]"
        text.append(rendered_label, style=style)
        if value is not None:
            text.append(f" {value}", style=value_style)
        self.console.print(text)

    def section(self, title):
        self.console.print(Rule(title, style=PRIMARY))

    def info(self, message):
        self.console.print(Text(str(message), style=INFO))

    def memory(self, message):
        self.console.print(Text(str(message), style=MEMORY))

    def warning(self, message):
        self.console.print(Text(str(message), style=WARNING))

    def error(self, message):
        self.console.print(Text(str(message), style=ERROR))

    def dim(self, message):
        self.console.print(Text(str(message), style=DIM))

    def user(self, message):
        self._print_label("USER", str(message), style=USER)

    def ollama(self, label="OLLAMA CALL", value=None):
        self._print_label(label, value, style=OLLAMA)

    def model(self, label="MODEL RESPONSE", value=None):
        self._print_label(label, value, style=MODEL)

    def tool(self, label="TOOL CALL", value=None):
        self._print_label(label, value, style=TOOL)

    def tool_args(self, label="TOOL ARGUMENTS", value=None):
        self._print_label(label, value, style=TOOL_ARGS)

    def execute(self, label="EXECUTING TOOL", value=None):
        self._print_label(label, value, style=EXECUTE)

    def result(self, label="TOOL RESULT", value=None):
        self._print_label(label, value, style=RESULT)

    def prompt(self, label="PROMPT SECTION", value=None):
        self._print_label(label, value, style=PROMPT)

    def final_prompt(self, label="FINAL SYSTEM PROMPT", value=None):
        self._print_label(label, value, style=FINAL_PROMPT)

    def available_tools(self, tools):
        self._print_label("AVAILABLE TOOLS", tools, style=AVAILABLE_TOOLS)

    def json(self, payload):
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
        self.console.print(
            Syntax(rendered, "json", theme="monokai", word_wrap=True)
        )

    def timing(self, message):
        self.console.print(Text(str(message), style=DIM))

    def memory_error(self, message):
        self.console.print(Text(str(message), style=MEMORY_ERROR))

    def blank(self):
        self.console.print()


terminal = CYNXTerminal()
