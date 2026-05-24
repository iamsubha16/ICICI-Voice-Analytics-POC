// ============================================================
// DataSutram Echo — Dashboard JavaScript
// ============================================================

// ============================================================
// 1. INITIALIZATION
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
	// Auto-populate local call date/time
	const dtInput = document.getElementById("call_datetime");
	if (dtInput) {
		const now = new Date();
		now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
		dtInput.value = now.toISOString().slice(0, 16);
	}

	// Generate a fresh Call ID
	generateNewCallId();

	// Auth guard — silently verify session is still valid on page load.
	// If the user pressed Back after logout, this will catch the 401 and redirect.
	checkAuthSession();

	// Load previous calls history
	loadCallHistory();
});

function generateNewCallId() {
	const callIdInput = document.getElementById("call_id");
	if (callIdInput) {
		const uid = "CALL_" + Math.random().toString(36).substring(2, 8).toUpperCase() + "_" + Math.floor(1000 + Math.random() * 9000);
		callIdInput.value = uid;
	}
}

// ============================================================
// 2. AUTH GUARD — Back-button protection
// ============================================================
function checkAuthSession() {
	fetch("/api/auth-check", { method: "GET", credentials: "same-origin" })
		.then((res) => {
			if (res.status === 401) {
				// Session expired or cookie cleared (e.g. after logout + Back button)
				window.location.replace("/login");
			}
		})
		.catch(() => {
			// Network error — don't redirect, just log
			console.warn("Auth check failed (network)");
		});
}

// ============================================================
// 3. PREVIOUS CALLS HISTORY
// ============================================================
function loadCallHistory() {
	fetch("/api/calls/history", { credentials: "same-origin" })
		.then((res) => {
			if (res.status === 401) {
				window.location.replace("/login");
				return null;
			}
			return res.json();
		})
		.then((data) => {
			if (!data) return;
			renderCallHistory(data);
		})
		.catch((err) => {
			console.warn("Could not load call history:", err);
			renderCallHistory([]);
		});
}

function renderCallHistory(calls) {
	const container = document.getElementById("call-history-container");
	if (!container) return;

	container.innerHTML = "";

	if (!calls || calls.length === 0) {
		// Empty state
		container.innerHTML = `
            <div class="empty-calls-state animate-fade-in">
                <div class="empty-calls-icon">
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/>
                    </svg>
                </div>
                <p class="empty-title">No previous call records</p>
                <p class="empty-subtitle">
                    Upload a call recording using the form on the left to run your first compliance audit.
                    Completed analyses will appear here.
                </p>
            </div>
        `;
		return;
	}

	calls.forEach((call, idx) => {
		const card = document.createElement("div");
		card.className = "call-history-card animate-fade-in";
		card.style.animationDelay = `${idx * 0.05}s`;
		card.setAttribute("data-call-id", call.call_id);
		card.onclick = () => loadHistoryReport(call.call_id);

		// Format date
		let dateStr = "—";
		if (call.processed_at) {
			try {
				const d = new Date(call.processed_at);
				dateStr =
					d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) +
					", " +
					d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
			} catch (_) {}
		}

		// Disposition badge color
		const dispColor = getDispositionBadgeClass(call.disposition);
		const initials = (call.customer_id || "??")
			.replace(/[^a-zA-Z0-9]/g, "")
			.slice(0, 2)
			.toUpperCase();

		card.innerHTML = `
            <div class="call-hist-left">
                <div class="call-hist-avatar">${initials}</div>
                <div class="call-hist-info">
                    <div class="call-hist-id">${call.customer_id || call.call_id}</div>
                    <div class="call-hist-meta">${call.call_id} · ${call.loan_account || call.lender_name || "—"}</div>
                </div>
            </div>
            <div class="call-hist-right">
                <div class="call-hist-time">${dateStr}</div>
                <span class="badge ${dispColor}">${call.disposition || "—"}</span>
            </div>
        `;
		container.appendChild(card);
	});
}

