"""
Error analyser for AI Builder.
Parses and categorizes error messages, suggests fixes.
"""

import re
import ast
import traceback
from pathlib import Path
from core.logger import get_logger
from tools.file_reader import FileReader

log = get_logger("tools")


# Error pattern categories
ERROR_PATTERNS = {
    "syntax": {
        "patterns": [r"SyntaxError", r"IndentationError", r"TabError"],
        "description": "Code syntax or indentation issue",
    },
    "import": {
        "patterns": [r"ImportError", r"ModuleNotFoundError"],
        "description": "Missing or incorrect import",
    },
    "name": {
        "patterns": [r"NameError", r"UnboundLocalError"],
        "description": "Variable or function name not defined",
    },
    "type": {
        "patterns": [r"TypeError", r"AttributeError"],
        "description": "Incorrect type usage or attribute access",
    },
    "value": {
        "patterns": [r"ValueError", r"ZeroDivisionError"],
        "description": "Invalid value or operation",
    },
    "key_index": {
        "patterns": [r"KeyError", r"IndexError"],
        "description": "Missing key or out-of-bounds index",
    },
    "file_io": {
        "patterns": [r"FileNotFoundError", r"PermissionError", r"IsADirectoryError"],
        "description": "File system access issue",
    },
    "runtime": {
        "patterns": [r"RuntimeError", r"RecursionError"],
        "description": "Runtime execution issue",
    },
    "os": {
        "patterns": [r"OSError", r"SystemError"],
        "description": "Operating system level error",
    },
}


