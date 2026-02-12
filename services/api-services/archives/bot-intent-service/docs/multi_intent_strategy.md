# Multi-Intent Payment Flow Design

## 1. Objective
Reduce the number of message turns required to complete a payment flow.
enable "One-Shot" commands like:
> "hey how are you?. i want 2 oranges, and 4 aooles deliverered at riverside afternoon i will use mtn to pay"

## 2. Analysis of Current State
- **Intent Service**: Supports Gemini extraction.
- **Constraints**: 
  - Input: <= 450 tokens (The example sentence is ~30-40 tokens, well within limit).
  - Output: <= 150 tokens (Previously 50).
- **Current Limitation**: 
  - The `IntentResponse` schema primarily supports a single `intent` and `slots`.
  - Multi-intent parsing logic exists but buries results in `diagnostics`.
  - Output token limit (50) is too strict for a JSON list of 4+ actions.

## 3. Token Budget Analysis (Output)
For the example payload:
Input: ~35 tokens.

Desired Output JSON (Compact):
```json
{
 "intents": [
  {"id":"add_item", "slots":{"item":"oranges", "qty":2}},
  {"id":"add_item", "slots":{"item":"apples", "qty":4}},
  {"id":"set_delivery", "slots":{"loc":"riverside", "time":"afternoon"}},
  {"id":"set_payment", "slots":{"method":"mtn"}}
 ]
}
```
**Estimated Token Count**: ~90-110 tokens.
**Conclusion**: The requested `< 150` token limit is feasible but requires strict prompt engineering to avoid verbose keys (e.g., using `id` instead of `intent_id`, omitting `confidence` if high).

## 4. Implementation Plan

### Phase 1: Configuration & Schema
1. **Output Token Limit**: Increase `INTENT_GEMINI_MAX_OUTPUT_TOKENS` from `50` to `150`.
2. **Schema Update**: Update `IntentResponse` (in `schemas.py`) to include a top-level `intents` list.
   ```python
   class IntentResponse(BaseModel):
       # ... existing ...
       intents: List[IntentWithSlots] = [] # New field for multi-shot
   ```

### Phase 2: Intent Service Logic
1. **Context Summarizer (New)**:
   - **Requirement**: Condense complex session/cart status into minimal text to fit the 450-token window.
   - **Tooling**: Use Python-based **Structured Reduction** (Template-based) for data, and optionally `sumy` (LSA/TextRank) for long conversation history if needed.
   - **Implementation**:
     - Create `app/services/summarizer.py`.
     - Function `summarize_context(request: IntentRequest) -> str`.
     - Logic:
       - **Cart**: "Cart: 2 items (Oranges x2, Apples x4)." (Dense string).
       - **History**: Last 2 user messages (Raw).
       - **State**: "State: delivering_to_riverside".
   - **Output**: A single string injected into the Gemini prompt as `Context: ...`.

2. **Prompt Engineering**: 
   - Instruct Gemini to return a *pure array* or compact object to save tokens.
   - Example instruction: `Return JSON: {"intents": [{"id": "...", "slots": {...}}]}`.
   - Enforce "NO Preamble" strictness to ensure JSON parsing succeeds without wasting tokens on "Here is the JSON...".
2. **Parsing Logic**:
   - Map the Gemini response list directly to the new `IntentResponse.intents` field.
   - Ensure the primary `intent` field (legacy) acts as a summary or points to the first intent for backward compatibility.

### Phase 3: Downstream Handling (Bot Engine)
*(Note: This is outside intent-service scope but critical for E2E)*
- The bot engine processing `intent:results` must iterate through `intents`.
- **Strategy**: 
  1. `add_item` (oranges) -> Update Context
  2. `add_item` (apples) -> Update Context
  3. `set_delivery` -> Update Context
  4. `set_payment` -> Trigger Payment Flow
- If the bot engine is single-threaded per event, it may need to recursively process the list.

## 5. Proposed Gemini Prompt
```text
You are a slot extraction parser.
Input: User text.
Output: JSON object with key "intents".
Schema: {"id": string (snake_case), "slots": object}.
Constraints: Max 150 tokens. Compact JSON. No markdown.
```

## 6. Verification Steps
1. **Unit Test**: Feed the example complex string. Assert `response.intents` has length 4. Assert JSON output is valid.
2. **Token Check**: Verify output token usage is logged in `diagnostics` and stays under 150.
