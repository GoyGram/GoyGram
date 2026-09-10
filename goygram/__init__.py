# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from importlib.metadata import PackageNotFoundError, version as pkg_version

from .client import GoyGram
from .errors import StopPropagation
from .session import Session
from .utils import print_methods
from .types.kbd import KbdBuilder
from .types.obj import Obj as MemberObj
from .types.obj import Obj as PollObj
from .sugar import html, chunk_text, human_size, human_duration, parse_entities_html, progress_bar, code_block, plural_ru, json_dumps
from .sugar import html_to_entities, extract_sent_message, split_html_text
from .rich import Rich, rich_html

__all__ = ["GoyGram", "Session", "StopPropagation", "KbdBuilder", "PollObj", "MemberObj", "print_methods", "html", "chunk_text", "human_size", "human_duration", "parse_entities_html", "progress_bar", "code_block", "plural_ru", "json_dumps", "html_to_entities", "extract_sent_message", "split_html_text", "Rich", "rich_html"]

from . import filters

try:
    __version__ = pkg_version("goygram")
except PackageNotFoundError:
    __version__ = "0.0.0"
