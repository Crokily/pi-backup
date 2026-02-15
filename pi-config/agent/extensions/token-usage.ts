import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.on("turn_end", (event, ctx) => {
    const message = event.message;
    if (message.role === "assistant" && message.usage) {
      const u = message.usage;
      const stats = `[Last Turn] In: ${u.input} | Out: ${u.output} | Total: ${u.totalTokens}`;
      ctx.ui.setStatus("token-usage", stats);
    }
  });

  pi.on("session_start", (event, ctx) => {
      ctx.ui.setStatus("token-usage", "Token Stats Ready");
  });
}
