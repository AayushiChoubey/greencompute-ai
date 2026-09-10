let telemetryData = [];
let pollInterval = null;
let timerInterval = null;
let telemetryPollInterval = null;
let startTime = null;

function workflowExecutionId(record) {
  let details = record.event_details || {};
  if (typeof details === 'string') {
    try {
      details = JSON.parse(details);
    } catch (_) {
      return '';
    }
  }
  return details.workflow_execution_id || '';
}

function workflowLogsUrl(executionId) {
  const query = `resource.type="workflows.googleapis.com/Workflow" AND "${executionId}"`;
  return `https://console.cloud.google.com/logs/query;query=${encodeURIComponent(query)}?project=greencompute-ai`;
}

function workflowStatusText(executionName, info) {
  let text = `Workflow Execution Dispatched:\n${executionName}\nStatus: ${info.state || 'ACTIVE'}`;
  if (info.error) {
    const error = typeof info.error === 'string' ? info.error : JSON.stringify(info.error);
    text += `\nError: ${error}`;
  }
  return text;
}

function startElapsedTimer() {
  clearInterval(timerInterval);
  startTime = Date.now();
  const timerEl = document.getElementById('elapsedTimerText');
  const loaderEl = document.getElementById('activeLoader');
  if (loaderEl) loaderEl.classList.remove('hidden');
  if (timerEl) timerEl.innerText = '⏱ Elapsed: 0s';

  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    if (timerEl) timerEl.innerText = `⏱ Elapsed: ${elapsed}s`;
  }, 1000);
}

function stopElapsedTimer() {
  clearInterval(timerInterval);
  const loaderEl = document.getElementById('activeLoader');
  if (loaderEl) loaderEl.classList.add('hidden');
}

