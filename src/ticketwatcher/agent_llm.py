import os
import json
import re
from string import Template
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI


class TicketWatcherAgent:
    """
    Minimal agent wrapper that:
      - Builds the system/user prompts
      - Calls the LLM
      - Enforces the JSON-only response contract
      - Supports an iterative "request_context -> fetch snippets -> propose_patch" loop

    Usage (pseudo):
      agent = TicketWatcherAgent()
      result = agent.run(
          ticket_title="...",
          ticket_body="...",
          snippets=[{"path":"src/app/auth.py","start_line":1,"end_line":120,"code": "..."}]
      )
      if result["action"] == "request_context":
          # fetch the requested slices and call run(...) again, or do a second round with agent.run_round(...)
      elif result["action"] == "propose_patch":
          # validate + apply the unified diff in result["diff"]
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        allowed_paths: Optional[List[str]] = None,
        max_files: int = 4,
        max_total_lines: int = 200,
        default_around_lines: int = 60,
        route_hint: str = "llm",
        system_prompt: Optional[str] = None,
        user_prompt_template: Optional[str] = None,
    ):
        self.model = model or os.getenv("TICKETWATCHER_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        env_allowed = os.getenv("ALLOWED_PATHS")
        env_string = env_allowed if env_allowed is not None else "src/,app/"
        if allowed_paths is None:
            # Honor explicit []/ [""] inputs from callers by only falling back to
            # environment parsing when the argument is None.
            self.allowed_paths = self._parse_allowed_paths_env(env_string)
        else:
            # Copy to avoid accidental mutation and preserve an explicit [] which
            # now signifies "allow everything".
            self.allowed_paths = list(allowed_paths)
        self.max_files = int(os.getenv("MAX_FILES", str(max_files)))
        self.max_total_lines = int(os.getenv("MAX_LINES", str(max_total_lines)))
        self.default_around_lines = int(
            os.getenv("DEFAULT_AROUND_LINES", str(default_around_lines))
        )
        self.route_hint = os.getenv("ROUTE", route_hint)

        # Prompts
        self.sysprompt = system_prompt or (
            "You are TicketFix, an automated code-fixing agent.\n\n"
            "Return EXACTLY ONE JSON object and NOTHING ELSE (no prose, no code fences). It must match ONE of:\n\n"
            "1) Ask for more context:\n"
            "{\n"
            '  "action": "request_context",\n'
            '  "needs": [\n'
            '    { "path": "string", "symbol": "string|null", "line": "integer|null", "around_lines": "integer" }\n'
            "  ],\n"
            '  "reason": "string"\n'
            "}\n\n"
            "2) Propose a minimal patch:\n"
            "{\n"
            '  "action": "propose_patch",\n'
            '  "format": "unified_diff",\n'
            '  "diff": "string (standard unified diff: --- a/<path> / +++ b/<path> …)",\n'
            '  "files_touched": ["string", ...],\n'
            '  "estimated_changed_lines": "integer",\n'
            '  "notes": "string"\n'
            "}\n\n"
            "Rules:\n"
            "- Use request_context when current snippets are insufficient. Each need selects a precise slice: either a symbol OR a line (one can be null). around_lines is typically 60.\n"
            "- Patches MUST respect constraints: allowed_paths only; ≤ max_files; ≤ max_total_lines; no new files unless clearly allowed.\n"
            "- Prefer the smallest safe change. Do not refactor broadly.\n"
            "- Work only from provided snippets and requested slices. Do not assume unseen code.\n"
            '- Output JSON ONLY. If constraints make a safe fix impossible, request_context and explain briefly in "reason".\n'
        )

        self.user_template = user_prompt_template or """
TICKET
Title: $ticket_title
Body:
$ticket_body_trimmed

CONSTRAINTS
allowed_paths: $allowed_paths_csv
max_files: $max_files
max_total_lines: $max_total_lines
default_around_lines: $around_lines
route: $route_hint

CURRENT SNIPPETS
$snippets_block
# Each snippet uses this format, repeated 0..N times:
# --- path: <repo-relative-path>
# --- start_line: <int>
# --- end_line: <int>
# --- code:
# <code lines…>

YOUR TASK
Return ONE of:
(A) { "action": "request_context", "needs": [ { "path": "<string>", "symbol": "<string|null>", "line": "<int|null>", "around_lines": <int> } ... ], "reason": "..." }
    - Use this if more slices are needed. Keep requests inside allowed_paths.
    - Use symbol for functions/classes when known; otherwise provide a line.
(B) { "action": "propose_patch", "format": "unified_diff", "diff": "...", "files_touched": ["..."], "estimated_changed_lines": <int>, "notes": "..." }
    - Unified diff must apply cleanly to current code.
    - Respect max_files and max_total_lines; if exceeded, choose (A) instead.
