#!/usr/bin/env python3
"""
Migrate existing bash/script tools to proper pi extensions.

Usage:
    python3 migrate-to-extension.py web-search

This script helps convert ad-hoc tools (bash scripts, binaries) into
proper pi extensions that follow official standards.
"""

import os
import sys
from pathlib import Path
from typing import Optional


EXTENSION_TEMPLATE = '''import type {{ ExtensionAPI }} from "@mariozechner/pi-coding-agent";
import {{ Type }} from "@sinclair/typebox";
import {{
  truncateHead,
  DEFAULT_MAX_BYTES,
  DEFAULT_MAX_LINES,
}} from "@mariozechner/pi-coding-agent";

export default function (pi: ExtensionAPI) {{
  pi.registerTool({{
    name: "{tool_name}",
    label: "{tool_label}",
    description: "{tool_description}",
    parameters: Type.Object({{
      {parameters}
    }}),

    async execute(toolCallId, params, signal, onUpdate, ctx) {{
      // Check cancellation
      if (signal?.aborted) {{
        return {{ content: [{{ type: "text", text: "Cancelled" }}] }};
      }}

      // Execute command
      const result = await pi.exec(
        "{command}",
        {command_args},
        {{ signal, timeout: 30000 }}
      );

      if (result.code !== 0) {{
        return {{
          content: [{{ type: "text", text: `Error: ${{result.stderr}}` }}],
          details: {{ error: result.stderr, exitCode: result.code }}
        }};
      }}

      // Truncate output
      const truncation = truncateHead(result.stdout, {{
        maxLines: DEFAULT_MAX_LINES,
        maxBytes: DEFAULT_MAX_BYTES,
      }});

      let output = truncation.content;
      if (truncation.truncated) {{
        output += `\\n[Output truncated: ${{truncation.outputLines}}/${{truncation.totalLines}} lines]`;
      }}

      return {{
        content: [{{ type: "text", text: output }}],
        details: {{ exitCode: result.code }}
      }};
    }}
  }});
}}
'''


def generate_web_search_extension() -> str:
    """Generate web-search extension."""
    return '''import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import {
  truncateHead,
  DEFAULT_MAX_BYTES,
  DEFAULT_MAX_LINES,
} from "@mariozechner/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "web_search",
    label: "Web Search",
    description: "Search the web via Bing RSS and optionally fetch page content using r.jina.ai mirror",
    parameters: Type.Object({
      query: Type.String({ description: "Search query keywords" }),
      limit: Type.Optional(Type.Number({
        description: "Number of results (1-20)",
        default: 5,
        minimum: 1,
        maximum: 20
      })),
      fetchContent: Type.Optional(Type.Number({
        description: "Fetch readable content for Nth result (1-based)"
      })),
    }),

    async execute(toolCallId, params, signal, onUpdate, ctx) {
      // Check cancellation
      if (signal?.aborted) {
        return { content: [{ type: "text", text: "Search cancelled" }] };
      }

      // Build arguments
      const args = [params.query, "-n", String(params.limit ?? 5)];
      if (params.fetchContent) {
        args.push("--open", String(params.fetchContent));
      }

      // Show progress
      onUpdate?.({
        content: [{ type: "text", text: `Searching: ${params.query}...` }]
      });

      // Execute search
      const result = await pi.exec(
        "python3",
        ["/home/ubuntu/web_search.py", ...args],
        { signal, timeout: 45000 }
      );

      if (result.code !== 0) {
        return {
          content: [{ type: "text", text: `Search failed: ${result.stderr}` }],
          details: { error: result.stderr, exitCode: result.code }
        };
      }

      // Truncate output
      const truncation = truncateHead(result.stdout, {
        maxLines: DEFAULT_MAX_LINES,
        maxBytes: DEFAULT_MAX_BYTES,
      });

      let output = truncation.content;
      if (truncation.truncated) {
        output += `\\n\\n[Output truncated: ${truncation.outputLines} of ${truncation.totalLines} lines`;
        output += `, full output saved]`;
      }

      return {
        content: [{ type: "text", text: output }],
        details: {
          query: params.query,
          resultCount: params.limit,
          exitCode: result.code
        }
      };
    }
  });
}
'''