function getDispositionBadgeClass(disposition) {
	if (!disposition) return "badge-muted";
	const d = disposition.toUpperCase();
	if (d === "PAID") return "badge-teal";
	if (d === "PROMISE_TO_PAY") return "badge-teal";
	if (d === "REFUSED") return "badge-danger";
	if (d === "DISPUTED") return "badge-warning";
	if (d === "NOT_REACHABLE") return "badge-muted";
	return "badge-muted";
}

function loadHistoryReport(callId) {
	// Mark card as active
	document.querySelectorAll(".call-history-card").forEach((c) => c.classList.remove("active-call"));
	const card = document.querySelector(`[data-call-id="${callId}"]`);
	if (card) card.classList.add("active-call");

	// Show the report view from JOBS_STORE via the status endpoint
	fetch(`/api/status/${callId}`, { credentials: "same-origin" })
		.then((res) => {
			if (!res.ok) throw new Error("Report not found");
			return res.json();
		})
		.then((data) => {
			if (data.report) {
				// Switch to report view
				showReportView();
				renderAuditReport(data.report);
			}
		})
		.catch((err) => {
			console.error("Could not load history report:", err);
		});
}

// ============================================================
// 4. VIEW NAVIGATION
// ============================================================
function showDashboardView() {
	document.getElementById("view-idle").classList.remove("hidden");
	document.getElementById("view-processing").classList.add("hidden");
	document.getElementById("view-report").classList.add("hidden");

	// Hide breadcrumb
	document.getElementById("header-breadcrumb").style.display = "none";
	document.getElementById("nav-dashboard-btn").classList.add("active");

	// Clear active card selection
	document.querySelectorAll(".call-history-card").forEach((c) => c.classList.remove("active-call"));
}

function showReportView() {
	document.getElementById("view-idle").classList.add("hidden");
	document.getElementById("view-processing").classList.add("hidden");
	document.getElementById("view-report").classList.remove("hidden");

	// Show breadcrumb
	document.getElementById("header-breadcrumb").style.display = "flex";
}

function refreshCurrentReport() {
	// Re-fetch and re-render the current call report (if any)
	const activeCard = document.querySelector(".call-history-card.active-call");
	if (activeCard) {
		const callId = activeCard.getAttribute("data-call-id");
		if (callId) loadHistoryReport(callId);
	}
}

function copyReportLink() {
	navigator.clipboard.writeText(window.location.href).then(() => {
		const btn = document.querySelector(".btn-copy-link");
		const origText = btn.innerHTML;
		btn.innerHTML = `<svg fill="none" viewBox="0 0 24 24" stroke="currentColor" style="height:0.8rem;width:0.8rem"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg> Copied!`;
		setTimeout(() => {
			btn.innerHTML = origText;
		}, 1800);
	});
}

// ============================================================
// 5. DRAG AND DROP FILE HANDLERS
// ============================================================
function clickFileInput() {
	document.getElementById("audio_file").click();
}

function handleDragOver(e) {
	e.preventDefault();
	document.getElementById("dropzone").classList.add("dragover");
}

function handleDragLeave() {
	document.getElementById("dropzone").classList.remove("dragover");
}

function handleDrop(e) {
	e.preventDefault();
	const dropzone = document.getElementById("dropzone");
	dropzone.classList.remove("dragover");
	if (e.dataTransfer.files.length > 0) {
		setFileInInput(e.dataTransfer.files[0]);
	}
}

function handleFileSelect(e) {
	if (e.target.files.length > 0) {
		setFileInInput(e.target.files[0]);
	}
}

