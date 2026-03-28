import type {
  ExtensionAPI,
  ExtensionContext,
} from "@mariozechner/pi-coding-agent";

type ThinkingLevel = "off" | "minimal" | "low" | "medium" | "high" | "xhigh";

interface ModelRef {
  provider?: string;
  id?: string;
}

interface AssistantTurnMessage {
  role?: string;
  stopReason?: string;
  errorMessage?: string;
}

interface FallbackCandidate {
  provider: string;
  id: string;
  thinking: ThinkingLevel;
}

const STATUS_KEY = "model-fallback";
const REPORT_SKILL_PATH = "/home/ubuntu/.pi/agent/skills/discord-agent";
const REPORT_MODEL = "openai-codex/gpt-5.4:low";
const MAX_FAILURE_HISTORY = 8;

const USER_ABORT_PATTERNS: RegExp[] = [
  /aborted by user/i,
  /cancelled by user/i,
  /canceled by user/i,
  /keyboard interrupt/i,
  /interrupted by user/i,
];

const SUCCESS_STOP_REASONS = new Set(["stop", "length", "toolUse"]);

const FALLBACK_CANDIDATES: readonly FallbackCandidate[] = [
  {
    provider: "openai-codex",
    id: "gpt-5.4",
    thinking: "low",
  },
  {
    provider: "openai-codex",
    id: "gpt-5.3-codex",
    thinking: "xhigh",
  },
] as const;

function asAssistantTurnMessage(message: unknown): AssistantTurnMessage | null {
  if (!message || typeof message !== "object") return null;
  return message as AssistantTurnMessage;
}

function summarizeText(value: unknown, maxLength = 240): string {
  const text = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 3)}...`;
}

function getFailureReason(message: unknown): string {
  return summarizeText(asAssistantTurnMessage(message)?.errorMessage);
}

function isUserAbortReason(reason: string): boolean {
  return USER_ABORT_PATTERNS.some((pattern) => pattern.test(reason));
}

function isModelFailure(message: unknown): boolean {
  const assistantMessage = asAssistantTurnMessage(message);
  if (!assistantMessage || assistantMessage.role !== "assistant") return false;

  if (assistantMessage.stopReason === "error") return true;

  if (assistantMessage.stopReason === "aborted") {
    const reason = getFailureReason(message);
    return reason.length > 0 && !isUserAbortReason(reason);
  }

  return false;
}

function isSuccessfulAssistantTurn(message: unknown): boolean {
  const assistantMessage = asAssistantTurnMessage(message);
  if (!assistantMessage || assistantMessage.role !== "assistant") return false;
  return SUCCESS_STOP_REASONS.has(assistantMessage.stopReason ?? "");
}

function formatModelRef(model: ModelRef | null | undefined): string {
  const provider = model?.provider ?? "unknown-provider";
  const id = model?.id ?? "unknown-model";
  return `${provider}/${id}`;
}

function formatCandidate(candidate: FallbackCandidate): string {
  return `${candidate.provider}/${candidate.id} (thinking=${candidate.thinking})`;
}

function findCandidateIndex(model: ModelRef | null | undefined): number {
  return FALLBACK_CANDIDATES.findIndex(
    (candidate) =>
      candidate.provider === model?.provider && candidate.id === model?.id
  );
}

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'"'"'`)}'`;
}

function formatUnknownError(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return summarizeText((error as { message?: unknown }).message, 200);
  }
  return summarizeText(error, 200) || "unknown error";
}

