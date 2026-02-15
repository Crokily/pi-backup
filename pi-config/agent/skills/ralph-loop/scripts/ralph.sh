#!/bin/bash
# Ralph Loop for Pi — Autonomous AI agent loop
# Usage: ralph.sh [--prd path/to/prd.json] [max_iterations]
#
# Spawns fresh pi instances repeatedly, each executing one user story
# from prd.json until all stories pass or max iterations reached.

set -e

# --- Parse arguments ---
MAX_ITERATIONS=10
PRD_PATH=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --prd)
      PRD_PATH="$2"
      shift 2
      ;;
    --prd=*)
      PRD_PATH="${1#*=}"
      shift
      ;;
    -h|--help)
      echo "Usage: ralph.sh [--prd path/to/prd.json] [max_iterations]"
      echo ""
      echo "Options:"
      echo "  --prd PATH    Path to prd.json (default: ./prd.json)"
      echo "  max_iterations Number of iterations (default: 10)"
      echo ""
      echo "Environment:"
      echo "  RALPH_MODEL   Model to use with pi (optional)"
      echo "  RALPH_PROFILE Pi profile to use (optional)"
      exit 0
      ;;
    *)
      if [[ "$1" =~ ^[0-9]+$ ]]; then
        MAX_ITERATIONS="$1"
      fi
      shift
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

# Find prd.json
if [ -z "$PRD_PATH" ]; then
  PRD_PATH="./prd.json"
fi

if [ ! -f "$PRD_PATH" ]; then
  echo "Error: prd.json not found at $PRD_PATH"
  echo "Create one first: ask pi to 'create a PRD and convert to prd.json'"
  exit 1
fi

PRD_DIR="$(cd "$(dirname "$PRD_PATH")" && pwd)"
PRD_FILE="$PRD_DIR/$(basename "$PRD_PATH")"
PROGRESS_FILE="$PRD_DIR/progress.txt"
ARCHIVE_DIR="$PRD_DIR/archive"
LAST_BRANCH_FILE="$PRD_DIR/.ralph-last-branch"

# --- Check dependencies ---
if ! command -v pi &> /dev/null; then
  echo "Error: 'pi' command not found. Install pi coding agent first."
  exit 1
fi

if ! command -v jq &> /dev/null; then
  echo "Error: 'jq' not found. Install with: sudo apt install jq"
  exit 1
fi

# --- Archive previous run if branch changed ---
if [ -f "$PRD_FILE" ] && [ -f "$LAST_BRANCH_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  LAST_BRANCH=$(cat "$LAST_BRANCH_FILE" 2>/dev/null || echo "")

  if [ -n "$CURRENT_BRANCH" ] && [ -n "$LAST_BRANCH" ] && [ "$CURRENT_BRANCH" != "$LAST_BRANCH" ]; then
    DATE=$(date +%Y-%m-%d)
    FOLDER_NAME=$(echo "$LAST_BRANCH" | sed 's|^ralph/||')
    ARCHIVE_FOLDER="$ARCHIVE_DIR/$DATE-$FOLDER_NAME"

    echo "📦 Archiving previous run: $LAST_BRANCH → $ARCHIVE_FOLDER"
    mkdir -p "$ARCHIVE_FOLDER"
    [ -f "$PRD_FILE" ] && cp "$PRD_FILE" "$ARCHIVE_FOLDER/"
    [ -f "$PROGRESS_FILE" ] && cp "$PROGRESS_FILE" "$ARCHIVE_FOLDER/"

    # Reset progress for new run
    echo "# Ralph Progress Log" > "$PROGRESS_FILE"
    echo "Started: $(date)" >> "$PROGRESS_FILE"
    echo "---" >> "$PROGRESS_FILE"
  fi
fi

# Track current branch
if [ -f "$PRD_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  if [ -n "$CURRENT_BRANCH" ]; then
    echo "$CURRENT_BRANCH" > "$LAST_BRANCH_FILE"
  fi
fi

# Initialize progress file
if [ ! -f "$PROGRESS_FILE" ]; then
  echo "# Ralph Progress Log" > "$PROGRESS_FILE"
  echo "Started: $(date)" >> "$PROGRESS_FILE"
  echo "---" >> "$PROGRESS_FILE"
fi

# --- Pre-flight status ---
TOTAL_STORIES=$(jq '.userStories | length' "$PRD_FILE")
DONE_STORIES=$(jq '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE")
REMAINING=$((TOTAL_STORIES - DONE_STORIES))

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              🤖 Ralph Loop for Pi                        ║"
echo "╠═══════════════════════════════════════════════════════════╣"
echo "║  PRD:        $(printf '%-43s' "$PRD_FILE") ║"
echo "║  Stories:    $DONE_STORIES/$TOTAL_STORIES complete ($REMAINING remaining)                    ║"
echo "║  Iterations: max $MAX_ITERATIONS                                      ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

if [ "$REMAINING" -eq 0 ]; then
  echo "✅ All stories already complete!"
  exit 0
fi

# --- Build the prompt ---
PROMPT_TEMPLATE="$SCRIPT_DIR/prompt.md"

# --- Main Loop ---
for i in $(seq 1 $MAX_ITERATIONS); do
  # Check remaining stories
  DONE_STORIES=$(jq '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE")
  REMAINING=$((TOTAL_STORIES - DONE_STORIES))

  if [ "$REMAINING" -eq 0 ]; then
    echo ""
    echo "✅ All stories complete! Finished at iteration $i."
    exit 0
  fi

  # Show current story
  NEXT_STORY=$(jq -r '[.userStories[] | select(.passes == false)] | sort_by(.priority) | .[0] | "\(.id): \(.title)"' "$PRD_FILE")

  echo ""
  echo "═══════════════════════════════════════════════════════════"
  echo "  🔄 Iteration $i of $MAX_ITERATIONS — $REMAINING stories remaining"
  echo "  📋 Next: $NEXT_STORY"
  echo "═══════════════════════════════════════════════════════════"
  echo ""

  # Build pi command
  PI_CMD="pi"
  if [ -n "$RALPH_MODEL" ]; then
    PI_CMD="$PI_CMD -m $RALPH_MODEL"
  fi
  if [ -n "$RALPH_PROFILE" ]; then
    PI_CMD="$PI_CMD --profile $RALPH_PROFILE"
  fi

  # Run pi with the prompt, piping it as input
  # Using --print mode for non-interactive execution
  OUTPUT=$($PI_CMD --print < "$PROMPT_TEMPLATE" 2>&1 | tee /dev/stderr) || true

  # Check for completion signal
  if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║  ✅ Ralph completed all tasks!                           ║"
    echo "║  Finished at iteration $i of $MAX_ITERATIONS                        ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    exit 0
  fi

  echo ""
  echo "  ✓ Iteration $i complete. Continuing in 3s..."
  sleep 3
done

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  ⚠️  Ralph reached max iterations ($MAX_ITERATIONS)                    ║"
echo "║  Check progress.txt for status.                          ║"
echo "╚═══════════════════════════════════════════════════════════╝"

# Final status
DONE_STORIES=$(jq '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE")
echo ""
echo "Final status: $DONE_STORIES/$TOTAL_STORIES stories completed"
jq '.userStories[] | "\(.id): \(.title) — \(if .passes then "✅" else "❌" end)"' "$PRD_FILE" -r

exit 1
