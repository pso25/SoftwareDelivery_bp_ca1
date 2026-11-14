#!/usr/bin/env bash
# Usage: telemetry-check.sh <site-url> <since>
#
# Continuous telemetry monitoring after a production release. Sends a few
# requests to <site-url>, then reads the app's own telemetry from Application
# Insights (resource APPINSIGHTS_NAME) until those requests show up, which takes
# a few minutes. Fails if the app reported server errors (HTTP 5xx) or
# exceptions since <since> (UTC time the new version went live, ISO 8601), or
# if no telemetry arrives within TELEMETRY_TRIES x 30 seconds (default 20 =
# 10 minutes).
#
# Needs an Azure login that can read the resource (Monitoring Reader).
# Writes a table to the run summary and "line=<result>" to GITHUB_OUTPUT.
set -euo pipefail

url="${1%/}"
since="$2"
name="${APPINSIGHTS_NAME:?APPINSIGHTS_NAME is not set}"
tries="${TELEMETRY_TRIES:-20}"
sent=6

az extension add --name application-insights --upgrade --only-show-errors

group=$(az resource list --name "$name" --resource-type Microsoft.Insights/components \
  --query "[0].resourceGroup" -o tsv)
if [ -z "$group" ]; then
  echo "::error::Application Insights '$name' not found, or the pipeline identity has no Monitoring Reader role on it"
  exit 1
fi

# fresh traffic, so there is telemetry to check even when nobody is using the site
for i in $(seq 1 $((sent / 2))); do
  curl -fsS -o /dev/null --max-time 30 "$url/"
  curl -fsS -o /dev/null --max-time 30 "$url/Privacy"
done

query="let since = datetime($since);
let req = requests | where timestamp > since;
print requests = toscalar(req | count),
      failed = toscalar(req | where toint(resultCode) >= 500 | count),
      exceptions = toscalar(exceptions | where timestamp > since | count)"

requests=0
for i in $(seq 1 "$tries"); do
  result=$(az monitor app-insights query --app "$name" -g "$group" --offset 1h \
    --analytics-query "$query" -o json)
  read -r requests failed exceptions < <(jq -r '.tables[0].rows[0] | @tsv' <<< "$result")
  if [ "$requests" -ge "$sent" ]; then
    break
  fi
  echo "Attempt $i/$tries: $requests of $sent requests in Application Insights so far, waiting"
  sleep 30
done

line="$requests requests, $failed server errors, $exceptions exceptions since $since"
echo "line=$line" >> "$GITHUB_OUTPUT"

if [ "$requests" -eq 0 ]; then
  status="FAILED (no telemetry arrived)"
elif [ "$failed" -gt 0 ] || [ "$exceptions" -gt 0 ]; then
  status="FAILED"
else
  status="passed"
fi

{
  echo "## Telemetry check (production): $status"
  echo "Application Insights \`$name\`, since $since UTC"
  echo "| Measure | Result | Limit |"
  echo "|---|---|---|"
  echo "| Requests | $requests | > 0 |"
  echo "| Server errors (5xx) | $failed | 0 |"
  echo "| Exceptions | $exceptions | 0 |"
} >> "$GITHUB_STEP_SUMMARY"

echo "Telemetry: $line"
if [ "$status" != "passed" ]; then
  echo "::error::Telemetry check $status: $line"
  exit 1
fi
