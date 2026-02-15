import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
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
      const lines = stdout.split("\n");
      const truncation = truncateHead(stdout, {
        maxLines: DEFAULT_MAX_LINES,
        maxBytes: DEFAULT_MAX_BYTES,
      });

      let output = truncation.content;
      if (truncation.truncated) {
        output += `\n\n[Showing ${truncation.outputLines} of ${lines.length} matches]`;
      } else {
        output += `\n\n[Found ${lines.length} matches]`;
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
