let lastData = null;

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

const $ = id => document.getElementById(id);

function card(title, value) {
  return `<article class="metric-card spotlight"><span>${title}</span><strong>${value}</strong></article>`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function modelRow(m) {
  const state = m.loaded ? (m.healthy === false ? '异常' : '已加载') : (m.idle_unloaded ? '休眠' : '未加载');
  const active = Number(m.active_count || 0);
  const isolation = m.process_isolated ? `隔离 ${m.process_alive ? '在线' : '未启动'}` : '线程内';
  const provider = m.actual_provider || m.device || m.provider || '-';
  const dangerHint = active > 0 ? ` <small class="hint">busy=${active}</small>` : '';
  const id = escapeHtml(m.id);
  return `<tr>
    <td>${id}${m.current ? ' <b class="badge">当前</b>' : ''}</td>
    <td>${state}${dangerHint}</td>
    <td>${escapeHtml(provider)}</td>
    <td>${escapeHtml(isolation)}</td>
    <td class="button-row compact">
      <button class="ghost-button small" data-load="${id}">加载</button>
      <button class="ghost-button small" data-switch="${id}">切换</button>
      <button class="ghost-button small" data-unload="${id}">释放</button>
      <button class="danger-button small" data-force-unload="${id}">强制</button>
    </td>
  </tr>`;
}

function fillConfig(cfg) {
  $('cfg-max-concurrent').value = cfg.max_concurrent_requests ?? 1;
  $('cfg-timeout').value = cfg.request_timeout_seconds ?? 300;
  $('cfg-idle').value = cfg.idle_timeout_seconds ?? 600;
  $('cfg-moss-chunk').value = cfg.moss_stream_chunk_seconds ?? 0.42;
  $('cfg-moss-realtime').checked = Boolean(cfg.moss_realtime_streaming_decode);
  $('cfg-moss-isolation').checked = Boolean(cfg.moss_process_isolation_enabled);
  $('cfg-qps').value = cfg.rate_limit_qps ?? 0;
  $('cfg-burst').value = cfg.rate_limit_burst ?? 5;
  $('cfg-queue').value = cfg.max_queue_length ?? 0;
  $('cfg-trust-proxy').checked = Boolean(cfg.trust_proxy_headers);
  $('cfg-public-status').checked = Boolean(cfg.public_status_endpoints ?? true);
  $('cfg-source').value = cfg.model_source ?? 'auto';
}

function renderSecurity(security) {
  const keyState = security?.api_key_enabled ? '已启用' : '未启用';
  const generated = security?.api_key_auto_generated ? '自动生成' : '手动/环境变量';
  const preview = security?.api_key_preview || '-';
  $('api-key-status').textContent = `状态：${keyState} · 来源：${generated} · 当前：${preview} · 文件：${security?.api_key_file || '-'}`;
}

async function refresh() {
  const data = await api('/admin/api/status');
  lastData = data;
  const loaded = (data.models || []).filter(m => m.loaded).length;
  const busy = (data.models || []).reduce((sum, m) => sum + Number(m.active_count || 0), 0);
  document.getElementById('admin-metrics').innerHTML = [
    card('当前模型', data.current_model || '-'),
    card('已加载模型', loaded),
    card('活跃占用', busy),
    card('源站策略', data.config?.model_source_effective || data.config?.model_source || 'auto')
  ].join('');
  $('models-body').innerHTML = (data.models || []).map(modelRow).join('');
  fillConfig(data.config || {});
  renderSecurity(data.security || {});
  $('admin-json').textContent = JSON.stringify(data, null, 2);
}

async function loadModel(modelId) {
  $('admin-json').textContent = `正在加载 ${modelId}...`;
  const result = await api(`/admin/api/models/${encodeURIComponent(modelId)}/load`, {method:'POST'});
  $('admin-json').textContent = JSON.stringify(result, null, 2);
  await refresh();
}

async function switchModel(modelId) {
  $('admin-json').textContent = `正在切换到 ${modelId}...`;
  const result = await api('/admin/api/models/switch', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({model:modelId, load:true, unload_previous:false})
  });
  $('admin-json').textContent = JSON.stringify(result, null, 2);
  await refresh();
}

