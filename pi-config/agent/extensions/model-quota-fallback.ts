import type {
  ExtensionAPI,
  ExtensionContext,
} from "@mariozechner/pi-coding-agent";

const FAILURE_THRESHOLD = 3;
const BACKUP_PROVIDER = "google-gemini-cli";
const BACKUP_MODEL = "gemini-3-pro-preview";
const BACKUP_THINKING_LEVEL = "high" as const;

const QUOTA_PATTERNS: RegExp[] = [
  /exhausted your capacity/i,
  /quota/i,
  /resource[_\s-]?exhausted/i,
  /rate limit/i,
  /too many requests/i,
  /429/i,
];

function isQuotaError(message: unknown): boolean {
  if (!message || typeof message !== "object") return false;

  const m = message as {
    role?: string;
    stopReason?: string;
    errorMessage?: string;
  };

  if (m.role !== "assistant") return false;
  if (m.stopReason !== "error") return false;

  const errorMessage = String(m.errorMessage ?? "");
  return QUOTA_PATTERNS.some((pattern) => pattern.test(errorMessage));
}

function setFallbackStatus(ctx: ExtensionContext, text?: string) {
  if (!ctx.hasUI) return;
  ctx.ui.setStatus("model-fallback", text);
}

function notify(
  ctx: ExtensionContext,
  message: string,
  type: "info" | "warning" | "error"
) {
  if (!ctx.hasUI) return;
  ctx.ui.notify(message, type);
}

export default function (pi: ExtensionAPI) {
  let consecutiveQuotaFailures = 0;
  let switching = false;

  async function switchToBackup(ctx: ExtensionContext) {
    const backupModel = ctx.modelRegistry.find(BACKUP_PROVIDER, BACKUP_MODEL);
    if (!backupModel) {
      notify(
        ctx,
        `检测到连续额度失败，但未找到备用模型 ${BACKUP_PROVIDER}/${BACKUP_MODEL}`,
        "error"
      );
      return;
    }

    const current = ctx.model;
    const alreadyOnBackup =
      current &&
      current.provider === backupModel.provider &&
      current.id === backupModel.id;

    if (alreadyOnBackup) {
      pi.setThinkingLevel(BACKUP_THINKING_LEVEL);
      notify(
        ctx,
        `已在备用模型 ${BACKUP_PROVIDER}/${BACKUP_MODEL}，保持 thinking=${BACKUP_THINKING_LEVEL}`,
        "warning"
      );
      return;
    }

    const switched = await pi.setModel(backupModel);
    if (!switched) {
      notify(
        ctx,
        `检测到连续额度失败，但无法切换到备用模型（缺少可用凭证）：${BACKUP_PROVIDER}/${BACKUP_MODEL}`,
        "error"
      );
      return;
    }

    pi.setThinkingLevel(BACKUP_THINKING_LEVEL);
    notify(
      ctx,
      `检测到额度不足连续失败 ${FAILURE_THRESHOLD} 次，已自动切换到备用模型 ${BACKUP_PROVIDER}/${BACKUP_MODEL}（thinking=${BACKUP_THINKING_LEVEL}）`,
      "warning"
    );
  }

  pi.on("session_start", async (_event, ctx) => {
    consecutiveQuotaFailures = 0;
    switching = false;
    setFallbackStatus(ctx, undefined);
  });

  pi.on("model_select", async (_event, ctx) => {
    consecutiveQuotaFailures = 0;
    setFallbackStatus(ctx, undefined);
  });

  pi.on("turn_end", async (event, ctx) => {
    if (isQuotaError(event.message)) {
      consecutiveQuotaFailures += 1;
      setFallbackStatus(
        ctx,
        `quota-fail ${consecutiveQuotaFailures}/${FAILURE_THRESHOLD}`
      );

      if (consecutiveQuotaFailures >= FAILURE_THRESHOLD && !switching) {
        switching = true;
        try {
          await switchToBackup(ctx);
          consecutiveQuotaFailures = 0;
          setFallbackStatus(ctx, undefined);
        } finally {
          switching = false;
        }
      }
      return;
    }

    if (consecutiveQuotaFailures > 0) {
      consecutiveQuotaFailures = 0;
      setFallbackStatus(ctx, undefined);
    }
  });
}
