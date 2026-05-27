import os
import requests
from app.config import Config
import time
import sys
import re


def safe_print(text: str):
    """Prints text safely to stdout, handling Windows console encoding errors with escapes."""
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            encoding = sys.stdout.encoding or "utf-8"
            print(text.encode(encoding, errors="backslashreplace").decode(encoding))
        except Exception:
            print(text.encode("ascii", errors="backslashreplace").decode("ascii"))


_AGENT_INTRO_PATTERNS = [
    r"\bmy name is\b",
    r"\bi am calling from\b",
    r"\bI'm calling from\b",
    r"\bthis is\b",
    r"\bspeaking from\b",
    r"\bmera naam\b",
    r"\bmain .*bol rahi hoon\b",
    r"\bmain .*bol raha hoon\b",
    r"\bICICI\b",
]


def _looks_like_agent_intro(text: str) -> bool:
    normalized_text = (text or "").lower()
    return any(re.search(pattern.lower(), normalized_text) for pattern in _AGENT_INTRO_PATTERNS)


def _infer_agent_speaker_id(raw_segments: list) -> str | None:
    for seg in raw_segments:
        if _looks_like_agent_intro(seg.get("transcript", "")):
            return str(seg.get("speaker_id", "unknown"))

    if raw_segments:
        return str(raw_segments[0].get("speaker_id", "unknown"))

    return None


def _normalize_diarized_segments(raw_segments: list) -> list:
    """Normalize Sarvam diarization entries while labeling the self-introducing speaker as AGENT."""
    normalized_segments = []
    agent_speaker_id = _infer_agent_speaker_id(raw_segments)

    for seg in raw_segments:
        speaker_id = str(seg.get("speaker_id", "unknown"))
        speaker_label = "AGENT" if speaker_id == agent_speaker_id else "CUSTOMER"
        normalized_segments.append(
            {
                "speaker": speaker_label,
                "speaker_id": speaker_id,
                "start": float(seg.get("start_time_seconds", 0.0)),
                "end": float(seg.get("end_time_seconds", 0.0)),
                "text": seg.get("transcript", ""),
            }
        )

    return normalized_segments


