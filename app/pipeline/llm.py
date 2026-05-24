import os
import json
from openai import AzureOpenAI
from app.config import Config

def analyze_transcript(
    transcript: list,
    overdue_amount: float,
    loan_type: str,
    d0_disposition: str,
    d0_notes: str,
    filename: str
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
        api_key=Config.AZURE_OPENAI_API_KEY,
        api_version="2023-12-01-preview",
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT
    )
    
    # Format the transcript for the LLM
    formatted_turns = []
    for turn in transcript:
        formatted_turns.append(f"[{turn.get('speaker', 'UNKNOWN')}]: {turn.get('text', '')}")
    transcript_str = "\n".join(formatted_turns)
    
    system_prompt = f"""You are an expert Quality Audit & Compliance AI specializing in banking and NBFC debt collections.
Your task is to analyze a diarized transcript of an EMI recovery call, compare it against the bank's prescribed calling script, the tele-caller's self-reported disposition (D0), and the loan context. Output a highly detailed, structured, and compliant audit report in valid JSON.

### Calling Context Provided:
- **Prescribed Overdue Amount:** {overdue_amount} INR
- **Loan Type:** {loan_type}
- **Tele-caller Reported Disposition (D0):** {d0_disposition}
- **Tele-caller Notes:** {d0_notes}

### Prescribed Calling Script
The bank requires agents to follow these 5 stages in order:
- **Stage A: Greeting & Identity Verification (ID: A):** Politely greet, verify customer name and account holder identity.
- **Stage B: Overdue Amount Statement (ID: B):** Clearly state loan/EMI account, specify overdue amount in INR, and demand immediate payment.
- **Stage C: Consequence Nudge (ID: C):** Explain credit score/CIBIL impact, late payment penalties, and potential legal escalations if unpaid.
- **Stage D: Delay Reason Extraction & Objection Handling (ID: D):** Ask why customer is delaying, handle objections professionally, and offer solutions.
- **Stage E: Payment Commitment & Closing (ID: E):** Secure concrete payment commitment (exact amount, exact date/time, channel), send payment SMS link, and close call.

### Linguistic Context (Hindi, English, Hinglish):
Calls are frequently in Hinglish (code-switched Hindi-English) or conversational Hindi. You must apply the same audit rigour to translated meaning as you would to English text. Pay attention to colloquialisms and collection phrases:
- `"dekh lenge" / "dekhate hain"`: Signals deflecting or stalling behavior. True outcome (D1) is "UNCLEAR" or "REFUSED", NOT "PROMISE_TO_PAY".
- `"kal kar deta hoon"`: If said without a specific confirmed amount or clear intent, or if customer sounds defensive/unreliable, interpret as "PARTIAL_COMMITMENT" or "UNCLEAR".
- `"settlement karo"`: Signals an active dispute regarding the amount. True outcome (D1) is "DISPUTED".

### Analysis Tasks:
1. **Disposition Verification:** Infer true outcome (D1) from transcript: PAID, PROMISE_TO_PAY, REFUSED, NOT_REACHABLE, DISPUTED, PARTIAL_COMMITMENT, UNCLEAR.
   - Compare D1 with D0. Set `disposition_match` to true/false.
   - Classify `mismatch_severity`: 
     - `NONE`: D0 and D1 match perfectly.
     - `MINOR`: Slight discrepancy, e.g. D1 is PARTIAL_COMMITMENT but agent logged PROMISE_TO_PAY.
     - `SIGNIFICANT`: Intentional inflation of success, e.g. D1 is UNCLEAR (customer said "dekh lenge") but agent logged PROMISE_TO_PAY.
     - `CRITICAL`: Direct violation, e.g. customer flatly refused (D1 is REFUSED) but agent logged PROMISE_TO_PAY.
   - Provide a clear, analytical `mismatch_explanation`.
   - Calculate `confidence_score` (0.0 to 1.0) based on signal clarity. Lower the score if there is code-switching ambiguity, audio cutouts (indicated in transcript), or mixed signals.

2. **Diarization Guard (Fallback):**
   - If the transcript below lacks speaker labels (flat text), you must analyze conversational turn patterns, honorifics, and vocabulary (e.g. agent asks about money, customer complains of lack of funds) to infer speaker identities. Assign [AGENT] and [CUSTOMER] turns implicitly before executing compliance audits.

3. **Script Compliance Auditing (Flow & Premature Exits):**
   - Score each stage (COMPLETED, PARTIALLY_COMPLETED, SKIPPED, IMPROVISED).
   - Auditing Flow: If the agent skips crucial steps, mark them SKIPPED.
   - **Premature Exit Auditing:** Specifically flag if the agent took a shortcut (e.g. customer refused or raised an objection in Stage B, and the agent jumped straight to closing and sending an SMS link in Stage E, completely skipping Stage D delay probing). Highlight this as a major deviation.

4. **Escalation Risk:**
   - Classify as `LOW`, `MEDIUM`, or `HIGH`.
   - Set to `HIGH` if there is a severe dispute over the overdue amount, threats of legal action against the bank, regulatory complaints, or extremely hostile/agitated customer sentiment.

### Few-Shot Mismatch Example:
- **D0 (Agent logged):** PROMISE_TO_PAY
- **Transcript excerpt:** 
  - *AGENT:* Sir, apka Personal Loan EMI Rs. 15,000 overdue hai. Kab tak payment karenge?
  - *CUSTOMER:* Haan bhaiya, dekh lenge. Kal parso dekhta hoon.
  - *AGENT:* Okay sir, main payment link SMS kar raha hoon, payment kar dena. Thank you.
- **Inferred D1:** UNCLEAR
- **Mismatch Severity:** SIGNIFICANT
- **Reasoning:** The customer deflected with "dekh lenge" (we'll see) and gave no specific date or amount. The agent logged PROMISE_TO_PAY anyway to meet targets. This is a premature exit and a significant mismatch.

### Output JSON Format:
Respond ONLY with a valid, parsable JSON object matching this schema:
{{
  "disposition_verification": {{
    "ai_disposition": "PAID | PROMISE_TO_PAY | REFUSED | NOT_REACHABLE | DISPUTED | PARTIAL_COMMITMENT | UNCLEAR",
    "bank_disposition": "PAID | PROMISE_TO_PAY | REFUSED | NOT_REACHABLE | DISPUTED",
    "disposition_match": boolean,
    "mismatch_severity": "NONE | MINOR | SIGNIFICANT | CRITICAL",
    "mismatch_explanation": "Detailed explanation comparing transcript statements to logged disposition code",
    "confidence_score": float
  }},
  "refusal_analysis": {{
    "payment_status": "AGREED | PARTIAL | DEFERRED | REFUSED | UNCLEAR",
    "primary_reason": "FINANCIAL_HARDSHIP | DISPUTES_AMOUNT | ALREADY_PAID | WILL_PAY_LATER | JOB_LOSS | MEDICAL_EMERGENCY | UNRESPONSIVE | OTHER",
    "reason_verbatim": "Direct quotation from transcript",
    "secondary_reasons": ["string"],
    "customer_sentiment": "COOPERATIVE | NEUTRAL | AGITATED | HOSTILE",
    "escalation_risk": "LOW | MEDIUM | HIGH"
  }},
  "agent_quality": {{
    "scores": {{
      "flow_correctness": float,
      "response_handling": float,
      "call_quality": float,
      "composite_score": float
    }},
    "stage_assessment": [
      {{
        "stage_id": "A | B | C | D | E",
        "stage_name": "Greeting & Identity Verification | Overdue Amount Statement | Consequence Nudge | Delay Reason Extraction & Objection Handling | Payment Commitment & Closing",
        "status": "COMPLETED | PARTIALLY_COMPLETED | SKIPPED | IMPROVISED",
        "observation": "Specific agent actions during this stage",
        "deviation_note": "If status is not COMPLETED, details of what script stage elements were missed or incorrect"
      }}
    ],
    "coaching_feedback": {{
      "strengths": ["string"],
      "improvement_areas": ["string"],
      "suggested_alternative": "Dialogue script of how the agent should have handled the customer's specific refusal/objection"
    }}
  }},
  "call_intelligence": {{
    "call_summary": "3-5 sentences neutral summary",
    "key_pain_points": ["string"],
    "agent_missed_opportunities": ["string"],
    "notable_observations": ["string"],
    "recommended_next_action": "Actionable collections next step",
    "overall_feedback": "2-3 sentences call efficacy feedback"
  }}
}}"""

    user_prompt = f"Please audit the following transcript of an recovery call:\n\n{transcript_str}"
    
    response = client.chat.completions.create(
        model=Config.AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    
    response_text = response.choices[0].message.content
    print("Azure OpenAI audit completed successfully.")
    return json.loads(response_text)