async function unloadModel(modelId, force=false) {
  if (force && !confirm(`强制释放 ${modelId}？这会中断正在运行的请求，并 kill 隔离 worker。`)) return;
  const result = await api(`/admin/api/models/${encodeURIComponent(modelId)}/unload`, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({force})
  });
  $('admin-json').textContent = JSON.stringify(result, null, 2);
  await refresh();
}

document.addEventListener('click', async event => {
  try {
    const loadId = event.target?.dataset?.load;
    const switchId = event.target?.dataset?.switch;
    const unloadId = event.target?.dataset?.unload;
    const forceUnloadId = event.target?.dataset?.forceUnload;
    if (loadId) await loadModel(loadId);
    if (switchId) await switchModel(switchId);
    if (unloadId) await unloadModel(unloadId, false);
    if (forceUnloadId) await unloadModel(forceUnloadId, true);
  } catch (err) {
    $('admin-json').textContent = String(err);
    alert('操作失败：' + err.message);
  }
});

$('refresh-btn').onclick = refresh;
$('clear-cache-btn').onclick = async () => { await api('/admin/api/cache', {method:'DELETE'}); await refresh(); };
$('unload-btn').onclick = async () => {
  if (confirm('确认释放所有空闲/可释放模型？忙碌模型会跳过。')) {
    const result = await api('/admin/api/models/unload', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({include_current:true, force:false})});
    $('admin-json').textContent = JSON.stringify(result, null, 2);
    await refresh();
  }
};
const forceUnloadAll = $('force-unload-btn');
if (forceUnloadAll) {
  forceUnloadAll.onclick = async () => {
    if (confirm('强制释放所有模型？这会中断正在运行的请求，适合 MOSS CUDA 卡死/active_count 异常时使用。')) {
      const result = await api('/admin/api/models/unload', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({include_current:true, force:true})});
      $('admin-json').textContent = JSON.stringify(result, null, 2);
      await refresh();
    }
  };
}
$('save-config-btn').onclick = async () => {
  const body = {
    max_concurrent_requests: Number($('cfg-max-concurrent').value),
    request_timeout_seconds: Number($('cfg-timeout').value),
    model_idle_timeout_seconds: Number($('cfg-idle').value),
    moss_stream_chunk_seconds: Number($('cfg-moss-chunk').value),
    moss_realtime_streaming_decode: $('cfg-moss-realtime').checked,
    moss_process_isolation_enabled: $('cfg-moss-isolation').checked,
    rate_limit_qps: Number($('cfg-qps').value),
    rate_limit_burst: Number($('cfg-burst').value),
    max_queue_length: Number($('cfg-queue').value),
    trust_proxy_headers: $('cfg-trust-proxy').checked,
    public_status_endpoints: $('cfg-public-status').checked,
    model_source: $('cfg-source').value
  };
  const result = await api('/admin/api/config', {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  $('admin-json').textContent = JSON.stringify(result, null, 2);
  await refresh();
};
$('reveal-key-btn').onclick = async () => {
  const data = await api('/admin/api/security?reveal=true');
  $('api-key-status').textContent = data.api_key ? `当前 API Key：${data.api_key}` : '当前未启用 API Key';
};
$('rotate-key-btn').onclick = async () => {
  if (!confirm('确认生成/轮换 API Key？旧客户端 token 会立即失效。')) return;
  const data = await api('/admin/api/security/key', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({rotate:true})});
  $('api-key-status').textContent = `新 API Key：${data.api_key}`;
  $('admin-json').textContent = JSON.stringify(data, null, 2);
};
refresh().catch(err => { $('admin-json').textContent = String(err); });
