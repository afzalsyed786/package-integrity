"""Python AST facts with import-alias resolution. Parsing only; nothing is executed."""
import ast


class PyFacts:
    def __init__(self, text: str):
        self.tree = None
        self.aliases: dict[str, str] = {}
        self.imports: list[tuple[str, int]] = []
        self.calls: list[tuple[str, ast.Call]] = []
        try:
            self.tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            return
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
                    self.imports.append((a.name, node.lineno))
            elif isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"
                    self.imports.append((node.module, node.lineno))
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                name = self.canonical(node.func)
                if name:
                    self.calls.append((name, node))

    @property
    def ok(self) -> bool:
        return self.tree is not None

    def canonical(self, func) -> str | None:
        parts = []
        while isinstance(func, ast.Attribute):
            parts.append(func.attr)
            func = func.value
        if isinstance(func, ast.Name):
            parts.append(self.aliases.get(func.id, func.id))
        elif isinstance(func, ast.Call) and getattr(func.func, "id", None) == "__import__" and func.args and isinstance(func.args[0], ast.Constant):
            parts.append(str(func.args[0].value))
        else:
            return None
        parts.reverse()
        return ".".join(parts)

    def nested_call_names(self, node) -> set[str]:
        names = set()
        for arg in list(node.args) + [k.value for k in node.keywords]:
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Call):
                    n = self.canonical(sub.func)
                    if n:
                        names.add(n)
                    if isinstance(sub.func, ast.Attribute):
                        names.add("." + sub.func.attr)
        return names

    def module_level_lines(self) -> set[int]:
        """Line numbers of statements executed at import time (outside functions and classes)."""
        lines = set()
        if not self.tree:
            return lines
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for sub in ast.walk(node):
                if hasattr(sub, "lineno"):
                    lines.add(sub.lineno)
        return lines