def generate_fd_extension() -> str:
    """Generate fd (fast find) extension."""
    return '''import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { StringEnum } from "@mariozechner/pi-ai";
import {
  truncateHead,
  DEFAULT_MAX_BYTES,
  DEFAULT_MAX_LINES,
} from "@mariozechner/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  const FD_BIN = "~/.pi/agent/bin/fd";

  pi.registerTool({
    name: "find_fast",
    label: "Fast Find",
    description: "Fast file search using fd - much faster than traditional find for locating files by name or pattern",
    parameters: Type.Object({
      pattern: Type.String({ description: "File name pattern or regex" }),
      path: Type.Optional(Type.String({
        description: "Directory to search in",
        default: "."
      })),
      type: Type.Optional(StringEnum(["file", "directory", "symlink"] as const, {
        description: "Filter by type"
      })),
      extension: Type.Optional(Type.String({
        description: "Filter by file extension (e.g., 'ts', 'py')"
      })),
      hidden: Type.Optional(Type.Boolean({
        description: "Include hidden files",
        default: false
      })),
    }),

    async execute(toolCallId, params, signal, onUpdate, ctx) {
      if (signal?.aborted) {
        return { content: [{ type: "text", text: "Search cancelled" }] };
      }

      // Build fd arguments
      const args: string[] = [params.pattern];
      
      if (params.path && params.path !== ".") {
        args.push(params.path);
      }

      if (params.type) {
        args.push("--type", params.type.charAt(0)); // f, d, l
      }

      if (params.extension) {
        args.push("--extension", params.extension);
      }

      if (params.hidden) {
        args.push("--hidden");
      }

      // Execute fd
      const result = await pi.exec(FD_BIN, args, {
        signal,
        timeout: 10000
      });

      if (result.code !== 0 && result.code !== 1) { // Exit 1 = no matches (ok)
        return {
          content: [{ type: "text", text: `Error: ${result.stderr}` }],
          details: { error: result.stderr, exitCode: result.code }
        };
      }

      const stdout = result.stdout.trim();
      if (!stdout) {
        return {
          content: [{ type: "text", text: `No files found matching: ${params.pattern}` }],
          details: { matchCount: 0 }
        };
      }

      // Count and truncate results
      const lines = stdout.split("\\n");
      const truncation = truncateHead(stdout, {
        maxLines: DEFAULT_MAX_LINES,
        maxBytes: DEFAULT_MAX_BYTES,
      });

      let output = truncation.content;
      if (truncation.truncated) {
        output += `\\n\\n[Showing ${truncation.outputLines} of ${lines.length} matches]`;
      } else {
        output += `\\n\\n[Found ${lines.length} matches]`;
      }

      return {
        content: [{ type: "text", text: output }],
        details: {
          pattern: params.pattern,
          matchCount: lines.length,
          truncated: truncation.truncated
        }
      };
    }
  });
}
'''


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 migrate-to-extension.py <tool-name>")
        print("Available: web-search, fd")
        sys.exit(1)

    tool_name = sys.argv[1]
    output_dir = Path.home() / ".pi" / "agent" / "extensions"
    output_dir.mkdir(parents=True, exist_ok=True)

    if tool_name == "web-search":
        content = generate_web_search_extension()
        output_file = output_dir / "web-search.ts"
    elif tool_name == "fd":
        content = generate_fd_extension()
        output_file = output_dir / "fast-find.ts"
    else:
        print(f"Unknown tool: {tool_name}")
        print("Available: web-search, fd")
        sys.exit(1)

    output_file.write_text(content)
    print(f"✅ Generated: {output_file}")
    print(f"")
    print(f"Next steps:")
    print(f"1. Test: pi -e {output_file}")
    print(f"2. If working, the tool will auto-load on next pi start")
    print(f"3. Use /reload in pi to hot-reload without restart")


if __name__ == "__main__":
    main()
