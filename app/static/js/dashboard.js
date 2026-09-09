let telemetryData = [];
let pollInterval = null;
let timerInterval = null;
let startTime = null;

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
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const opt = data.optimization_result;
    if (opt && opt.selected_candidate) {
      const cand = opt.selected_candidate;
      document.getElementById('resRegion').innerText = cand.region;
      document.getElementById('resTier').innerText = `${cand.machine_type} (${cand.provisioning_model.value})`;
      document.getElementById('resCarbon').innerText = `${cand.carbon_score.toFixed(1)} gCO2e`;
      document.getElementById('resCost').innerText = `$${cand.estimated_compute_cost_usd.toFixed(4)}`;
      document.getElementById('resExplanation').innerText = data.gemini_explanation;
    }

    if (data.workflow_execution) {
      wfBox.classList.remove('hidden');
      startElapsedTimer();
      const wf = data.workflow_execution;
      const execId = (wf.workflow_execution_name || wf.name).split('/').pop();
      document.getElementById('resWorkflow').innerText = `Workflow Execution Dispatched:\n${wf.name}\nStatus: ACTIVE`;
      badgeStatus.innerText = 'WORKFLOW EXECUTING';

      pollInterval = setInterval(async () => {
        const statusRes = await fetch(`/api/v1/workflows/status/${execId}`);
        if (statusRes.ok) {
          const info = await statusRes.json();
          const state = info.state || 'ACTIVE';
          document.getElementById('resWorkflow').innerText = `Workflow Execution Dispatched:\n${wf.name}\nStatus: ${state}`;
          if (state === 'SUCCEEDED' || state === 'FAILED') {
            clearInterval(pollInterval);
            stopElapsedTimer();
            badgeStatus.innerText = state === 'SUCCEEDED' ? 'EXECUTION COMPLETE' : 'EXECUTION FAILED';
            fetchTelemetry();
          }
        }
      }, 3500);
    }
  } catch (err) {
    stopElapsedTimer();
    alert("Error: " + err.message);
  } finally {
    optBtn.disabled = false;
    dispBtn.disabled = false;
  }
}

async function fetchTelemetry() {
  const res = await fetch('/api/v1/telemetry');
  const data = await res.json();
  telemetryData = data;
  const tbody = document.getElementById('telemetryRows');
  tbody.innerHTML = '';
  data.forEach((r, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="p-2.5 font-mono text-slate-200">${r.workload_run_id}</td>
      <td class="p-2.5">${r.region}</td>
      <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] ${r.execution_status === 'SUCCEEDED' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-800'}">${r.execution_status}</span></td>
      <td class="p-2.5 font-mono">${r.actual_runtime_seconds}s</td>
      <td class="p-2.5 font-mono">$${r.actual_cost.toFixed(6)}</td>
      <td class="p-2.5 text-right"><button onclick="showJson(${idx})" class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 font-mono border border-slate-700">{ } JSON</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function showJson(index) {
  document.getElementById('jsonContent').innerText = JSON.stringify(telemetryData[index], null, 2);
  document.getElementById('jsonModal').classList.remove('hidden');
}

function closeModal() { document.getElementById('jsonModal').classList.add('hidden'); }
window.onload = fetchTelemetry;