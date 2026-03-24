#!/bin/bash
# budget.sh — Check remaining time and budget for this agent session.

NOW=$(date +%s)

# Time remaining
if [ -n "$AGENT_TIME_DEADLINE" ]; then
  REMAINING_SECS=$((AGENT_TIME_DEADLINE - NOW))
  if [ "$REMAINING_SECS" -lt 0 ]; then REMAINING_SECS=0; fi
  echo "Remaining time: ${REMAINING_SECS} seconds"
else
  echo "Remaining time: unknown (AGENT_TIME_DEADLINE not set)"
fi

# Budget remaining
if [ -n "$AGENT_BUDGET_CAP_USD" ] && [ -n "$CCUSAGE_COMMAND" ]; then
  CURRENT_COST=$($CCUSAGE_COMMAND session --json 2>/dev/null \
    | jq -r '(.sessions[0].totalCost // 0)')
  if [ $? -eq 0 ] && [ -n "$CURRENT_COST" ]; then
    REMAINING=$(echo "$AGENT_BUDGET_CAP_USD - $CURRENT_COST" | bc -l)
    printf "Remaining budget: %.2f USD\n" "$REMAINING"
  else
    echo "Remaining budget: unknown (ccusage failed)"
  fi
else
  echo "Remaining budget: unknown (AGENT_BUDGET_CAP_USD or CCUSAGE_COMMAND not set)"
fi