function setFallbackStatus(ctx: ExtensionContext, text?: string) {
  if (!ctx.hasUI) return;
  ctx.ui.setStatus(STATUS_KEY, text);
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
  let consecutiveFailures = 0;
  let switching = false;
  let recoveryPending = false;
  let failureHistory: string[] = [];

  function resetFailureCycle(ctx: ExtensionContext) {
    consecutiveFailures = 0;
    recoveryPending = false;
    failureHistory = [];
    switching = false;
    setFallbackStatus(ctx, undefined);
  }

  function recordFailure(modelLabel: string, reason: string) {
    const entry = reason ? `${modelLabel}: ${reason}` : `${modelLabel}: model failure`;
    failureHistory = [...failureHistory, entry].slice(-MAX_FAILURE_HISTORY);
  }

  async function launchRecoveryReport(
    ctx: ExtensionContext,
    recoveredModel: string,
    failuresBeforeRecovery: number,
    capturedFailureHistory: string[]
  ) {
    const reportLines = [
      "你是一个后台告警任务。",
      "请使用 discord-agent skill 发送一条模型切换恢复通知到 Discord。",
      "优先直接执行：python3 /home/ubuntu/discord-agent/send_notification.py <消息>。",
      "不要询问交互确认，发送后只输出“已发送”。",
      `Recovered model: ${recoveredModel}`,
      `Failures before recovery: ${failuresBeforeRecovery}`,
      "Failure history:",
      ...(capturedFailureHistory.length > 0
        ? capturedFailureHistory.map((entry, index) => `${index + 1}. ${entry}`)
        : ["1. No detailed failure history captured."]),
    ];

    const prompt = reportLines.join("\n");
    const sessionName = `pi-model-fallback-report-${Date.now()}`;

    const piCommand = [
      "/usr/bin/env",
      "pi",
      "-p",
      "--no-session",
      "--no-extensions",
      "--no-skills",
      "--skill",
      REPORT_SKILL_PATH,
      "--model",
      REPORT_MODEL,
      prompt,
    ]
      .map(shellQuote)
      .join(" ");

    const command = `cd ${shellQuote("/home/ubuntu")} && ${piCommand}`;

    try {
      const result = await pi.exec(
        "tmux",
        ["new-session", "-d", "-s", sessionName, command],
        { timeout: 8000 }
      );

      if (result.code !== 0) {
        const details = summarizeText(result.stderr || result.stdout, 240);
        notify(
          ctx,
          `模型已恢复到 ${recoveredModel}，但启动 Discord 汇报任务失败（tmux exit=${result.code}）${
            details ? `: ${details}` : ""
          }`,
          "warning"
        );
        return;
      }

      notify(
        ctx,
        `模型已恢复到 ${recoveredModel}。已在 tmux 会话 ${sessionName} 启动 Discord 汇报任务（${REPORT_MODEL}）。`,
        "info"
      );
    } catch (error) {
      notify(
        ctx,
        `模型已恢复到 ${recoveredModel}，但启动 Discord 汇报任务异常：${formatUnknownError(error)}`,
        "warning"
      );
    }
  }

  async function switchToNextFallback(
    ctx: ExtensionContext,
    failedModel: string,
    failureReason: string
  ) {
    const currentCandidateIndex = findCandidateIndex(ctx.model);
    const startIndex = Math.max(currentCandidateIndex + 1, 0);
    const skippedCandidates: string[] = [];

    for (let index = startIndex; index < FALLBACK_CANDIDATES.length; index += 1) {
      const candidate = FALLBACK_CANDIDATES[index];
      const candidateLabel = formatCandidate(candidate);

      setFallbackStatus(
        ctx,
        `Failure ${consecutiveFailures}: trying ${candidate.provider}/${candidate.id} (${index + 1}/${FALLBACK_CANDIDATES.length})`
      );

      const nextModel = ctx.modelRegistry.find(candidate.provider, candidate.id);
      if (!nextModel) {
        skippedCandidates.push(`${candidateLabel} not found`);
        continue;
      }

      const switched = await pi.setModel(nextModel);
      if (!switched) {
        skippedCandidates.push(`${candidateLabel} unavailable`);
        continue;
      }

      pi.setThinkingLevel(candidate.thinking);
      setFallbackStatus(
        ctx,
        `Fallback active: ${candidate.provider}/${candidate.id} (${index + 1}/${FALLBACK_CANDIDATES.length})`
      );

      let message = `Model failure on ${failedModel}`;
      if (failureReason) {
        message += `: ${failureReason}`;
      }
      message += `. Switched to ${candidateLabel}.`;
      if (skippedCandidates.length > 0) {
        message += ` Skipped: ${skippedCandidates.join("; ")}.`;
      }
      notify(ctx, message, "warning");
      return;
    }

    setFallbackStatus(
      ctx,
      `Fallback exhausted after ${consecutiveFailures} failure${consecutiveFailures === 1 ? "" : "s"}`
    );

    let message = `Model failure on ${failedModel}`;
    if (failureReason) {
      message += `: ${failureReason}`;
    }
    message += ". No remaining fallback models are available.";
    if (skippedCandidates.length > 0) {
      message += ` Checked: ${skippedCandidates.join("; ")}.`;
    }
    notify(ctx, message, "error");
  }

  pi.on("session_start", async (_event, ctx) => {
    resetFailureCycle(ctx);
  });

  pi.on("turn_end", async (event, ctx) => {
    if (isModelFailure(event.message)) {
      const failedModel = formatModelRef(ctx.model);
      const failureReason = getFailureReason(event.message);

      consecutiveFailures += 1;
      recoveryPending = true;
      recordFailure(failedModel, failureReason);
      setFallbackStatus(ctx, `Failure ${consecutiveFailures}: ${failedModel}`);

      if (!switching) {
        switching = true;
        try {
          await switchToNextFallback(ctx, failedModel, failureReason);
        } finally {
          switching = false;
        }
      }
      return;
    }

    if (recoveryPending && isSuccessfulAssistantTurn(event.message)) {
      const recoveredModel = formatModelRef(ctx.model);
      const failuresBeforeRecovery = consecutiveFailures;
      const capturedFailureHistory = [...failureHistory];

      resetFailureCycle(ctx);
      notify(
        ctx,
        `Model recovered on ${recoveredModel} after ${failuresBeforeRecovery} failure${failuresBeforeRecovery === 1 ? "" : "s"}.`,
        "info"
      );
      void launchRecoveryReport(
        ctx,
        recoveredModel,
        failuresBeforeRecovery,
        capturedFailureHistory
      );
    }
  });
}