async function runDispatch(dispatch) {
  const prompt = document.getElementById('promptInput').value;
  const badgeStatus = document.getElementById('badgeStatus');
  const optBtn = document.getElementById('optimizeBtn');
  const dispBtn = document.getElementById('dispatchBtn');
  const wfBox = document.getElementById('workflowStatusBox');
  
  clearInterval(pollInterval);
  stopElapsedTimer();

  optBtn.disabled = true;
  dispBtn.disabled = true;
  badgeStatus.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/30";
  badgeStatus.innerText = dispatch ? 'DISPATCHING TO CLOUD WORKFLOWS...' : 'RUNNING OPTIMIZER & GEMINI...';
  
  try {
    const res = await fetch(`/api/v1/workloads/from-prompt?dispatch=${dispatch}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, auto_optimize: true })
    });
    
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    
    const data = await res.json();
    const opt = data.optimization_result;
    
    if (opt && opt.selected_candidate) {
      const cand = opt.selected_candidate;
      const costVal = cand.estimated_compute_cost_usd ?? cand.estimated_cost_usd ?? 0.0043;
      const carbonVal = cand.carbon_score ?? cand.carbon_intensity ?? 170.0;
      
      let provModel = 'SPOT';
      if (cand.provisioning_model) {
        provModel = typeof cand.provisioning_model === 'object' 
          ? (cand.provisioning_model.value || 'SPOT') 
          : cand.provisioning_model;
      }

      document.getElementById('resRegion').innerText = cand.region || 'europe-west1';
      document.getElementById('resTier').innerText = `${cand.machine_type || 'n2-standard-4'} (${provModel})`;
      document.getElementById('resCarbon').innerText = `${Number(carbonVal).toFixed(1)} gCO2e`;
      document.getElementById('resCost').innerText = `$${Number(costVal).toFixed(4)}`;
      
      const explanation = data.gemini_explanation || opt.message || "Optimal carbon-aware candidate selected.";
      document.getElementById('resExplanation').innerText = explanation;
      
      if (!dispatch) {
        badgeStatus.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
        badgeStatus.innerText = 'OPTIMIZATION COMPLETE';
      }
    }

    if (data.workflow_execution) {
      if (wfBox) wfBox.classList.remove('hidden');
      startElapsedTimer();
      
      const wf = data.workflow_execution;
      const execName = wf.workflow_execution_name || wf.name || '';
      const execId = execName.split('/').pop();
      const initialState = wf.state || wf.status || 'ACTIVE';
      
      const resWfEl = document.getElementById('resWorkflow');
      if (resWfEl) {
        resWfEl.innerText = workflowStatusText(execName, { state: initialState });
      }
      const logsLink = document.getElementById('logsLink');
      if (logsLink && execId) logsLink.href = workflowLogsUrl(execId);
      badgeStatus.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30";
      badgeStatus.innerText = 'WORKFLOW EXECUTING';

      let pollCount = 0;
      pollInterval = setInterval(async () => {
        pollCount++;
        try {
          const statusRes = await fetch(`/api/v1/workflows/status/${execId}`);
          if (statusRes.ok) {
            const info = await statusRes.json();
            const currentState = info.state || 'ACTIVE';
            if (resWfEl) {
              resWfEl.innerText = workflowStatusText(execName, info);
            }

            if (currentState === 'SUCCEEDED') {
              clearInterval(pollInterval);
              stopElapsedTimer();
              badgeStatus.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
              badgeStatus.innerText = 'EXECUTION COMPLETE';
              fetchTelemetry();
            } else if (currentState === 'FAILED') {
              clearInterval(pollInterval);
              stopElapsedTimer();
              badgeStatus.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30";
              badgeStatus.innerText = 'EXECUTION FAILED';
              fetchTelemetry();
            }
          }
        } catch (e) {
          console.error('Polling error:', e);
        }
        if (pollCount > 40) {
          clearInterval(pollInterval);
          stopElapsedTimer();
        }
      }, 3500);
    } else if (!dispatch) {
      if (wfBox) wfBox.classList.add('hidden');
      stopElapsedTimer();
    }
  } catch (err) {
    stopElapsedTimer();
    badgeStatus.className = "px-2.5 py-0.5 text-xs font-semibold rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30";
    badgeStatus.innerText = 'EVALUATION FAILED';
    console.error('Dispatch error:', err);
    alert("Error: " + err.message);
  } finally {
    optBtn.disabled = false;
    dispBtn.disabled = false;
  }
}

async function fetchTelemetry() {
  const tbody = document.getElementById('telemetryRows');
  try {
    const res = await fetch('/api/v1/telemetry');
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Telemetry is unavailable.');
    }
    telemetryData = data || [];
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (!data || data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="p-4 text-center text-slate-500">No telemetry events recorded yet.</td></tr>';
      return;
    }

    data.forEach((r, idx) => {
      const tr = document.createElement('tr');
      const isSuccess = r.execution_status === 'SUCCEEDED';
      const workloadName = r.workload_run_id || r.workload_id || '—';
      
      let costVal = 'NULL';
      if (r.actual_cost !== null && r.actual_cost !== undefined && r.actual_cost !== '') {
        const num = Number(r.actual_cost);
        costVal = !isNaN(num) ? '$' + num.toFixed(6) : 'NULL';
      }

      let runtimeVal = 'NULL';
      if (r.actual_runtime_seconds !== null && r.actual_runtime_seconds !== undefined && r.actual_runtime_seconds !== '') {
        runtimeVal = `${r.actual_runtime_seconds}s`;
      }
      const executionId = workflowExecutionId(r);
      const workflowControls = executionId
        ? `<button onclick="showWorkflowDetails(${idx})" class="px-2 py-0.5 rounded text-[10px] bg-violet-500/10 hover:bg-violet-500/20 text-violet-300 font-mono border border-violet-500/30 transition">Workflow</button>
           <a href="${workflowLogsUrl(executionId)}" target="_blank" rel="noopener" class="ml-1 text-[10px] text-teal-400 hover:text-teal-300">Logs ↗</a>`
        : '<span class="text-slate-500">—</span>';
      
      tr.innerHTML = `
        <td class="p-2.5 font-mono text-slate-200">${workloadName}</td>
        <td class="p-2.5">${r.region || '—'}</td>
        <td class="p-2.5">
          <span class="px-2 py-0.5 rounded text-[10px] ${isSuccess ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-400'}">
            ${r.execution_status || 'UNKNOWN'}
          </span>
        </td>
        <td class="p-2.5 font-mono">${runtimeVal}</td>
        <td class="p-2.5 font-mono">${costVal}</td>
        <td class="p-2.5 whitespace-nowrap">${workflowControls}</td>
        <td class="p-2.5 text-right">
          <button onclick="showJson(${idx})" class="px-2 py-0.5 rounded text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono border border-slate-700 transition">
            { } JSON
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error("Failed to load telemetry:", e);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-4 text-center text-rose-400">${e.message}</td></tr>`;
    }
  }
}

function showJson(index) {
  showDetailModal('Execution Event Telemetry Record', telemetryData[index]);
}

async function showWorkflowDetails(index) {
  const executionId = workflowExecutionId(telemetryData[index]);
  if (!executionId) return;

  showDetailModal('Workflow Execution Details', { state: 'Loading...', execution_id: executionId });
  try {
    const response = await fetch(`/api/v1/workflows/status/${encodeURIComponent(executionId)}`);
    const details = await response.json();
    if (!response.ok) throw new Error(details.detail || 'Workflow details are unavailable.');
    showDetailModal('Workflow Execution Details', details);
  } catch (error) {
    showDetailModal('Workflow Execution Details', { execution_id: executionId, error: error.message });
  }
}

function showDetailModal(title, data) {
  const modalEl = document.getElementById('jsonModal');
  const contentEl = document.getElementById('jsonContent');
  const titleEl = document.getElementById('detailModalTitle');
  if (contentEl && modalEl) {
    if (titleEl) titleEl.innerText = title;
    contentEl.innerText = JSON.stringify(data, null, 2);
    modalEl.classList.remove('hidden');
  }
}

function closeModal() {
  const modalEl = document.getElementById('jsonModal');
  if (modalEl) modalEl.classList.add('hidden');
}

window.addEventListener('DOMContentLoaded', () => {
  fetchTelemetry();
  // Auto-refresh telemetry every 10 seconds
  telemetryPollInterval = setInterval(fetchTelemetry, 10000);
});
