"""Language detection and symbol pattern definitions for code_map."""

from __future__ import annotations

import re
from pathlib import Path

EXTENSION_MAP: dict[str, str] = {
    ".py": "Python",
    ".pyw": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin Script",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".scala": "Scala",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".cbl": "COBOL",
    ".cob": "COBOL",
    ".cobol": "COBOL",
    ".cpy": "COBOL Copybook",
    ".bas": "VBA",
    ".cls": "VBA",
    ".frm": "VBA",
    ".lss": "LotusScript",
}

SYMBOL_PATTERNS: dict[str, list[str]] = {
    "Python": [
        r"^\s*class\s+(\w+)",
        r"^\s*async\s+def\s+(\w+)",
        r"^\s*def\s+(\w+)",
    ],
    "TypeScript": [
        r"(?:export\s+)?(?:default\s+)?class\s+(\w+)",
        r"(?:export\s+)?interface\s+(\w+)",
        r"(?:export\s+)?type\s+(\w+)",
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        r"(?:export\s+)?const\s+(\w+)\s*[=:]",
        r"(?:export\s+)?enum\s+(\w+)",
        r"(?:export\s+)?abstract\s+class\s+(\w+)",
    ],
    "JavaScript": [
        r"(?:export\s+)?(?:default\s+)?class\s+(\w+)",
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        r"(?:export\s+)?const\s+(\w+)\s*[=:]",
    ],
    "Go": [
        r"^func\s+(?:\([^)]+\)\s+)?(\w+)",
        r"^type\s+(\w+)\s+struct",
        r"^type\s+(\w+)\s+interface",
    ],
    "Rust": [
        r"^fn\s+(\w+)",
        r"^pub\s+fn\s+(\w+)",
        r"^struct\s+(\w+)",
        r"^enum\s+(\w+)",
        r"^trait\s+(\w+)",
        r"^impl(?:\s*<[^>]+>)?\s+(\w+)",
        r"^mod\s+(\w+)",
        r"^type\s+(\w+)",
    ],
    "C": [
        r"^struct\s+(\w+)",
        r"^enum\s+(\w+)",
        r"^#define\s+(\w+)",
        r"^(?:static\s+)?(?:inline\s+)?(?:\w+\s+)+\*?\w+\s*\([^)]*\)\s*\{",
        r"^(?:void|int|char|long|float|double|size_t|uint\d+_t|int\d+_t)\s+\*?(\w+)\s*\(",
    ],
    "C++": [
        r"^class\s+(\w+)",
        r"^struct\s+(\w+)",
        r"^enum\s+(\w+)",
        r"^namespace\s+(\w+)",
        r"^template\s*<",
        r"^(?:virtual\s+)?(?:void|int|char|long|float|double|bool|std::\w+|\w+)\s+\*?(\w+)\s*\(",
    ],
    "C#": [
        r"^(?:\s*(?:public|private|protected|internal|static|virtual|override|abstract|sealed|partial|readonly)\s+)*(?:class|interface|struct|enum|record)\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal|static|virtual|override|abstract|sealed|partial|async|readonly)\s+)*(?:void|int|string|bool|long|double|float|decimal|char|byte|short|Task|ValueTask|IEnumerable|IActionResult|ActionResult|IActionResult|JsonResult|Task<[^>]+>|Task<(?:IEnumerable<[^>]+>|List<[^>]+>|ActionResult<[^>]+>|[A-Z]\w+))>\s+(\w+)\s*\(",
    ],
    "Java": [
        r"^(?:\s*(?:public|private|protected|static|final|abstract|synchronized)\s+)*(?:class|interface|enum|@interface|record)\s+(\w+)",
        r"@(\w+)",
        r"^(?:\s*(?:public|private|protected|static|final|abstract|synchronized)\s+)*(?:void|[A-Z]\w*|int|long|double|float|boolean|char|byte|short|String|List|Map|Set|Optional|Stream)\s*(?:<[^>]+>)?\s+(\w+)\s*\(",
    ],
    "Kotlin": [
        r"^(?:\s*(?:public|private|protected|internal|open|data|sealed|abstract|override)\s+)*(?:class|data class|sealed class|abstract class|open class|inner class)\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal|open|abstract|override)\s+)*interface\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal)\s+)*object\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal)\s+)*fun\s+(\w+)",
        r"^(?:\s*(?:public|private|protected|internal)\s+)*enum class\s+(\w+)",
    ],
    "Swift": [
        r"^(?:\s*(?:public|private|internal|fileprivate|open)\s+)*(?:class|struct|enum|protocol|extension)\s+(\w+)",
        r"^(?:\s*(?:public|private|internal|fileprivate|open)\s+)*func\s+(\w+)",
        r"^(?:\s*(?:public|private|internal|fileprivate|open)\s+)*var\s+(\w+)",
    ],
    "Ruby": [
        r"^\s*class\s+(\w+)",
        r"^\s*module\s+(\w+)",
        r"^\s*def\s+(?:self\.)?(\w+)",
    ],
    "PHP": [
        r"^\s*(?:abstract\s+|final\s+)?class\s+(\w+)",
        r"^\s*interface\s+(\w+)",
        r"^\s*trait\s+(\w+)",
        r"^\s*(?:public|private|protected|static)\s+function\s+(\w+)",
    ],
    "Scala": [
        r"^\s*(?:case\s+)?class\s+(\w+)",
        r"^\s*object\s+(\w+)",
        r"^\s*trait\s+(\w+)",
        r"^\s*def\s+(\w+)",
    ],
    "Dart": [
        r"^\s*class\s+(\w+)",
        r"^\s*(?:Future|Stream|void|int|String|bool|double|List|Map|Set)\s*<?[^>]*>?\s+(\w+)\s*\(",
    ],
    "Lua": [
        r"^\s*function\s+(\w+)",
        r"^\s*local\s+function\s+(\w+)",
    ],
    "Objective-C": [
        r"^\s*@interface\s+(\w+)",
        r"^\s*@protocol\s+(\w+)",
        r"^\s*@implementation\s+(\w+)",
        r"^\s*-\s*\([^)]*\)\s*(\w+)",
        r"^\s*\+\s*\([^)]*\)\s*(\w+)",
    ],
    "Objective-C++": [
        r"^\s*@interface\s+(\w+)",
        r"^\s*@protocol\s+(\w+)",
        r"^\s*@implementation\s+(\w+)",
        r"^\s*class\s+(\w+)",
        r"^\s*namespace\s+(\w+)",
    ],
    "VBA": [
        r"^\s*(?:Public\s+|Private\s+|Friend\s+|Static\s+)*(?:Async\s+)?Sub\s+(\w+)",
        r"^\s*(?:Public\s+|Private\s+|Friend\s+|Static\s+)*(?:Async\s+)?Function\s+(\w+)",
        r"^\s*(?:Public\s+|Private\s+)*(?:Property\s+)(?:Get|Let|Set)\s+(\w+)",
        r"^\s*(?:Public\s+|Private\s+)*(?:Type|Enum|Class)\s+(\w+)",
    ],
    "LotusScript": [
        r"^\s*(?:Public\s+|Private\s+)?(?:Sub|Function)\s+(\w+)",
        r"^\s*Property\s+(?:Get|Set)\s+(\w+)",
    ],
}


RELATION_LANGUAGES: set[str] = {
    "Python",
    "TypeScript",
    "JavaScript",
    "TypeScript (React)",
    "JavaScript (React)",
    "Go",
    "Rust",
    "COBOL",
    "COBOL Copybook",
    "Java",
    "Kotlin",
    "Kotlin Script",
    "Scala",
    "C",
    "C++",
    "C/C++ Header",
    "Objective-C",
    "Objective-C++",
    "C#",
    "PHP",
    "Ruby",
    "Swift",
    "Dart",
    "Lua",
    "R",
    "VBA",
    "LotusScript",
}


def detect_source_language(filepath: str) -> str:
    """Detect ambiguous header language using conservative content heuristics."""
    ext = Path(filepath).suffix.lower()
    if ext not in (".h", ".hpp"):
        return EXTENSION_MAP.get(ext, "Unknown")
    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return EXTENSION_MAP.get(ext, "Unknown")
    if re.search(
        r"@(?:interface|implementation|protocol|property|class|end)\b|#\s*import\b",
        text,
    ):
        return "Objective-C" if ext == ".h" else "Objective-C++"
    if re.search(r"\b(?:namespace|template|class)\b|std::|#\s*include\s*<", text):
        return "C++ Header"
    return "C/C++ Header"
