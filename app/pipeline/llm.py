import json
from openai import AzureOpenAI
from app.config import Config


def analyze_transcript(
    transcript: list,
    lender_name: str,
    loan_account: str,
    overdue_amount: float,
    d0_disposition: str,
    d0_notes: str,
) -> dict:
    """
    Analyzes a diarized transcript using Azure OpenAI based on calling context and script compliance.
    Strictly queries the live Azure OpenAI Service. If keys are missing, mock, or if any API/network
    errors are encountered, this function raises a loud exception to fail the pipeline and display accurate error logs.
    """
    # Verify API key configuration
    if not Config.AZURE_OPENAI_API_KEY or Config.AZURE_OPENAI_API_KEY == "mock_key_for_demo":
        raise ValueError(
            "Azure OpenAI Compliance Audit execution failed: "
            "AZURE_OPENAI_API_KEY is not configured or is set to a mock value in .env."
        )

    print("Connecting to Azure OpenAI ChatCompletions...")
    client = AzureOpenAI(
        api_key=Config.AZURE_OPENAI_API_KEY, api_version="2023-12-01-preview", azure_endpoint=Config.AZURE_OPENAI_ENDPOINT
    )

    # Format the transcript for the LLM
    formatted_turns = []
    for turn in transcript:
        formatted_turns.append(f"[{turn.get('speaker', 'UNKNOWN')}]: {turn.get('text', '')}")
    transcript_str = "\n".join(formatted_turns)

    json_schema_example = """
  {
      "disposition_verification": {
        "d0_logged_disposition": "PAID | PROMISE_TO_PAY | REFUSED | NOT_REACHABLE | DISPUTED",
        "d1_inferred_disposition": "PAID | PROMISE_TO_PAY | REFUSED | NOT_REACHABLE | DISPUTED | PARTIAL_COMMITMENT | UNCLEAR",
        "disposition_match": true,
        "mismatch_severity": "NONE | MINOR | SIGNIFICANT | CRITICAL",
        "mismatch_explanation": "Detailed validation explaining transcript statements versus the logged AI system disposition state",
        "confidence_score": 0.95
      },
      "refusal_analysis": {
        "payment_status": "AGREED | PARTIAL | DEFERRED | REFUSED | UNCLEAR",
        "primary_reason": "FINANCIAL_HARDSHIP | DISPUTES_AMOUNT | ALREADY_PAID | WILL_PAY_LATER | JOB_LOSS | MEDICAL_EMERGENCY | UNRESPONSIVE | OTHER",
        "reason_verbatim": "Direct quotation from transcript",
        "secondary_reasons": ["String array of compounding friction points"],
        "customer_sentiment": "COOPERATIVE | NEUTRAL | AGITATED | HOSTILE",
        "escalation_risk": "LOW | MEDIUM | HIGH"
      },
      "agent_quality": {
        "scores": {
          "flow_correctness": 0.0,
          "response_handling": 0.0,
          "call_quality": 0.0,
          "composite_score": 0.0
        },
        "stage_assessment": [
          {
            "stage_id": "A | B | C | D | E",
            "stage_name": "Greeting & Identity Verification | Overdue Amount Statement | Consequence Nudge | Delay Reason Extraction & Objection Handling | Payment Commitment & Closing",
            "status": "COMPLETED | PARTIALLY_COMPLETED | SKIPPED | IMPROVISED",
            "observation": "Document specific actions taken by the Voice AI during this interaction slice.",
            "deviation_note": "Detail missing elements if status isn't COMPLETED. Flag infractions such as violations of the Critical Number Rule, incorrect Hindi gender markers, full sentence echoing, or short-circuit script behaviors."
          }
        ],
        "coaching_feedback": {
          "strengths": ["List of engineering rules successfully executed by the LLM/TTS engine"],
          "improvement_areas": ["List of algorithmic, programmatic, prompt, or linguistic gaps observed"],
          "suggested_alternative": "Corrected script dialogue showing exactly how the automated voice agent should have responded to adhere to its core prompt constraints."
        }
      },
      "call_intelligence": {
        "call_summary": "Provide a 3-5 sentence neutral summary of the voice system transaction.",
        "key_pain_points": ["System or customer friction items identified"],
        "agent_missed_opportunities": ["Missed prompt protocols, failed language pivots, or bad SSML tag sequences"],
        "notable_observations": ["Unique conversational anomalies, user behavior observations, or structural TTS glitches"],
        "recommended_next_action": "Operational recommendations for the collections strategy team (e.g., issue human callback, trigger automated payment SMS link, flag for dispute review panel)",
        "overall_feedback": "2-3 sentences evaluating the systemic effectiveness of the automated conversational agent during the interaction."
      }
    }
  """

    system_prompt = f"""
# Voice AI Collections Quality Audit & Compliance Prompt

You are an expert Quality Audit & Compliance AI specializing in banking and NBFC conversational AI applications. Your task is to analyze a diarized transcript of an automated Voice AI recovery call. You will cross-examine the transcript against the specific architectural guidelines of the Voice assistant prompt, the lender context, and the AI's post-call metadata logs.

Output a highly detailed, structured, and legally compliant audit report in valid JSON.

### Voice AI System Context Provided:
- **Lender Name:** {lender_name}
- **Prescribed Overdue Amount:** {overdue_amount} INR
- **Loan Account Number:** {loan_account}
- **Voice AI Post-Call Logged Disposition (D0):** {d0_disposition}
- **Voice AI Technical Logs/Notes:** {d0_notes}

---

### Part 1: Operational Compliance Standards

#### 1. Script Progression Framework
The system must guide the customer sequentially through 5 distinct ordered conversational stages:
- **Stage A: Identity Verification (ID: A):** Greet from the organization, disclose recording warnings if needed, and strictly confirm the customer identity before revealing financial details.
- **Stage B: Overdue Amount Statement (ID: B):** Explicitly mention the account/loan string, indicate that the EMI has bounced, specify the overdue balance, and push for a immediate/same-day payment.
- **Stage C: Consequence Nudge (ID: C):** Apply targeted empathy or soft penalty friction (e.g., impact on credit health/CIBIL rating, additional late charge risks).
- **Stage D: Delay Reason Extraction & Objection Handling (ID: D):** Professionally process why payment hasn't cleared, maintain active listening without mirroring full customer entries, and pivot back to the target.
- **Stage E: Payment Commitment & Closing (ID: E):** Secure definite commitments (specific date/time/method) or handle standard polite termination loops (e.g., payment link confirmations, callbacks, or third-party exits).

#### 2. Critical Number & Technical Token Rules
- **The Critical Number Rule:** ALL technical variables, financial integers, rupee balances, dates, specific clock times, and isolated numerals MUST be synthesized in **English words only**. This remains true even if the primary dialect of the turn switches to Hindi or Hinglish. Rupee strings must never be evaluated digit-by-digit.
- **Loan Account Pronunciation:** Loan strings must be processed individually as isolated alphanumeric digits (e.g., "one two three") entirely in English.

#### 3. Bilingualism & Language Matching Rules
- **Default State:** The Voice AI must introduce itself and begin conversations.
- **Dynamic Matching:** The assistant must gracefully mirror language choices. If a customer explicitly transitions to Hindi or back to English, subsequent turns must match. However, isolated generic filler words (e.g., "okay," "yes," "EMI") do not qualify for a systemic language flip.
- **Code-switching Boundaries:** The engine must avoid blending alternative linguistic systems mid-sentence (avoid raw syntactic code-mixing within a single thought structure).
---

### Part 2: Audit Analytics & Analysis Tasks

1. **Disposition Verification:** Infer the real-world operational result (**D1**) solely from the conversation flow: `PAID`, `PROMISE_TO_PAY`, `REFUSED`, `NOT_REACHABLE`, `DISPUTED`, `PARTIAL_COMMITMENT`, `UNCLEAR`.
   - **Strict field assignment (no ambiguity allowed):**
     - `d0_logged_disposition` MUST be set to the **exact value** of the Voice AI Post-Call Logged Disposition (D0) provided above as system context — i.e. `{d0_disposition}`. Do not re-interpret, infer, or modify D0. Copy it verbatim.
     - `d1_inferred_disposition` MUST be set to the disposition you (the auditor) infer **strictly from the transcript content**, independent of D0.
   - Contrast inferred D1 with logged D0 to flag system discrepancies (`disposition_match`: true/false).
   - Evaluate `mismatch_severity`:
     - `NONE`: Perfect alignment.
     - `MINOR`: Micro-level variations (e.g., AI captures full `PROMISE_TO_PAY` but text reflects a `PARTIAL_COMMITMENT`).
     - `SIGNIFICANT`: Misinterpreted deflection patterns (e.g., customer used stall tactics like *"dekh lenge" / "dekhate hain"* which implies an `UNCLEAR` state, but the AI flagged it as a firm commitment).
     - `CRITICAL`: Direct operational failure (e.g., customer explicitly issued an account amount challenge / requested a settlement which implies `DISPUTED`, but the AI processed a default closing sequence).
   - Compute an algorithmic `confidence_score` (0.0 to 1.0) tracking ambient acoustic markers or translation/code-switching ambiguities in the transcript text.

2. **Diarization & Edge Condition Verification:** If the text document arrives as unstructured, flat lines without speaker indicators, parse internal honorific patterns and programmatic hooks to assign `[AGENT]` and `[CUSTOMER]` nodes implicitly before conducting audit pipelines.

3. **Script Compliance Auditing (Flow & Short-Circuit Exits):**
   - Rate each conversation chapter status: `COMPLETED`, `PARTIALLY_COMPLETED`, `SKIPPED`, `IMPROVISED`.
   - **Short-Circuit Detection:** Audit for system processing shortcuts. Flag scenarios where the AI abruptly exited after a customer objection in Stage B, skipping directly to Stage E closing steps without assessing the core obstruction.

4. **Escalation & Account Vulnerability Risk:**
   - Rank vulnerabilities as `LOW`, `MEDIUM`, or `HIGH`.
   - Escalate to `HIGH` if the customer exhibits extreme agitation, voices legal/regulatory pushback, triggers human-handoff overrides, or details a severe dispute.

*IMPORTANT*: You must check if the call was disconnected mid-conversation. If the transcript ends abruptly without a proper closing, flag it as required.

---

### Output JSON Format:
Respond ONLY with a valid, parsable JSON object matching this schema. Do not include markdown formatting except wrapping the raw payload block.
{json_schema_example}
"""

    user_prompt = f"Please audit the following transcript of an recovery call:\n\n{transcript_str}"

    response = client.chat.completions.create(
        model=Config.AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content
    print("Azure OpenAI audit completed successfully.")
    return json.loads(response_text)