OUTPUT MUST BE A SINGLE JSON OBJECT ONLY.
"""  
        

    # ---------- public entry points ----------

    def run(
        self,
        ticket_title: str,
        ticket_body: str,
        snippets: List[Dict[str, Any]],
        trim_body_chars: int = 3000,
    ) -> Dict[str, Any]:
        """
        Single round call. Provide any snippets you already have (can be []),
        returns either request_context or propose_patch dict.
        """
        user = self._build_user_prompt(
            ticket_title=ticket_title,
            ticket_body=ticket_body,
            snippets=snippets,
            trim_body_chars=trim_body_chars,
        )
        return self._call_llm(self.sysprompt, user)

    def run_two_rounds(
        self,
        ticket_title: str,
        ticket_body: str,
        seed_snippets: List[Dict[str, Any]],
        fetch_callback,
        # fetch_callback(needs: List[Dict]) -> List[snippet-dicts]
        trim_body_chars: int = 3000,
    ) -> Dict[str, Any]:
        """
        Convenience helper:
          - round 1 with seed snippets
          - if request_context, uses fetch_callback to fetch more slices
          - round 2 with augmented snippets
        Returns the final JSON dict (request_context or propose_patch).
        """
        result = self.run(ticket_title, ticket_body, seed_snippets, trim_body_chars)
        if result.get("action") == "request_context":
            needs = self._sanitize_needs(result.get("needs", []))
            if not needs:
                return result  # nothing to fetch; return as-is
            more = fetch_callback(needs)
            all_snips = seed_snippets + (more or [])
            return self.run(ticket_title, ticket_body, all_snips, trim_body_chars)
        return result

    # ---------- prompt building ----------

    def _build_user_prompt(
        self,
        ticket_title: str,
        ticket_body: str,
        snippets: List[Dict[str, Any]],
        trim_body_chars: int = 3000,
    ) -> str:
        ticket_body_trimmed = (ticket_body or "")[:trim_body_chars]
        snippets_block = self._format_snippets_block(snippets)

        return Template(self.user_template).safe_substitute(
            ticket_title=ticket_title or "",
            ticket_body_trimmed=ticket_body_trimmed,
            allowed_paths_csv=self._format_allowed_paths_for_prompt(),
            max_files=self.max_files,
            max_total_lines=self.max_total_lines,
            around_lines=self.default_around_lines,
            route_hint=self.route_hint,
            snippets_block=snippets_block,
        )

    @staticmethod
    def _format_snippets_block(snippets: List[Dict[str, Any]]) -> str:
        parts = []
        for s in snippets:
            path = s.get("path", "")
            start = int(s.get("start_line", 1))
            end = int(s.get("end_line", max(start, start)))
            code = s.get("code", "")
            parts.append(
                f"--- path: {path}\n--- start_line: {start}\n--- end_line: {end}\n--- code:\n{code}\n"
            )
        return "\n".join(parts) if parts else ""

    # ---------- LLM call & parsing ----------

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()

        # Be defensive: strip code fences if the model added them
        raw = self._strip_code_fences(raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Force a request for context if format is bad (keeps runner simple)
            return {
                "action": "request_context",
                "needs": [],
                "reason": "Model did not return valid JSON. Please provide exact slices you need.",
                "raw": raw[:2000],
            }

        # Validate minimal contract
        action = data.get("action")
        if action not in {"request_context", "propose_patch"}:
            return {
                "action": "request_context",
                "needs": [],
                "reason": "Missing or invalid 'action'. Expected 'request_context' or 'propose_patch'.",
                "raw": raw[:2000],
            }
        return data

    @staticmethod
    def _strip_code_fences(s: str) -> str:
        # Remove ```json ... ``` or ``` ... ```
        s = s.strip()
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
        return s.strip()

    # ---------- helpers ----------

    def _sanitize_needs(self, needs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure each need has path within allowed_paths and sane around_lines."""
        cleaned = []
        for n in needs or []:
            path = (n or {}).get("path", "")
            if not self._path_allowed(path):
                continue
            around = int((n.get("around_lines") or self.default_around_lines))
            around = max(10, min(around, self.default_around_lines))  # cap at default
            out = {
                "path": path,
                "symbol": n.get("symbol"),
                "line": n.get("line"),
                "around_lines": around,
            }
            cleaned.append(out)
        return cleaned

    def _path_allowed(self, path: str) -> bool:
        """Return True if the repo-relative path satisfies the allowlist."""
        if not path:
            return False
        if self._allows_all_paths():
            return True
        return any(path.startswith(pfx) for pfx in self.allowed_paths)

    def _allows_all_paths(self) -> bool:
        """True when the agent is configured without path restrictions."""
        return (not self.allowed_paths) or ("" in self.allowed_paths)

    @staticmethod
    def _parse_allowed_paths_env(s: str) -> List[str]:
        raw_parts = [(p or "").strip() for p in (s or "").split(",")]
        allow_all = any(p == "" for p in raw_parts)

        parts = [p for p in raw_parts if p]
        # normalize to end with slash where appropriate
        norm = []
        for p in parts:
            norm.append(p if p.endswith("/") else (p + ("/" if "." not in p else "")))

        if not norm:
            # An explicit empty entry (or a completely empty env var) means allow all.
            return [""] if allow_all else ["src/"]
        return norm

    def _format_allowed_paths_for_prompt(self) -> str:
        if self._allows_all_paths():
            return "* (all paths allowed)"
        return ",".join(self.allowed_paths)


