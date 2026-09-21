# Jev / TypeSafe API reference (for wiring JevPolicy)

Source: https://docs.typesafe.ai (api.md, quickstart, primitives/choice). Fetched 2026-09-20.

## Endpoint
- `POST https://api.typesafe.ai/v1/systemone`
- Headers: `Authorization: Bearer <API_KEY>`, `Content-Type: application/json`
- API key comes from the dashboard: https://console.typesafe.ai/keys

## Request body
```json
{
  "state": "<plain-text state>",
  "model": "jev-latest",
  "questions": {
    "<question_id>": {
      "type": "choice",
      "instructions": "<the question the model answers>",
      "criteria": { "<option_name>": "<option description>", "...": "..." }
    }
  }
}
```
- `state`: string (or object/array). For us: the animal's perceived, banded plain-text state.
- `questions`: a map; the question id is chosen by us and the model never sees it.
- Choice `criteria`: up to 255 options; BOTH option name and description are sent to the model, so descriptions must be clear. For us the options = the masked available actions.
- Other question types exist (`noul` = yes/no, `score` = rated scale) if we want them later.

## Response body
```json
{
  "model": "jev-1.13.0",
  "answers": {
    "<question_id>": {
      "type": "choice",
      "choice": "<selected option name>",
      "probabilities": { "<option>": 0.0, "...": 1.0 },
      "confidence": 0.0
    }
  },
  "usage": { "input_tokens": 0, "output_tokens": 0 }
}
```
- `choice`: the picked option (highest probability).
- `probabilities`: full distribution over options, sums to 1.
- `confidence`: 0..1, how concentrated the distribution is (a single peak = high, flat = low).

Errors: 401 bad/missing key, 422 validation, 429 rate limited, 529 overloaded.

## How this maps to our design (JevPolicy)
- One Choice question per decision. `state` = the animal's perceived banded state text (hunger/stamina/health/threat/nearest-prey/current-action, etc). `criteria` = the currently-available (masked) actions, each with a one-line description.
- `answers[qid].choice` = the action the animal takes. `confidence` = Jev's calibrated decision confidence = our P(choose). This is about the DECISION, not the outcome.
- CRITICAL (per DESIGN.md): Jev must NEVER be told the action success odds. It decides only from perceived state. Outcome (P(succeed)) is resolved separately by the engine from the matchup + terrain.

## Auth / key
- Set `TYPESAFE_API_KEY` in the environment (do NOT hardcode in source). The engine's JevPolicy reads it from env.
- Key stored securely by aria (see ~/.typesafe/), not committed to this repo.