function setFileInInput(file) {
	if (file.size > 15 * 1024 * 1024) {
		alert("File size exceeds 15 MB. Please upload a compressed telephony audio.");
		return;
	}

	const fileInput = document.getElementById("audio_file");
	const dt = new DataTransfer();
	dt.items.add(file);
	fileInput.files = dt.files;

	// Clear sample settings
	document.getElementById("sample_file").value = "";

	// Update dropzone UI
	const dropzone = document.getElementById("dropzone");
	dropzone.classList.add("active-loaded");
	dropzone.classList.remove("dragover");

	document.getElementById("dropzone-label").innerHTML = `Selected: <strong>${file.name}</strong>`;
	document.getElementById("dropzone-sublabel").textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB — Ready to upload`;
}

// ============================================================
// 6. PIPELINE TRIGGER & STATUS POLLING
// ============================================================
let currentCallId = null;
let pollInterval = null;
let renderedLogsCount = 0;

function triggerAudit(event) {
	event.preventDefault();

	const form = document.getElementById("audit-form");
	const fileVal = document.getElementById("audio_file").files.length;

	if (!fileVal) {
		alert("Please upload a call recording audio file before running the audit.");
		return;
	}

	const formData = new FormData(form);

	// Switch to processing view
	document.getElementById("view-idle").classList.add("hidden");
	document.getElementById("view-report").classList.add("hidden");
	document.getElementById("header-breadcrumb").style.display = "none";

	const procView = document.getElementById("view-processing");
	procView.classList.remove("hidden");

	resetProcessingSteps();
	document.getElementById("terminal-console-logs").innerHTML = "";
	renderedLogsCount = 0;

	// Submit via AJAX
	fetch("/api/analyze", {
		method: "POST",
		body: formData,
		credentials: "same-origin",
	})
		.then((res) => {
			if (res.status === 401) {
				window.location.replace("/login");
				return null;
			}
			if (!res.ok) throw new Error("Server rejected analysis request.");
			return res.json();
		})
		.then((data) => {
			if (!data) return;
			currentCallId = data.call_id;
			pollInterval = setInterval(pollPipelineStatus, 600);
		})
		.catch((err) => {
			console.error(err);
			alert("Failed to initialize compliance engine: " + err.message);
			showDashboardView();
		});
}

function resetProcessingSteps() {
	document.getElementById("current-step-label").textContent = "Audio Validation & Preprocessing...";
	document.getElementById("progress-percentage-label").textContent = "0%";
	document.querySelectorAll(".step-node").forEach((n) => (n.className = "step-node"));
	document.querySelectorAll(".step-connector").forEach((c) => (c.className = "step-connector"));
	document.getElementById("step-node-1").classList.add("active");
}

function pollPipelineStatus() {
	if (!currentCallId) return;

	fetch(`/api/status/${currentCallId}`, { credentials: "same-origin" })
		.then((res) => {
			if (res.status === 401) {
				window.location.replace("/login");
				return null;
			}
			if (!res.ok) throw new Error("Status endpoint unavailable.");
			return res.json();
		})
		.then((data) => {
			if (!data) return;

			const progress = data.status;
			document.getElementById("progress-percentage-label").textContent = `${progress}%`;
			document.getElementById("current-step-label").textContent = data.step;

			// Append new terminal logs
			const consoleLogs = document.getElementById("terminal-console-logs");
			const logs = data.logs || [];
			for (let i = renderedLogsCount; i < logs.length; i++) {
				const line = document.createElement("div");
				line.className = "console-line animate-fade-in";
				if (logs[i].includes("[ERROR]")) line.style.color = "#ef4444";
				line.textContent = logs[i];
				consoleLogs.appendChild(line);
			}
			renderedLogsCount = logs.length;
			consoleLogs.scrollTop = consoleLogs.scrollHeight;

			updateStepperVisualization(progress);

			if (progress === 100) {
				clearInterval(pollInterval);
				pollInterval = null;

				if (data.error) {
					alert("Pipeline failed: " + data.error);
					showDashboardView();
					return;
				}

				setTimeout(() => {
					// Show report and refresh history
					showReportView();
					renderAuditReport(data.report);
					loadCallHistory(); // Refresh left panel history
				}, 1000);
			}
		})
		.catch((err) => {
			console.error("Polling error:", err);
			clearInterval(pollInterval);
			pollInterval = null;
		});
}

function updateStepperVisualization(progress) {
	const n1 = document.getElementById("step-node-1");
	const n2 = document.getElementById("step-node-2");
	const n3 = document.getElementById("step-node-3");
	const n4 = document.getElementById("step-node-4");
	const c1 = document.getElementById("step-connector-1");
	const c2 = document.getElementById("step-connector-2");
	const c3 = document.getElementById("step-connector-3");

	if (progress >= 10 && progress < 45) {
		n1.className = "step-node active";
	} else if (progress >= 45 && progress < 80) {
		n1.className = "step-node completed";
		c1.className = "step-connector completed";
		n2.className = "step-node active";
	} else if (progress >= 80 && progress < 100) {
		n1.className = "step-node completed";
		c1.className = "step-connector completed";
		n2.className = "step-node completed";
		c2.className = "step-connector completed";
		n3.className = "step-node active";
	} else if (progress === 100) {
		n1.className = "step-node completed";
		c1.className = "step-connector completed";
		n2.className = "step-node completed";
		c2.className = "step-connector completed";
		n3.className = "step-node completed";
		c3.className = "step-connector completed";
		n4.className = "step-node completed";
	}
}

// ============================================================
// 7. REPORT RENDERING
// ============================================================
function renderAuditReport(report) {
	if (!report) return;

	// ---- Header Banner ----
	document.getElementById("val-customer-id-display").textContent = report.customer_id || "—";

	// Badges (status + disposition)
	const badgesEl = document.getElementById("report-call-badges");
	badgesEl.innerHTML = "";
	// Completion status
	const statusBadge = document.createElement("span");
	statusBadge.className = "badge badge-teal";
	statusBadge.textContent = "completed";
	badgesEl.appendChild(statusBadge);
	// Lender and account context
	const lenderBadge = document.createElement("span");
	lenderBadge.className = "badge badge-muted";
	lenderBadge.textContent = report.lender_name || "—";
	badgesEl.appendChild(lenderBadge);

	const accountBadge = document.createElement("span");
	accountBadge.className = "badge badge-muted";
	accountBadge.textContent = report.loan_account || "—";
	badgesEl.appendChild(accountBadge);

	// Meta fields (agent = phone/call_id, call_id = initiated by, lender/account = reference)
	document.getElementById("val-agent-id").textContent = report.agent_id || "—";
	document.getElementById("val-call-id").textContent = report.call_id || "—";
	document.getElementById("val-lender-name").textContent = report.lender_name || "—";
	document.getElementById("val-loan-account").textContent = report.loan_account || "—";

	// Overdue amount (shown in disposition pill area)
	const overdue = parseFloat(report.overdue_amount || 0);
	document.getElementById("report-disposition-pill").textContent =
		"DISPOSITION  " + (report.disposition_verification?.ai_disposition || "—");

	// ---- TAB 1: CALL INTELLIGENCE ----
	const intel = report.call_intelligence || {};
	document.getElementById("report-summary-text").textContent = intel.call_summary || "No summary available.";

	// Transcript preview (first 5 turns shown in summary tab)
	renderTranscriptTurns("transcript-preview-turns", report.transcript || [], 5);

	// Pain Points
	const painContainer = document.getElementById("report-pain-points");
	painContainer.innerHTML = "";
	(intel.key_pain_points || []).forEach((pt) => {
		const chip = document.createElement("span");
		chip.className = "chip-item";
		chip.textContent = pt;
		painContainer.appendChild(chip);
	});
	if (!painContainer.innerHTML)
		painContainer.innerHTML = "<span class='text-muted' style='font-size:0.78rem'>No pain points flagged.</span>";

	// Observations
	const obsContainer = document.getElementById("report-observations");
	obsContainer.innerHTML = "";
	(intel.notable_observations || []).forEach((obs) => {
		const li = document.createElement("li");
		li.textContent = obs;
		obsContainer.appendChild(li);
	});
	if (!obsContainer.innerHTML) obsContainer.innerHTML = "<li class='text-muted'>No special observations.</li>";

	// Missed Opportunities
	const missedContainer = document.getElementById("report-missed-opts");
	missedContainer.innerHTML = "";
	(intel.agent_missed_opportunities || []).forEach((opt) => {
		const li = document.createElement("li");
		li.textContent = opt;
		missedContainer.appendChild(li);
	});
	if (!missedContainer.innerHTML) missedContainer.innerHTML = "<li>No significant missed opportunities flagged.</li>";

	// Next Action + Feedback
	document.getElementById("report-next-action").textContent = intel.recommended_next_action || "Standard follow-up procedure.";
	document.getElementById("report-overall-feedback").textContent = intel.overall_feedback || "Compliance audit complete.";

	// ---- TAB 2: DISPOSITION AUDIT ----
	const dispo = report.disposition_verification || {};
	document.getElementById("audit-d0-value").textContent = dispo.bank_disposition || "—";
	document.getElementById("audit-d1-value").textContent = dispo.ai_disposition || "—";
	document.getElementById("audit-mismatch-explanation").textContent = dispo.mismatch_explanation || "Disposition verified.";

	const conf = Math.round((dispo.confidence_score || 0.9) * 100);
	document.getElementById("audit-confidence-value").textContent = conf + "%";
	document.getElementById("confidence-bar-fill").style.width = conf + "%";

	// Severity hero
	const banner = document.getElementById("severity-badge-banner");
	const badgeEl = document.getElementById("severity-hero-badge");
	badgeEl.className = "severity-hero-badge";

	if (dispo.disposition_match) {
		badgeEl.textContent = "DISPOSITION MATCHED";
		badgeEl.classList.add("severity-none");
		banner.style.borderColor = "var(--green-border)";
		banner.style.background = "var(--green-bg)";
	} else {
		const sev = dispo.mismatch_severity || "MINOR";
		badgeEl.textContent = sev + " MISMATCH";
		if (sev === "CRITICAL") {
			badgeEl.classList.add("severity-critical");
			banner.style.borderColor = "var(--danger-border)";
			banner.style.background = "var(--danger-bg)";
		} else if (sev === "SIGNIFICANT") {
			badgeEl.classList.add("severity-significant");
			banner.style.borderColor = "rgba(249,115,22,0.25)";
			banner.style.background = "rgba(249,115,22,0.06)";
		} else {
			badgeEl.classList.add("severity-minor");
			banner.style.borderColor = "var(--warning-border)";
			banner.style.background = "var(--warning-bg)";
		}
	}

	// ---- TAB 3: FULL TRANSCRIPT ----
	renderTranscriptTurns("transcript-chat-turns", report.transcript || []);

	// ---- TAB 4: SCRIPT TIMELINE ----
	const quality = report.agent_quality || {};
	const scores = quality.scores || {};

	document.getElementById("gauge-composite").textContent = scores.composite_score || "—";

	const flowVal = Math.round((scores.flow_correctness || 0) * 10);
	document.getElementById("gauge-flow").textContent = (scores.flow_correctness || 0) + "/1";
	document.getElementById("slider-flow-fill").style.width = flowVal + "%";

	const handVal = Math.round((scores.response_handling || 0) * 10);
	document.getElementById("gauge-handling").textContent = (scores.response_handling || 0) + "/1";
	document.getElementById("slider-handling-fill").style.width = handVal + "%";

	const qualVal = Math.round((scores.call_quality || 0) * 10);
	document.getElementById("gauge-quality").textContent = (scores.call_quality || 0) + "/1";
	document.getElementById("slider-quality-fill").style.width = qualVal + "%";

	// Stage nodes
	const stagesContainer = document.getElementById("compliance-stages-list");
	stagesContainer.innerHTML = "";
	(quality.stage_assessment || []).forEach((stage, idx) => {
		const nodeWrapper = document.createElement("div");
		nodeWrapper.className = "stage-timeline-node-wrapper";
		const statusClass = "status-" + (stage.status?.toLowerCase().replace("_", "-") || "skipped");
		nodeWrapper.innerHTML = `
            <div class="compliance-stage-node" onclick="toggleStageDetails(${idx})">
                <div class="node-stage-info">
                    <span class="node-letter-ring">${stage.stage_id}</span>
                    <span class="node-title-lbl">${stage.stage_name}</span>
                </div>
                <span class="stage-status-badge ${statusClass}">${stage.status?.replace("_", " ")}</span>
            </div>
            <div class="stage-expand-detail-box hidden" id="stage-detail-${idx}">
                <p class="detail-observation-txt"><strong>Observation:</strong> ${stage.observation || "No details."}</p>
                ${stage.deviation_note ? `<p class="detail-deviation-txt"><strong>Deviation:</strong> ${stage.deviation_note}</p>` : ""}
            </div>
        `;
		stagesContainer.appendChild(nodeWrapper);
	});

	// ---- TAB 5: COACHING ----
	const coaching = quality.coaching_feedback || {};

	const strengthsContainer = document.getElementById("coaching-strengths");
	strengthsContainer.innerHTML = "";
	(coaching.strengths || []).forEach((str) => {
		const li = document.createElement("li");
		li.textContent = str;
		strengthsContainer.appendChild(li);
	});
	if (!strengthsContainer.innerHTML) strengthsContainer.innerHTML = "<li>No strengths recorded.</li>";

	const improveContainer = document.getElementById("coaching-improvements");
	improveContainer.innerHTML = "";
	(coaching.improvement_areas || []).forEach((imp) => {
		const li = document.createElement("li");
		li.textContent = imp;
		improveContainer.appendChild(li);
	});
	if (!improveContainer.innerHTML) improveContainer.innerHTML = "<li class='text-green'>Perfect compliance! No improvements needed.</li>";

	document.getElementById("coaching-alternative").textContent = coaching.suggested_alternative || "Coaching dialogues up to date.";

	// Always start on Call Intelligence tab
	switchReportTab("tab-call-intel");
}

// ============================================================
// 8. TRANSCRIPT RENDERING (shared helper)
// ============================================================
function renderTranscriptTurns(containerId, transcript, limit) {
	const container = document.getElementById(containerId);
	if (!container) return;
	container.innerHTML = "";

	const turns = limit ? transcript.slice(0, limit) : transcript;

	turns.forEach((turn) => {
		const bubble = document.createElement("div");
		const speaker = turn.speaker || "UNKNOWN";
		const speakerId = turn.speaker_id != null ? String(turn.speaker_id) : null;
		const normalizedSpeaker = speaker.toLowerCase();
		const role = normalizedSpeaker === "agent" || speakerId === "0" ? "agent" : "customer";

		bubble.className = `chat-turn-bubble ${role}`;

		const start = turn.start || 0.0;
		const min = Math.floor(start / 60);
		const sec = Math.floor(start % 60)
			.toString()
			.padStart(2, "0");
		const timestamp = `${min}:${sec}`;

		bubble.innerHTML = `
            <div class="speaker-name-row">
                <span class="speaker-dot"></span>
                <span class="speaker-name-lbl">${speaker}</span>
                <span class="turn-timestamp-inline">${timestamp}</span>
            </div>
            <div class="bubble-text-box">
                <p class="turn-speech-text">${turn.text}</p>
            </div>
        `;
		container.appendChild(bubble);
	});

	if (!turns.length) {
		container.innerHTML = "<div class='text-muted text-center' style='padding:1rem;font-size:0.8rem'>Transcript unavailable.</div>";
	} else if (limit && transcript.length > limit) {
		const moreNote = document.createElement("div");
		moreNote.style.cssText = "text-align:center;font-size:0.72rem;color:var(--text-muted);padding:0.5rem";
		moreNote.textContent = `+${transcript.length - limit} more turns — view full transcript tab`;
		container.appendChild(moreNote);
	}
}

// ============================================================
// 9. UI HELPERS
// ============================================================
function toggleStageDetails(idx) {
	const box = document.getElementById(`stage-detail-${idx}`);
	if (box) box.classList.toggle("hidden");
}

function switchReportTab(tabId) {
	// Update tab button states
	const tabNames = {
		"tab-call-intel": "Call Intelligence",
		"tab-dispo-audit": "Disposition Audit",
		"tab-transcript": "Transcript",
		"tab-script-timeline": "Script Timeline",
		"tab-coaching": "Coaching Corner",
	};

	document.querySelectorAll(".nav-tab-btn").forEach((btn) => {
		btn.classList.remove("active");
		if (btn.textContent.trim() === tabNames[tabId]) {
			btn.classList.add("active");
		}
	});

	// Show/hide panels
	document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
	const target = document.getElementById(tabId);
	if (target) target.classList.remove("hidden");
}
