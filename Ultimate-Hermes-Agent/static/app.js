const $ = (id) => document.getElementById(id);
let currentPage = 'chat';
let activeDownloadPoll = null;
let analyzedVideo = null;
let toastTimer = null;

function escapeText(value) { return String(value ?? ''); }
function showToast(message, error = false) {
  const el = $('toast'); el.textContent = message; el.classList.toggle('error', error); el.classList.remove('hidden');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.add('hidden'), 4500);
}
async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options });
  let data = {};
  try { data = await response.json(); } catch { data = { detail: await response.text() }; }
  if (!response.ok) throw new Error(data.detail || data.message || `HTTP ${response.status}`);
  return data;
}
function setPage(page) {
  currentPage = page;
  document.querySelectorAll('.nav-item').forEach(button => button.classList.toggle('active', button.dataset.page === page));
  document.querySelectorAll('.page').forEach(section => section.classList.toggle('active', section.id === `page-${page}`));
  const names = {chat:'Assistant',youtube:'YouTube Downloader',files:'File Memory',windows:'Windows Tools',skills:'Skills Library',settings:'Settings'};
  $('page-title').textContent = names[page] || 'Assistant';
  if (page === 'windows') { refreshMcp(); refreshApprovals(); }
  if (page === 'youtube') refreshDownloads();
  if (page === 'files') refreshFileStats();
  if (page === 'settings') loadSettings();
}
document.querySelectorAll('.nav-item').forEach(button => button.addEventListener('click', () => setPage(button.dataset.page)));
function renderMessages(messages) {
  const container = $('chat-messages'); container.replaceChildren();
  for (const message of messages || []) {
    if (!['user','assistant','system'].includes(message.role)) continue;
    const article = document.createElement('article'); article.className = `message ${message.role}`;
    const label = document.createElement('div'); label.className = 'message-role'; label.textContent = message.role === 'user' ? 'You' : message.role === 'assistant' ? 'Ultimate Hermes' : 'System';
    const body = document.createElement('div'); body.textContent = escapeText(message.content);
    article.append(label, body); container.appendChild(article);
  }
  container.scrollTop = container.scrollHeight;
}
async function loadState() {
  try {
    const state = await api('/api/state');
    renderMessages(state.messages || []);
    updateHealth(state);
    renderSkills(state.skills || []);
    renderApprovals(state.pending_approvals || []);
    $('indexed-count').textContent = state.file_memory?.indexed_files ?? 0;
    $('chunk-count').textContent = state.file_memory?.chunks ?? 0;
    if (state.settings) applyPublicSettings(state.settings);
  } catch (error) { $('status-text').textContent = 'Backend unavailable'; $('status-dot').className = 'status-dot warn'; }
}
function updateHealth(state) {
  const online = !!state.ok;
  $('status-dot').className = `status-dot ${online ? 'online' : 'warn'}`;
  $('status-text').textContent = state.emergency_stop ? 'Emergency stop active' : online ? 'Backend online' : 'Checking services';
  $('model-chip').textContent = `${state.gemini_model || 'Gemini'} · ${state.gemini_key_count || 0} key(s)`;
  $('key-count-pill').textContent = `${state.gemini_key_count || 0} key(s)`;
  $('stop-button').classList.toggle('hidden', !!state.emergency_stop);
  $('reset-stop-button').classList.toggle('hidden', !state.emergency_stop);
  if (state.available_models) {
    populateModelSelectors(state.available_models, state.gemini_model);
  }
}

let currentAvailableModels = [];