def transcribe_audio(audio_path: str, filename: str, d0_notes: str = "", d0_disposition: str = "") -> list:
    """
    Transcribes an audio file using Sarvam AI Speech-to-Text.
    Strictly uses the live Sarvam AI ASR Batch API. If the API key is missing, mock,
    or if any network or API error occurs, this function raises a loud exception to fail the pipeline.
    """
    # Verify API key configuration
    if not Config.SARVAM_API_KEY or Config.SARVAM_API_KEY == "mock_key_for_demo":
        raise ValueError(
            "Sarvam AI Speech-to-Text API execution failed: SARVAM_API_KEY is not configured or is set to a mock value in .env."
        )

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found at path: {audio_path}")

    print("=================================================================")
    print(f"STARTING SARVAM BATCH STT PIPELINE FOR: {filename}")
    print(f"Audio Path: {audio_path}")
    print("=================================================================")

    # Step 1: Initiate Job
    print("[Batch STT Step 1/6] Initiating asynchronous job...")
    init_url = "https://api.sarvam.ai/speech-to-text/job/v1"
    headers = {"api-subscription-key": Config.SARVAM_API_KEY, "Content-Type": "application/json"}
    init_payload = {
        "job_parameters": {
            "model": "saaras:v3",
            "mode": "codemix",
            "language_code": "hi-IN",
            "with_diarization": True,
            "num_speakers": 2,
        }
    }
    init_resp = requests.post(init_url, headers=headers, json=init_payload, timeout=30)
    print(f"Initiate Job Response HTTP Code: {init_resp.status_code}")
    if init_resp.status_code not in (200, 202):
        raise RuntimeError(f"Sarvam Job initiation failed with status {init_resp.status_code}: {init_resp.text}")

    init_data = init_resp.json()
    job_id = init_data.get("job_id")
    if not job_id:
        raise RuntimeError(f"Sarvam Job initiation did not return a valid job_id: {init_data}")
    print(f"Job initiated successfully. Job ID: {job_id}")

    # Step 2: Request Presigned Upload URLs
    print(f"[Batch STT Step 2/6] Requesting presigned upload URL for: {filename}")
    upload_urls_url = "https://api.sarvam.ai/speech-to-text/job/v1/upload-files"
    upload_payload = {"job_id": job_id, "files": [filename]}
    upload_urls_resp = requests.post(upload_urls_url, headers=headers, json=upload_payload, timeout=30)
    print(f"Upload URL Request Response HTTP Code: {upload_urls_resp.status_code}")
    if upload_urls_resp.status_code != 200:
        raise RuntimeError(f"Failed to request upload URLs with status {upload_urls_resp.status_code}: {upload_urls_resp.text}")

    upload_data = upload_urls_resp.json()
    upload_urls = upload_data.get("upload_urls", {})
    file_info = upload_urls.get(filename)
    if not file_info:
        raise RuntimeError(f"No upload URL object returned for filename '{filename}' in response: {upload_data}")

    presigned_url = file_info.get("file_url") if isinstance(file_info, dict) else file_info
    if not presigned_url:
        raise RuntimeError(f"Could not extract 'file_url' for filename '{filename}' from response.")
    print(f"Extracted Presigned SAS URL successfully.")

    # Step 3: Upload Audio Binary
    print(f"[Batch STT Step 3/6] Uploading audio binary to storage...")
    mimetype = "audio/mpeg" if audio_path.lower().endswith(".mp3") else "audio/wav"
    with open(audio_path, "rb") as audio_file:
        put_headers = {
            "Content-Type": mimetype,
            "x-ms-blob-type": "BlockBlob",  # Mandatory header for Azure SAS URL uploads!
        }
        put_resp = requests.put(presigned_url, data=audio_file, headers=put_headers, timeout=60)
    print(f"Binary Upload HTTP Code: {put_resp.status_code}")
    if put_resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to upload audio binary with status {put_resp.status_code}: {put_resp.text}")
    print("Audio binary successfully uploaded.")

    # Step 4: Start Processing Job
    print(f"[Batch STT Step 4/6] Starting transcription job processing on Sarvam...")
    start_url = f"https://api.sarvam.ai/speech-to-text/job/v1/{job_id}/start"
    start_resp = requests.post(start_url, headers={"api-subscription-key": Config.SARVAM_API_KEY}, timeout=30)
    print(f"Start Job Response HTTP Code: {start_resp.status_code}")
    if start_resp.status_code not in (200, 202):
        raise RuntimeError(f"Failed to start job processing with status {start_resp.status_code}: {start_resp.text}")
    print("Job processing successfully started.")

    # Step 5: Poll Job Status
    print(f"[Batch STT Step 5/6] Polling job status...")
    status_url = f"https://api.sarvam.ai/speech-to-text/job/v1/{job_id}/status"
    status_headers = {"api-subscription-key": Config.SARVAM_API_KEY}

    output_files = []
    max_polls = 100
    poll_interval = 3.0
    completed = False

    for i in range(max_polls):
        time.sleep(poll_interval)
        status_resp = requests.get(status_url, headers=status_headers, timeout=30)
        print(f"Poll #{i + 1} HTTP Code: {status_resp.status_code}")
        if status_resp.status_code != 200:
            print(f"Warning: Status poll returned {status_resp.status_code}: {status_resp.text}")
            continue

        status_data = status_resp.json()
        job_state = status_data.get("job_state")
        print(f"Current Job State: {job_state}")

        if job_state == "Completed":
            completed = True
            print("Sarvam Batch job processing completed successfully!")

            # Extract outputs filenames
            for detail in status_data.get("job_details", []):
                for out in detail.get("outputs", []):
                    if out.get("file_name"):
                        output_files.append(out.get("file_name"))
            break
        elif job_state == "Failed":
            raise RuntimeError(f"Sarvam Batch job failed processing: {status_data}")

    if not completed:
        raise TimeoutError(f"Sarvam Batch job polling timed out after {max_polls * poll_interval} seconds.")

    if not output_files:
        print("Warning: No output files listed in job details. Falling back to default '0.json'.")
        output_files = ["0.json"]

    # Step 6: Download & Parse Results
    print(f"[Batch STT Step 6/6] Fetching download read URLs for: {output_files}")
    download_url = "https://api.sarvam.ai/speech-to-text/job/v1/download-files"
    download_payload = {"job_id": job_id, "files": output_files}
    download_resp = requests.post(download_url, headers=headers, json=download_payload, timeout=30)
    print(f"Download URL Request Response HTTP Code: {download_resp.status_code}")
    if download_resp.status_code != 200:
        raise RuntimeError(f"Failed to request download URLs with status {download_resp.status_code}: {download_resp.text}")

    download_data = download_resp.json()
    download_urls = download_data.get("download_urls", {})

    # Fetch the first output file (typically 0.json)
    target_file = output_files[0]
    target_info = download_urls.get(target_file)
    if not target_info:
        raise RuntimeError(f"No download URL returned for target output file '{target_file}' in: {download_urls}")

    read_url = target_info.get("file_url") if isinstance(target_info, dict) else target_info
    if not read_url:
        raise RuntimeError(f"Could not extract 'file_url' for output file '{target_file}' from response.")

    print(f"Fetching transcription JSON content from presigned read URL...")
    result_resp = requests.get(read_url, timeout=30)
    print(f"Fetch Transcript Content Response HTTP Code: {result_resp.status_code}")
    if result_resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch transcription result with status {result_resp.status_code}: {result_resp.text}")

    result = result_resp.json()
    print("Sarvam STT Batch results successfully downloaded!")

    # Print full flat transcript
    full_flat_text = result.get("transcript", "")
    print("\n------------------ FULL TRANSCRIPT FROM SARVAM STT ------------------")
    safe_print(full_flat_text)
    print("--------------------------------------------------------------------\n")

    # Parse speaker diarized entries
    diarized = result.get("diarized_transcript")
    raw_segments = []
    if isinstance(diarized, dict) and "entries" in diarized:
        raw_segments = diarized["entries"]
    elif isinstance(diarized, list):
        raw_segments = diarized

    if raw_segments:
        print(f"Extracted {len(raw_segments)} raw diarized segments from Sarvam output.")
        mapped_segments = _normalize_diarized_segments(raw_segments)
        print(f"Speaker normalization complete. Total mapped segments: {len(mapped_segments)}")
        print("\n---------------- DIARIZED SEGMENTS FROM SARVAM STT ----------------")
        for seg in mapped_segments:
            safe_print(f"[{seg['speaker']} ({seg['start']:.2f}s - {seg['end']:.2f}s)]: {seg['text']}")
        print("--------------------------------------------------------------------\n")

        return mapped_segments

    elif full_flat_text:
        print("Warning: Sarvam returned flat transcript but no diarized segments. Downstream LLM Diarization Guard will run.")
        return [{"speaker": "UNKNOWN", "start": 0.0, "end": 0.0, "text": full_flat_text}]

    else:
        raise RuntimeError("Sarvam STT returned empty transcript and empty diarized segments.")