class ErrorAnalyser:
    """Parses, categorizes, and suggests fixes for errors."""

    def __init__(self):
        self.reader = FileReader()

    def analyze_error(self, error_message, traceback_str=None, file_path=None):
        """
        Analyze an error message and return structured info.

        Returns dict: {category, error_type, message, file, line, suggestions}
        """
        full_text = error_message
        if traceback_str:
            full_text = traceback_str + "\n" + error_message

        result = {
            "category": "unknown",
            "error_type": "Unknown",
            "message": error_message.strip(),
            "file": None,
            "line": None,
            "column": None,
            "suggestions": [],
            "context": None,
        }

        # Extract error type
        type_match = re.search(r"(\w+(?:Error|Exception|Warning)):", full_text)
        if type_match:
            result["error_type"] = type_match.group(1)

        # Categorize
        result["category"] = self._categorize(result["error_type"], full_text)

        # Extract file and line
        file_line_match = re.search(r'File "([^"]+)", line (\d+)', full_text)
        if file_line_match:
            result["file"] = file_line_match.group(1)
            result["line"] = int(file_line_match.group(2))

        col_match = re.search(r"line \d+:(\d+)", full_text)
        if col_match:
            result["column"] = int(col_match.group(1))

        # Generate suggestions
        result["suggestions"] = self._generate_suggestions(result, full_text)

        # Get context from file
        if result["file"] and result["line"]:
            result["context"] = self._get_context(result["file"], result["line"])

        log.info(f"Analyzed error: {result['error_type']} [{result['category']}] "
                 f"at {result['file']}:{result['line']}")
        return result

    def analyze_traceback(self, traceback_str):
        """Parse a full traceback string."""
        lines = traceback_str.strip().splitlines()
        if not lines:
            return self.analyze_error("Empty traceback")

        # Last line usually has the error type and message
        error_line = lines[-1].strip()
        return self.analyze_error(error_line, traceback_str)

    def analyze_exception(self, exc):
        """Analyze a caught exception object."""
        tb_str = traceback.format_exception(type(exc), exc, exc.__traceback__)
        return self.analyze_traceback("".join(tb_str))

    def _categorize(self, error_type, full_text):
        """Determine the error category."""
        for category, info in ERROR_PATTERNS.items():
            for pattern in info["patterns"]:
                if re.search(pattern, error_type) or re.search(pattern, full_text):
                    return category
        return "unknown"

    def _generate_suggestions(self, result, full_text):
        """Generate fix suggestions based on error category."""
        suggestions = []
        category = result["category"]
        error_type = result["error_type"]

        if category == "syntax":
            if "IndentationError" in error_type or "TabError" in error_type:
                suggestions.append("Check indentation — use consistent spaces or tabs.")
                suggestions.append("Ensure no mixing of tabs and spaces.")
            else:
                suggestions.append("Check for missing colons, parentheses, or brackets.")
                suggestions.append("Verify string quotes are properly closed.")
                suggestions.append("Check for missing commas in lists/dicts/function calls.")

        elif category == "import":
            suggestions.append("Verify the module/package is installed (pip install <name>).")
            suggestions.append("Check the module name spelling.")
            suggestions.append("Ensure the module is in the Python path.")
            suggestions.append("Check for circular imports.")

        elif category == "name":
            suggestions.append("Check variable/function name spelling.")
            suggestions.append("Verify the variable is defined before use.")
            suggestions.append("Check for missing 'global' or 'nonlocal' declarations.")
            suggestions.append("Ensure imports include the referenced name.")

        elif category == "type":
            if "AttributeError" in error_type:
                suggestions.append("Check if the object has the attribute/method being accessed.")
                suggestions.append("Verify the object is not None before accessing attributes.")
                suggestions.append("Check for incorrect variable assignments.")
            else:
                suggestions.append("Check argument types passed to functions.")
                suggestions.append("Verify operations are valid for the given types.")
                suggestions.append("Add type conversion where needed (str(), int(), etc.).")

        elif category == "value":
            if "ZeroDivisionError" in error_type:
                suggestions.append("Add a check for zero before division.")
            else:
                suggestions.append("Validate input values before use.")
                suggestions.append("Add bounds checking for numeric inputs.")

        elif category == "key_index":
            if "KeyError" in error_type:
                suggestions.append("Use dict.get(key, default) for safe access.")
                suggestions.append("Check if the key exists before accessing (key in dict).")
            else:
                suggestions.append("Check list length before accessing by index.")
                suggestions.append("Use try/except IndexError for safe access.")

        elif category == "file_io":
            if "FileNotFoundError" in error_type:
                suggestions.append("Verify the file path is correct.")
                suggestions.append("Check if the file exists before opening (os.path.exists).")
                suggestions.append("Ensure the working directory is correct.")
            elif "PermissionError" in error_type:
                suggestions.append("Check file permissions (chmod).")
                suggestions.append("Run with appropriate user privileges.")

        elif category == "runtime":
            if "RecursionError" in error_type:
                suggestions.append("Add a base case to the recursive function.")
                suggestions.append("Consider an iterative approach instead of recursion.")
                suggestions.append("Increase recursion limit if necessary (sys.setrecursionlimit).")
            else:
                suggestions.append("Review the logic flow.")
                suggestions.append("Add debug logging to trace execution.")

        elif category == "os":
            suggestions.append("Check system resources and permissions.")
            suggestions.append("Verify environment variables are set correctly.")

        else:
            suggestions.append("Review the error message and stack trace.")
            suggestions.append("Search for the error type in documentation.")

        return suggestions

    def _get_context(self, file_path, line_num, context=3):
        """Get surrounding lines of context from a file."""
        lines = self.reader.read_lines(file_path)
        if not lines:
            return None

        start = max(0, line_num - 1 - context)
        end = min(len(lines), line_num + context)

        context_lines = []
        for i in range(start, end):
            marker = ">>>" if i == line_num - 1 else "   "
            context_lines.append(f"{marker} {i+1:4d} | {lines[i]}")

        return "\n".join(context_lines)

    def check_file_for_errors(self, file_path):
        """Check a Python file for syntax errors."""
        content = self.reader.read(file_path)
        if content is None:
            return {"has_errors": True, "errors": ["Cannot read file"]}

        if not file_path.endswith(".py"):
            return {"has_errors": False, "errors": []}

        errors = []

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            errors.append({
                "type": "SyntaxError",
                "message": e.msg,
                "line": e.lineno,
                "column": e.offset,
                "file": file_path,
            })

        return {
            "has_errors": len(errors) > 0,
            "errors": errors,
        }