function populateModelSelectors(models, activeModel) {
  currentAvailableModels = models || [];
  const topSelect = $('topbar-model-select');
  const settingsSelect = $('settings-model-select');
  if (!topSelect || !settingsSelect) return;
  const currentVal = activeModel || topSelect.value || 'gemini-flash-lite-latest';

  const fill = (el) => {
    el.replaceChildren();
    let hasMatch = false;
    for (const m of currentAvailableModels) {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.label || m.id;
      if (m.id === currentVal) {
        opt.selected = true;
        hasMatch = true;
      }
      el.appendChild(opt);
    }
    const custom = document.createElement('option');
    custom.value = 'custom';
    custom.textContent = 'Custom model ID...';
    if (!hasMatch) custom.selected = true;
    el.appendChild(custom);
    el.value = hasMatch ? currentVal : 'custom';
  };

  fill(topSelect);
  fill(settingsSelect);
  const input = $('gemini-model');
  if (input && document.activeElement !== input) {
    input.value = currentVal;
  }
}

function applyPublicSettings(settings) {
  const activeModel = settings.gemini_model || 'gemini-flash-lite-latest';
  const keyCount = settings.gemini_key_count || 0;
  const savedCount = settings.saved_key_count ?? keyCount;

  $('model-chip').textContent = `${activeModel} · ${keyCount} key(s)`;
  $('key-count-pill').textContent = `${keyCount} key(s)`;
  $('settings-file').textContent = `Local settings file: ${settings.settings_file || 'data/local_settings.json'}. Key values are safely stored locally.`;

  if (settings.available_models) {
    populateModelSelectors(settings.available_models, activeModel);
  } else {
    const input = $('gemini-model');
    if (input) input.value = activeModel;
  }

  if (Array.isArray(settings.gemini_api_keys) && settings.gemini_api_keys.length > 0) {
    const keysInput = $('gemini-keys');
    if (keysInput && (document.activeElement !== keysInput || !keysInput.value.trim())) {
      keysInput.value = settings.gemini_api_keys.join('\n');
    }
  }

  const ind = $('keys-status-indicator');
  const clearBtn = $('clear-keys-button');
  if (ind) {
    if (savedCount > 0) {
      ind.innerHTML = `<span>✔ <strong>${savedCount} key(s) saved in local settings & active</strong>. You can edit them above anytime.</span>`;
      if (clearBtn) clearBtn.classList.remove('hidden');
    } else {
      ind.innerHTML = `<span class="muted">No API keys saved yet. Paste one or more keys above to configure.</span>`;
      if (clearBtn) clearBtn.classList.add('hidden');
    }
  }
}
async function sendMessage() {
  const input = $('chat-input'); const message = input.value.trim();
  if (!message) return;
  input.value = ''; input.style.height = 'auto'; $('chat-error').classList.add('hidden');
  const send = $('send-button'); send.disabled = true; send.textContent = 'Working…';
  // Keep the user message visible during a potentially slow model call.
  const container = $('chat-messages');
  const userMessage = document.createElement('article'); userMessage.className = 'message user';
  const role = document.createElement('div'); role.className = 'message-role'; role.textContent = 'You';
  const text = document.createElement('div'); text.textContent = message; userMessage.append(role,text); container.appendChild(userMessage); container.scrollTop = container.scrollHeight;
  try {
    const result = await api('/api/chat', { method:'POST', body: JSON.stringify({message}) });
    renderMessages(result.history || []);
    if ((result.pending_approvals || []).length) { showToast('A Windows action is waiting for your approval.'); refreshApprovals(); }
    if (result.stopped) showToast('The tool loop was stopped.');
  } catch (error) {
    $('chat-error').textContent = error.message; $('chat-error').classList.remove('hidden');
    showToast(error.message, true);
  } finally { send.disabled = false; send.innerHTML = 'Send <span>↗</span>'; input.focus(); refreshHealth(); }
}
$('send-button').addEventListener('click', sendMessage);
$('chat-input').addEventListener('keydown', event => { if (event.key === 'Enter' && event.ctrlKey) { event.preventDefault(); sendMessage(); } });
$('chat-input').addEventListener('input', event => { event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight, 220)}px`; });

async function refreshHealth() { try { updateHealth(await api('/api/health')); } catch {} }
$('stop-button').addEventListener('click', activateStop);
$('reset-stop-button').addEventListener('click', resetStopAction);
async function activateStop() { try { await api('/api/emergency-stop',{method:'POST',body:'{}'}); showToast('Emergency stop activated.'); await refreshHealth(); await refreshApprovals(); } catch (error) { showToast(error.message,true); } }
async function resetStopAction() { try { await api('/api/emergency-stop/reset',{method:'POST',body:'{}'}); showToast('Emergency stop reset.'); await refreshHealth(); } catch (error) { showToast(error.message,true); } }
document.addEventListener('keydown', event => {
  if (event.ctrlKey && event.key.toLowerCase() === 'k') { event.preventDefault(); setPage('chat'); $('chat-input').focus(); }
  else if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'q') { event.preventDefault(); activateStop(); }
  else if (event.key === 'Escape') { const active = document.activeElement; if (active && ['INPUT','TEXTAREA'].includes(active.tagName)) active.value = ''; }
});

$('analyze-youtube').addEventListener('click', async () => {
  const url = $('youtube-url').value.trim(); if (!url) return showToast('Enter a YouTube URL first.', true);
  $('youtube-status').textContent = 'Analyzing formats…'; $('start-download').disabled = true; analyzedVideo = null; $('video-info').classList.add('hidden');
  try {
    const info = await api('/api/youtube/analyze',{method:'POST',body:JSON.stringify({url})}); analyzedVideo = info;
    const box = $('video-info'); box.replaceChildren();
    if (info.thumbnail) { const img = document.createElement('img'); img.src = info.thumbnail; img.alt = 'Video thumbnail'; box.appendChild(img); }
    const details = document.createElement('div'); const title = document.createElement('h4'); title.textContent = info.title || 'Video';
    const meta = document.createElement('p'); const duration = Number.isFinite(info.duration_seconds) ? `${Math.floor(info.duration_seconds/60)}m ${Math.floor(info.duration_seconds%60)}s` : 'Duration unknown';
    meta.textContent = `${info.uploader || 'Unknown uploader'} · ${duration}\nResolutions: ${(info.resolutions || []).map(x=>`${x}p`).join(', ') || 'Not reported'}`;
    details.append(title,meta); box.appendChild(details); box.classList.remove('hidden'); $('start-download').disabled = false; $('youtube-status').textContent = 'Ready. Select a format and start the job.';
  } catch (error) { $('youtube-status').textContent = error.message; showToast(error.message,true); }
});
$('start-download').addEventListener('click', async () => {
  if (!analyzedVideo) return;
  $('start-download').disabled = true; $('youtube-status').textContent = 'Starting download…';
  try { const job = await api('/api/youtube/download',{method:'POST',body:JSON.stringify({url:$('youtube-url').value.trim(),quality:$('youtube-quality').value,output_format:$('youtube-format').value,engine:$('youtube-engine')?$('youtube-engine').value:'auto'})});
    $('download-progress-wrap').classList.remove('hidden'); pollDownload(job.id); }
  catch (error) { $('youtube-status').textContent = error.message; $('start-download').disabled = false; showToast(error.message,true); }
});
async function pollDownload(id) {
  if (activeDownloadPoll) clearTimeout(activeDownloadPoll);
  try {
    const job = await api(`/api/youtube/jobs/${encodeURIComponent(id)}`);
    $('download-progress-wrap').classList.remove('hidden'); $('download-progress-bar').style.width = `${job.progress || 0}%`;
    $('download-progress-percent').textContent = `${Math.round(job.progress || 0)}%`;
    let label = job.status;
    if (job.status === 'downloading') { const speed = job.speed ? `${(job.speed/1024/1024).toFixed(2)} MB/s` : ''; const eta = Number.isFinite(job.eta_seconds) ? ` · ETA ${job.eta_seconds}s` : ''; label = `${speed || 'Downloading'}${eta}`; }
    $('download-progress-text').textContent = label; $('youtube-status').textContent = job.status === 'failed' ? job.error : job.status === 'completed' ? 'Download complete.' : 'Download job running…';
    if (job.status === 'completed') { const link = document.createElement('a'); link.href = `/api/youtube/files/${encodeURIComponent(job.file_name)}`; link.textContent = `Download ${job.file_name}`; link.className='text-link'; $('youtube-status').replaceChildren(link); showToast('Download completed.'); $('start-download').disabled = false; await refreshDownloads(); return; }
    if (job.status === 'failed') { showToast(job.error || 'Download failed.',true); $('start-download').disabled = false; return; }
    activeDownloadPoll = setTimeout(() => pollDownload(id), 1300);
  } catch (error) { $('youtube-status').textContent = error.message; $('start-download').disabled = false; }
}
$('refresh-downloads').addEventListener('click', refreshDownloads);
async function refreshDownloads() {
  try { const data = await api('/api/youtube/files'); const box = $('download-list'); box.replaceChildren();
    if (!data.files.length) { box.textContent = 'No downloads yet.'; box.className='file-list muted'; return; }
    box.className='file-list'; for (const file of data.files) { const row=document.createElement('div'); row.className='file-row'; const left=document.createElement('div'); const name=document.createElement('div'); name.className='file-name'; name.textContent=file.file_name; const meta=document.createElement('div'); meta.className='file-meta'; meta.textContent=`${(file.size_bytes/1024/1024).toFixed(1)} MB`; left.append(name,meta); const link=document.createElement('a'); link.className='text-link'; link.href=`/api/youtube/files/${encodeURIComponent(file.file_name)}`; link.textContent='Save file ↗'; row.append(left,link); box.appendChild(row); }
  } catch (error) { $('download-list').textContent=error.message; }
}

$('index-folder').addEventListener('click', async () => {
  const path = $('folder-path').value.trim(); if (!path) return showToast('Enter a folder path.',true);
  $('index-folder').disabled = true; $('index-status').textContent='Indexing supported files…';
  try { const result=await api('/api/files/index',{method:'POST',body:JSON.stringify({path,recursive:true,force:false})}); $('index-status').textContent=`Scan complete: ${result.scanned} candidate files, ${result.indexed_or_updated} indexed/updated, ${result.unchanged} unchanged, ${result.skipped} skipped, ${result.errors} errors.`; await refreshFileStats(); showToast('File index updated.'); }
  catch(error) { $('index-status').textContent=error.message; showToast(error.message,true); }
  finally { $('index-folder').disabled=false; }
});
$('search-files').addEventListener('click', searchFiles);
$('file-query').addEventListener('keydown', event=>{if(event.key==='Enter')searchFiles();});
async function searchFiles() {
  const query=$('file-query').value.trim(); if(!query)return;
  const box=$('file-results'); box.textContent='Searching…';
  try { const data=await api('/api/files/search',{method:'POST',body:JSON.stringify({query,limit:10})}); box.replaceChildren();
    if(!data.results.length){box.textContent='No match. Index more folders or try different keywords.';return;}
    for(const result of data.results){const card=document.createElement('div');card.className='search-result';const path=document.createElement('div');path.className='path';path.textContent=result.path;const excerpt=document.createElement('p');excerpt.textContent=result.excerpt;card.append(path,excerpt);box.appendChild(card);}
  }catch(error){box.textContent=error.message;}
}
async function refreshFileStats(){try{const data=await api('/api/files/stats');$('indexed-count').textContent=data.indexed_files;$('chunk-count').textContent=data.chunks;}catch{}}
$('analyze-archive').addEventListener('click', async () => {
  const path=$('archive-path').value.trim(); if(!path)return showToast('Enter the ZIP path.',true); const box=$('archive-result');box.classList.remove('hidden');box.textContent='Inspecting archive…';
  try{const data=await api('/api/archives/analyze',{method:'POST',body:JSON.stringify({path})});box.textContent=JSON.stringify(data,null,2);showToast('Archive inventory ready.');}
  catch(error){box.textContent=error.message;showToast(error.message,true);}
});

$('refresh-mcp').addEventListener('click',refreshMcp);
async function refreshMcp(){
  $('refresh-mcp').disabled=true;
  try{const data=await api('/api/mcp/refresh',{method:'POST',body:'{}'});$('mcp-summary').textContent=`${data.configured_servers || 0} configured server(s) · ${data.tool_count || 0} tool(s) available.`; $('mcp-error').classList.toggle('hidden',!data.error);$('mcp-error').textContent=data.error||'';renderMcpTools(data.tools||[]);await refreshApprovals();}
  catch(error){$('mcp-summary').textContent='Could not connect to MCP server.';$('mcp-error').classList.remove('hidden');$('mcp-error').textContent=error.message;}
  finally{$('refresh-mcp').disabled=false;}
}
function renderMcpTools(tools){const box=$('mcp-tools');box.replaceChildren();if(!tools.length){box.textContent='No remote MCP tools found. Configure a server in Settings, then refresh. Local file and YouTube tools work without MCP.';box.className='tool-grid muted';return;}box.className='tool-grid';for(const tool of tools){const card=document.createElement('div');card.className='tool-card';const name=document.createElement('h4');name.textContent=tool.name;const p=document.createElement('p');p.textContent=(tool.description||'No description')+' · Approval required';const button=document.createElement('button');button.className='secondary-button';button.textContent='Call tool…';button.addEventListener('click',()=>manualMcpCall(tool));card.append(name,p,button);box.appendChild(card);}}
async function manualMcpCall(tool){const raw=prompt(`Arguments JSON for ${tool.name}\nSchema: ${JSON.stringify(tool.input_schema||{},null,2)}`,'{}');if(raw===null)return;let args;try{args=JSON.parse(raw);}catch{return showToast('Arguments must be valid JSON.',true);}if(!confirm(`Approve this Windows/MCP action?\n\nTool: ${tool.name}\nArguments:\n${JSON.stringify(args,null,2)}`))return;
  try{const result=await api('/api/tools/call',{method:'POST',body:JSON.stringify({name:tool.name,arguments:args})});if(result.approval_required){showToast('Action queued. Approve it in Pending approvals.');await refreshApprovals();}else{showToast('Tool returned a result.');alert(JSON.stringify(result.result,null,2));}}
  catch(error){showToast(error.message,true);}}
async function refreshApprovals(){try{const data=await api('/api/approvals');renderApprovals(data.pending||[]);$('stop-button').classList.toggle('hidden',!!data.emergency_stop);$('reset-stop-button').classList.toggle('hidden',!data.emergency_stop);}catch{}}
function renderApprovals(approvals){const box=$('approval-list');box.replaceChildren();if(!approvals.length){box.className='approval-list';box.textContent='No pending actions.';return;}box.className='approval-list';for(const approval of approvals){const card=document.createElement('div');card.className='approval-card';const title=document.createElement('h4');title.textContent=`Approval required · ${approval.display_name}`;const args=document.createElement('pre');args.textContent=JSON.stringify(approval.arguments,null,2);const actions=document.createElement('div');actions.className='approval-actions';const approve=document.createElement('button');approve.className='approve-button';approve.textContent='Approve and run';approve.addEventListener('click',()=>approveAction(approval.id));const deny=document.createElement('button');deny.className='deny-button';deny.textContent='Deny';deny.addEventListener('click',()=>denyAction(approval.id));actions.append(approve,deny);card.append(title,args,actions);box.appendChild(card);}}
async function approveAction(id){if(!confirm('Run this tool now? Review the displayed arguments first.'))return;try{const data=await api(`/api/approvals/${id}/approve`,{method:'POST',body:JSON.stringify({confirm:true})});showToast(`Action ${data.status}.`);renderMessages(data.history||[]);await refreshApprovals();}catch(error){showToast(error.message,true);}}
async function denyAction(id){try{await api(`/api/approvals/${id}/deny`,{method:'POST',body:'{}'});showToast('Action denied; it was not run.');await refreshApprovals();}catch(error){showToast(error.message,true);}}

async function renderSkills(skills){const box=$('skills-list');if(!box)return;box.replaceChildren();for(const skill of skills||[]){const card=document.createElement('div');card.className='skill-card';const title=document.createElement('h4');title.textContent=skill.name;const path=document.createElement('div');path.className='file-meta';path.textContent=skill.path;const desc=document.createElement('p');desc.textContent=skill.description||'';card.append(title,path,desc);box.appendChild(card);}}
async function onModelSelectChanged(newModel) {
  if (newModel === 'custom') {
    setPage('settings');
    $('gemini-model').focus();
    return;
  }
  try {
    const res = await api('/api/settings/model', {
      method: 'POST',
      body: JSON.stringify({ model: newModel })
    });
    applyPublicSettings(res);
    showToast(`Model switched to ${newModel}`);
  } catch (err) {
    showToast(err.message, true);
  }
}

$('topbar-model-select').addEventListener('change', (e) => {
  onModelSelectChanged(e.target.value);
});

$('settings-model-select').addEventListener('change', (e) => {
  const val = e.target.value;
  if (val !== 'custom') {
    $('gemini-model').value = val;
    onModelSelectChanged(val);
  } else {
    $('gemini-model').focus();
  }
});

let keysMasked = false;
const toggleBtn = $('toggle-keys-visibility');
if (toggleBtn) {
  toggleBtn.addEventListener('click', () => {
    keysMasked = !keysMasked;
    $('gemini-keys').classList.toggle('masked-keys', keysMasked);
    toggleBtn.textContent = keysMasked ? '👁 Unmask keys' : '👁 Mask keys';
  });
}

$('clear-keys-button').addEventListener('click', async () => {
  if (!confirm('Are you sure you want to remove all saved Gemini API keys from the local dashboard?')) return;
  try {
    const res = await api('/api/settings/keys/clear', { method: 'POST', body: '{}' });
    $('gemini-keys').value = '';
    applyPublicSettings(res);
    showToast('Saved Gemini keys cleared.');
  } catch (err) {
    showToast(err.message, true);
  }
});

async function loadSettings() {
  try {
    const settings = await api('/api/settings');
    applyPublicSettings(settings);
    const config = await api('/api/settings/configuration');
    $('mcp-config').value = JSON.stringify(config.mcp_servers || [], null, 2);
  } catch (error) {
    $('settings-status').textContent = error.message;
  }
}

$('save-settings').addEventListener('click', async () => {
  let servers;
  try {
    servers = JSON.parse($('mcp-config').value || '[]');
    if (!Array.isArray(servers)) throw new Error('MCP config must be a JSON array.');
  } catch (error) {
    $('settings-status').textContent = error.message;
    return;
  }
  let chosenModel = $('gemini-model').value.trim();
  if (!chosenModel) chosenModel = $('settings-model-select').value;
  if (!chosenModel || chosenModel === 'custom') chosenModel = 'gemini-flash-lite-latest';

  $('save-settings').disabled = true;
  $('settings-status').textContent = 'Saving…';
  try {
    const result = await api('/api/settings', {
      method: 'POST',
      body: JSON.stringify({
        gemini_model: chosenModel,
        gemini_api_keys_text: $('gemini-keys').value,
        mcp_servers_json: JSON.stringify(servers)
      })
    });
    if (Array.isArray(result.gemini_api_keys) && result.gemini_api_keys.length > 0) {
      $('gemini-keys').value = result.gemini_api_keys.join('\n');
    }
    $('settings-status').textContent = `Saved! ${result.gemini_key_count} key(s) active.`;
    applyPublicSettings(result);
    showToast(`Settings saved! ${result.gemini_key_count} key(s) active.`);
    await refreshMcp();
  } catch (error) {
    $('settings-status').textContent = error.message;
    showToast(error.message, true);
  } finally {
    $('save-settings').disabled = false;
  }
});

loadState();
setInterval(refreshHealth, 8000);
setInterval(refreshApprovals, 3500);

