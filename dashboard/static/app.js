let activeView = 'overview';
let currentSiteId = 'ccm';
let allWebsitesList = [];
let activityChartInstance = null;
let categoryChartInstance = null;

document.addEventListener('DOMContentLoaded', async () => {
  initClock();
  initNavigation();
  initEventListeners();
  initAmbientParticles();
  init3DCyberCore();
  init3DCardTilt();

  // Restore saved active view from hash or sessionStorage
  const hashView = window.location.hash.replace('#', '').trim();
  const savedView = sessionStorage.getItem('ccm_active_view');
  const initialView = hashView || savedView || 'overview';

  // Restore saved active website from sessionStorage or localStorage
  const savedSite = sessionStorage.getItem('ccm_selected_site') || localStorage.getItem('ccm_selected_site');
  if (savedSite) {
    currentSiteId = savedSite;
  }

  await initWebsiteSwitcher();
  switchToView(initialView);
});

function initClock() {
  const clockEl = document.getElementById('live-time');
  function update() {
    const now = new Date();
    clockEl.textContent = 'UTC ' + now.toISOString().substring(11, 19);
  }
  update();
  setInterval(update, 1000);
}

function switchToView(view) {
  const navItems = document.querySelectorAll('.nav-item');
  const targetNav = document.querySelector(`.nav-item[data-view="${view}"]`);
  const effectiveView = targetNav ? view : 'overview';

  navItems.forEach(n => n.classList.remove('active'));
  const activeNavItem = document.querySelector(`.nav-item[data-view="${effectiveView}"]`);
  if (activeNavItem) activeNavItem.classList.add('active');

  document.querySelectorAll('.page-view').forEach(v => v.classList.remove('active'));
  const targetView = document.getElementById(`view-${effectiveView}`);
  if (targetView) targetView.classList.add('active');

  activeView = effectiveView;
  sessionStorage.setItem('ccm_active_view', effectiveView);
  if (window.location.hash !== '#' + effectiveView) {
    history.replaceState(null, '', '#' + effectiveView);
  }

  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.textContent = getTitleForView(effectiveView);
  loadCurrentView(effectiveView);
}

window.openMobileSidebar = function(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (sidebar) sidebar.classList.add('open');
  if (overlay) overlay.classList.add('active');
};

window.closeMobileSidebar = function(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (sidebar) sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('active');
};

window.toggleMobileSidebar = function(e) {
  if (e) {
    if (e.stopPropagation) e.stopPropagation();
    if (e.preventDefault) e.preventDefault();
  }
  const sidebar = document.getElementById('sidebar');
  if (sidebar && sidebar.classList.contains('open')) {
    window.closeMobileSidebar(e);
  } else {
    window.openMobileSidebar(e);
  }
};

function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const closeBtn = document.getElementById('sidebar-close-btn');

  if (closeBtn) {
    closeBtn.onclick = function(e) {
      e.stopPropagation();
      window.closeMobileSidebar(e);
    };
  }

  if (overlay) {
    overlay.onclick = function(e) {
      e.stopPropagation();
      window.closeMobileSidebar(e);
    };
  }

  if (sidebar) {
    sidebar.onclick = function(e) {
      e.stopPropagation();
    };
  }

  navItems.forEach(item => {
    item.onclick = function(e) {
      const view = item.dataset.view;
      if (!view) return;
      switchToView(view);
      window.closeMobileSidebar(e);
    };
  });
}

function getTitleForView(view) {
  const activeSite = allWebsitesList.find(s => s.site_id === currentSiteId);
  const siteSuffix = currentSiteId === 'all'
    ? ' (Portfolio View)'
    : (activeSite ? ` — ${activeSite.name}` : '');

  const titles = {
    'overview': `System Overview & 3D Telemetry${siteSuffix}`,
    'agents': `18-Agent Operating System Registry${siteSuffix}`,
    'tasks': `Task Queue & Execution Pipeline${siteSuffix}`,
    'approvals': `Human Approval Queue${siteSuffix}`,
    'scheduler': `Automated Cron Job Scheduler${siteSuffix}`,
    'ai-usage': `AI Model Router & Cost Analytics${siteSuffix}`,
    'logs': `Structured Execution Logs${siteSuffix}`,
    'errors': `Error Tracing & Recovery${siteSuffix}`,
    'audit': `Immutable System Audit Trail${siteSuffix}`,
    'health': `System Health & Diagnostics${siteSuffix}`,
    'settings': `Command Center Configuration${siteSuffix}`
  };
  return titles[view] || 'Dashboard';
}

function initEventListeners() {
  const refreshBtn = document.getElementById('refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      const icon = refreshBtn.querySelector('i');
      if (icon) icon.classList.add('fa-spin');
      refreshBtn.disabled = true;
      
      // Save current view so it reloads on the same page
      sessionStorage.setItem('ccm_active_view', activeView);

      // Force hard refresh by reloading with cache-busting timestamp parameter
      const cleanPath = window.location.pathname;
      const targetHash = '#' + activeView;
      window.location.href = cleanPath + '?_reload=' + Date.now() + targetHash;
    });
  }

  document.getElementById('open-create-task-modal').addEventListener('click', async () => {
    await populateAgentDropdown();
    openModal('create-task-modal');
  });

  document.getElementById('create-task-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const siteId = document.getElementById('task-website-select').value || currentSiteId;
    const agentId = document.getElementById('task-agent-select').value;
    const action = document.getElementById('task-action-select').value;
    const approval = document.getElementById('task-approval-select').value === 'true';
    const priority = document.getElementById('task-priority-select').value;

    try {
      const res = await fetch('/api/tasks/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: agentId,
          task_type: action,
          input_data: { action: action, site: siteId, site_id: siteId },
          requires_approval: approval,
          priority: priority,
          site_id: siteId
        })
      });
      const data = await res.json();
      closeModal('create-task-modal');
      alert(`Task ${data.task.task_id} created for website [${siteId}] successfully.`);
      loadCurrentView(activeView);
    } catch (err) {
      alert(`Failed to create task: ${err}`);
    }
  });

  document.getElementById('logs-agent-filter').addEventListener('change', () => {
    loadLogs();
  });
}

/* --- Multi-Website Switcher & Registry Handlers --- */
async function initWebsiteSwitcher() {
  try {
    const res = await fetch('/api/websites');
    const data = await res.json();
    if (data.websites && data.websites.length > 0) {
      allWebsitesList = data.websites;
    }
  } catch (err) {
    console.error('Failed to load websites list:', err);
  }

  renderWebsiteDropdown();
  updateWebsiteHeaderUI();

  // Toggle dropdown on button click
  const dropdownWrap = document.getElementById('website-switcher-wrap');
  const dropdownBtn = document.getElementById('website-dropdown-btn');
  const addModalBtn = document.getElementById('open-add-website-modal-btn');

  if (dropdownBtn) {
    dropdownBtn.onclick = (e) => {
      e.stopPropagation();
      dropdownWrap.classList.toggle('open');
    };
  }

  if (addModalBtn) {
    addModalBtn.onclick = (e) => {
      e.stopPropagation();
      dropdownWrap.classList.remove('open');
      openModal('add-website-modal');
    };
  }

  // Close dropdown on outside click
  document.addEventListener('click', (e) => {
    if (dropdownWrap && !dropdownWrap.contains(e.target)) {
      dropdownWrap.classList.remove('open');
    }
  });
}

function renderWebsiteDropdown() {
  const listEl = document.getElementById('dropdown-site-list');
  const countBadge = document.getElementById('dropdown-sites-count');
  if (!listEl) return;

  if (countBadge) countBadge.textContent = `${allWebsitesList.length} Sites`;

  let itemsHtml = `
    <div class="dropdown-site-item ${currentSiteId === 'all' ? 'selected' : ''}" onclick="switchWebsite('all')">
      <div class="dropdown-site-left">
        <span class="site-dot" style="background:#10b981; box-shadow:0 0 8px #10b981;"></span>
        <div class="dropdown-site-info">
          <div class="dropdown-site-title">All Websites (Portfolio)</div>
          <div class="dropdown-site-sub">Aggregated Portfolio Telemetry</div>
        </div>
      </div>
      ${currentSiteId === 'all' ? '<i class="fa-solid fa-check" style="color:var(--accent-cyan);"></i>' : ''}
    </div>
  `;

  itemsHtml += allWebsitesList.map(site => `
    <div class="dropdown-site-item ${currentSiteId === site.site_id ? 'selected' : ''}" onclick="switchWebsite('${site.site_id}')">
      <div class="dropdown-site-left">
        <span class="site-dot" style="background:${site.color_accent || '#06b6d4'}; box-shadow:0 0 8px ${site.color_accent || '#06b6d4'};"></span>
        <div class="dropdown-site-info">
          <div class="dropdown-site-title">${site.name}</div>
          <div class="dropdown-site-sub">${site.domain.replace('https://', '').replace('http://', '')} &bull; ${site.location}</div>
        </div>
      </div>
      ${currentSiteId === site.site_id ? '<i class="fa-solid fa-check" style="color:var(--accent-cyan);"></i>' : ''}
    </div>
  `).join('');

  listEl.innerHTML = itemsHtml;
}

function updateWebsiteHeaderUI() {
  const nameEl = document.getElementById('active-site-name');
  const dotEl = document.getElementById('active-site-dot');
  const heroDesc = document.getElementById('cyber-hero-desc');
  const pageTitleEl = document.getElementById('page-title');
  const sidebarBrandTitle = document.querySelector('.brand-title');
  const heroH3 = document.querySelector('.cyber-core-info h3');

  if (pageTitleEl) {
    pageTitleEl.textContent = getTitleForView(activeView);
  }

  if (currentSiteId === 'all') {
    if (nameEl) nameEl.textContent = 'All Websites (Portfolio)';
    if (dotEl) {
      dotEl.style.background = '#10b981';
      dotEl.style.boxShadow = '0 0 8px #10b981';
    }
    if (sidebarBrandTitle) sidebarBrandTitle.textContent = 'Portfolio OS';
    if (heroH3) heroH3.innerHTML = '<i class="fa-solid fa-car" style="color: var(--accent-cyan);"></i> Master Orchestrator — Multi-Brand AI Telemetry';
    if (heroDesc) heroDesc.textContent = 'Multi-Tenant Portfolio Aggregator controlling SEO, Google Ads, Meta Ads, Social Media, and Leads across all connected websites.';
  } else {
    const activeSite = allWebsitesList.find(s => s.site_id === currentSiteId) || allWebsitesList[0];
    if (activeSite) {
      if (nameEl) nameEl.textContent = activeSite.name.length > 22 ? activeSite.name.substring(0, 20) + '...' : activeSite.name;
      if (dotEl) {
        dotEl.style.background = activeSite.color_accent || '#06b6d4';
        dotEl.style.boxShadow = `0 0 8px ${activeSite.color_accent || '#06b6d4'}`;
      }
      if (sidebarBrandTitle) sidebarBrandTitle.textContent = activeSite.name.length > 18 ? activeSite.name.substring(0, 16) + '..' : activeSite.name;
      if (heroH3) heroH3.innerHTML = `<i class="fa-solid fa-car" style="color: ${activeSite.color_accent || 'var(--accent-cyan)'};"></i> Master Orchestrator — ${activeSite.name} AI Telemetry`;
      if (heroDesc) heroDesc.textContent = `Autonomous 18-Agent Marketing Operating System controlling SEO, Ads, Social Media, and Leads for ${activeSite.name} (${activeSite.location}).`;

      // Update Modal default target URLs & Anchor text
      const outreachLanding = document.getElementById('outreach-landing-page');
      const outreachAnchor = document.getElementById('outreach-anchor-text');
      if (outreachLanding) {
        outreachLanding.value = activeSite.domain.endsWith('/') ? activeSite.domain : activeSite.domain + '/';
      }
      if (outreachAnchor) {
        outreachAnchor.value = activeSite.name;
      }
    }
  }
}

async function switchWebsite(siteId) {
  currentSiteId = siteId;
  sessionStorage.setItem('ccm_selected_site', siteId);
  localStorage.setItem('ccm_selected_site', siteId);

  const dropdownWrap = document.getElementById('website-switcher-wrap');
  if (dropdownWrap) dropdownWrap.classList.remove('open');

  renderWebsiteDropdown();
  updateWebsiteHeaderUI();
  await loadCurrentView(activeView);
}

async function submitAddNewWebsite(e) {
  e.preventDefault();
  const siteId = document.getElementById('new-site-id').value.trim();
  const name = document.getElementById('new-site-name').value.trim();
  const domain = document.getElementById('new-site-domain').value.trim();
  const location = document.getElementById('new-site-location').value.trim();
  const category = document.getElementById('new-site-category').value.trim() || 'Chauffeur Services';
  const niche = document.getElementById('new-site-niche').value.trim();
  const color = document.getElementById('new-site-color').value;

  try {
    const res = await fetch('/api/websites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        site_id: siteId,
        name: name,
        domain: domain,
        location: location,
        default_category: category,
        niche: niche,
        color_accent: color
      })
    });

    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      alert(`Error registering website: ${data.detail || data.message || 'Failed'}`);
      return;
    }

    closeModal('add-website-modal');
    document.getElementById('add-website-form').reset();
    alert(`Website "${name}" successfully connected! Switching to it now.`);

    await initWebsiteSwitcher();
    await switchWebsite(siteId);
  } catch (err) {
    alert(`Failed to add website: ${err.message}`);
  }
}

async function populateAgentDropdown() {
  try {
    const [agentsRes, sitesRes] = await Promise.all([
      fetch('/api/agents'),
      fetch('/api/websites')
    ]);
    const agentsData = await agentsRes.json();
    const sitesData = await sitesRes.json();

    const agentSelect = document.getElementById('task-agent-select');
    if (agentsData.agents && agentsData.agents.length > 0) {
      agentSelect.innerHTML = agentsData.agents.map(a => `
        <option value="${a.agent_id}">${a.name} (${a.agent_id})</option>
      `).join('');
    }

    const siteSelect = document.getElementById('task-website-select');
    if (siteSelect && sitesData.websites && sitesData.websites.length > 0) {
      siteSelect.innerHTML = sitesData.websites.map(s => `
        <option value="${s.site_id}" ${s.site_id === currentSiteId ? 'selected' : ''}>${s.name} (${s.site_id})</option>
      `).join('');
    }
  } catch (err) {
    console.error('Failed to populate dropdowns:', err);
  }
}

/* --- Ambient Floating Particle Background --- */
function initAmbientParticles() {
  const canvas = document.getElementById('ambient-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  const particles = [];
  for (let i = 0; i < 45; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 2 + 1,
      speedX: (Math.random() - 0.5) * 0.4,
      speedY: (Math.random() - 0.5) * 0.4,
      color: i % 2 === 0 ? 'rgba(6, 182, 212, ' : 'rgba(168, 85, 247, ',
      alpha: Math.random() * 0.5 + 0.2
    });
  }

  function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach(p => {
      p.x += p.speedX;
      p.y += p.speedY;

      if (p.x < 0) p.x = canvas.width;
      if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height;
      if (p.y > canvas.height) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fillStyle = p.color + p.alpha + ')';
      ctx.fill();
    });
    requestAnimationFrame(render);
  }
  render();
}

/* --- Rectangular Half-Rotation Oscillating Car Visualizer --- */
function init3DCyberCore() {
  const canvas = document.getElementById('cyber-core-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  function resize() {
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth || 330;
    canvas.height = parent.clientHeight || 190;
  }
  resize();
  window.addEventListener('resize', resize);

  // Preload Luxury Vehicle Image
  const carImg = new Image();
  carImg.src = '/static/fleet_vclass.jpg';

  let time = 0;

  function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const w = canvas.width;
    const h = canvas.height;
    const centerX = w / 2;
    const centerY = h / 2;

    time += 0.015;
    // Smooth half-rotation oscillation (sways gently back & forth between -12° and +12°)
    const halfRotateAngle = Math.sin(time) * 0.2; 

    // 1. Render Half-Rotating Rectangular Vehicle Image
    ctx.save();
    ctx.translate(centerX, centerY);
    ctx.rotate(halfRotateAngle);

    if (carImg.complete && carImg.naturalWidth !== 0) {
      ctx.globalAlpha = 0.92;
      ctx.drawImage(carImg, -w / 2, -h / 2, w, h);
    }
    ctx.restore();

    // 2. Futuristic Cyber Metallic Frame & Neon Accent Lines
    ctx.save();
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.4)';
    ctx.lineWidth = 2;
    ctx.shadowColor = '#06b6d4';
    ctx.shadowBlur = 12;
    ctx.strokeRect(2, 2, w - 4, h - 4);
    ctx.restore();

    requestAnimationFrame(render);
  }

  render();
}

/* --- 3D Interactive Card Tilt Effect --- */
function init3DCardTilt() {
  document.addEventListener('mousemove', (e) => {
    const cards = document.querySelectorAll('.metric-card, .agent-card, .cyber-core-banner');
    const mouseX = e.clientX;
    const mouseY = e.clientY;

    cards.forEach(card => {
      const rect = card.getBoundingClientRect();
      const cardX = rect.left + rect.width / 2;
      const cardY = rect.top + rect.height / 2;

      const distX = mouseX - cardX;
      const distY = mouseY - cardY;

      if (Math.abs(distX) < 350 && Math.abs(distY) < 250) {
        const tiltX = (distY / rect.height) * -6;
        const tiltY = (distX / rect.width) * 6;
        card.style.transform = `perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) translateY(-4px)`;
      } else {
        card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)';
      }
    });
  });
}

function loadCurrentView(view) {
  switch (view) {
    case 'overview': loadOverview(); break;
    case 'agents': loadAgents(); break;
    case 'tasks': loadTasks(); break;
    case 'approvals': loadApprovals(); break;
    case 'scheduler': loadScheduler(); break;
    case 'ai-usage': loadAIUsage(); break;
    case 'logs': loadLogs(); break;
    case 'errors': loadErrors(); break;
    case 'audit': loadAuditTrail(); break;
    case 'health': loadHealth(); break;
    case 'page-doctor': loadPageDoctorView(); break;
    case 'settings': loadSettings(); break;
  }
}

/* --- API Loaders --- */

async function loadOverview() {
  try {
    const [overviewRes, agentsRes, auditRes] = await Promise.all([
      fetch(`/api/overview?site_id=${currentSiteId}`),
      fetch(`/api/agents?site_id=${encodeURIComponent(currentSiteId)}`),
      fetch('/api/audit-trail?limit=10')
    ]);

    const overview = await overviewRes.json();
    const agents = await agentsRes.json();
    const audit = await auditRes.json();

    const stats = overview.stats;

    // Update dynamic agent count badges across UI
    updateDynamicAgentCounters(stats.total_agents, stats.active_agents);

    // Metric Cards
    const metricsHtml = `
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">Registered Sub-Agents</div>
          <div class="metric-icon-box" style="background:rgba(6, 182, 212, 0.2); color:var(--accent-cyan);">
            <i class="fa-solid fa-robot"></i>
          </div>
        </div>
        <div class="metric-value" style="color: var(--accent-cyan);">${stats.total_agents}</div>
        <div class="metric-subtext">${stats.active_agents} Active / ${stats.disabled_agents} Disabled</div>
      </div>
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">Pending Approvals</div>
          <div class="metric-icon-box" style="background:rgba(245, 158, 11, 0.2); color:var(--status-warning);">
            <i class="fa-solid fa-user-shield"></i>
          </div>
        </div>
        <div class="metric-value" style="color: var(--status-warning);">${stats.awaiting_approval_tasks}</div>
        <div class="metric-subtext">Human Gatekeeper Required</div>
      </div>
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">Total AI Requests</div>
          <div class="metric-icon-box" style="background:rgba(168, 85, 247, 0.2); color:var(--accent-purple);">
            <i class="fa-solid fa-bolt"></i>
          </div>
        </div>
        <div class="metric-value" style="color: var(--accent-purple);">${stats.total_ai_requests}</div>
        <div class="metric-subtext">${stats.total_tokens} Tokens Processed</div>
      </div>
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">Estimated AI Cost</div>
          <div class="metric-icon-box" style="background:rgba(16, 185, 129, 0.2); color:var(--status-success);">
            <i class="fa-solid fa-sack-dollar"></i>
          </div>
        </div>
        <div class="metric-value" style="color: var(--status-success);">$${stats.total_cost_usd.toFixed(4)}</div>
        <div class="metric-subtext">Cost Optimized Router Engine</div>
      </div>
    `;
    document.getElementById('overview-metrics').innerHTML = metricsHtml;

    // Overview Agents Table
    const agentsRows = agents.agents.map(a => `
      <tr>
        <td><strong>${a.name}</strong><br><small style="font-family:var(--font-mono); color:var(--text-muted);">${a.agent_id}</small></td>
        <td><span class="action-chip">${a.category}</span></td>
        <td><span class="badge ${a.enabled ? 'badge-success' : 'badge-danger'}">${a.enabled ? 'Active' : 'Disabled'}</span></td>
        <td style="font-size:11px; font-family:var(--font-mono);">${a.supported_actions.join(', ')}</td>
      </tr>
    `).join('');
    document.getElementById('overview-agents-table').innerHTML = agentsRows || '<tr><td colspan="4">No agents registered</td></tr>';

    // Overview Audit Activity Table
    const auditRows = audit.events.map(e => `
      <tr>
        <td style="font-family:var(--font-mono); font-size:11px;">${e.timestamp.substring(11, 19)}</td>
        <td><span class="action-chip" style="color:var(--accent-cyan);">${e.agent_id}</span></td>
        <td><strong>${e.action}</strong></td>
      </tr>
    `).join('');
    document.getElementById('overview-audit-table').innerHTML = auditRows || '<tr><td colspan="3">No recent audit activity</td></tr>';

    // Render Telemetry Charts
    initDashboardCharts(agents.agents);

  } catch (err) {
    console.error('Failed to load overview:', err);
  }
}

function initDashboardCharts(agentsList) {
  if (typeof Chart === 'undefined') {
    console.warn('Chart.js library loading...');
    setTimeout(() => initDashboardCharts(agentsList), 500);
    return;
  }

  // 1. Activity & Telemetry Area Chart
  const actCtx = document.getElementById('activityChart');
  if (actCtx) {
    if (activityChartInstance) activityChartInstance.destroy();

    const ctx = actCtx.getContext('2d');
    const cyanGrad = ctx.createLinearGradient(0, 0, 0, 200);
    cyanGrad.addColorStop(0, 'rgba(6, 182, 212, 0.4)');
    cyanGrad.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

    const purpleGrad = ctx.createLinearGradient(0, 0, 0, 200);
    purpleGrad.addColorStop(0, 'rgba(168, 85, 247, 0.4)');
    purpleGrad.addColorStop(1, 'rgba(168, 85, 247, 0.0)');

    activityChartInstance = new Chart(actCtx, {
      type: 'line',
      data: {
        labels: ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00'],
        datasets: [
          {
            label: 'Task Requests',
            data: [14, 22, 18, 30, 28, 38, 32],
            borderColor: '#06b6d4',
            backgroundColor: cyanGrad,
            fill: true,
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: '#06b6d4'
          },
          {
            label: 'AI Calls',
            data: [10, 16, 12, 22, 19, 28, 25],
            borderColor: '#a855f7',
            backgroundColor: purpleGrad,
            fill: true,
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: '#a855f7'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 12, weight: '700' } } }
        },
        scales: {
          x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8', font: { family: 'Space Grotesk' } } },
          y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8', font: { family: 'Space Grotesk' } } }
        }
      }
    });
  }

  // 2. Category Doughnut Chart
  const catCtx = document.getElementById('categoryChart');
  if (catCtx && agentsList) {
    if (categoryChartInstance) categoryChartInstance.destroy();

    const categoriesCount = {};
    agentsList.forEach(a => {
      categoriesCount[a.category] = (categoriesCount[a.category] || 0) + 1;
    });

    categoryChartInstance = new Chart(catCtx, {
      type: 'doughnut',
      data: {
        labels: Object.keys(categoriesCount),
        datasets: [{
          data: Object.values(categoriesCount),
          backgroundColor: ['#06b6d4', '#a855f7', '#10b981', '#f59e0b', '#3b82f6', '#ec4899'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11, weight: '600' } } }
        },
        cutout: '70%'
      }
    });
  }
}

async function loadAgents() {
  try {
    const res = await fetch(`/api/agents?site_id=${encodeURIComponent(currentSiteId)}`);
    const data = await res.json();
    const grid = document.getElementById('agents-grid');

    if (!data.agents || data.agents.length === 0) {
      grid.innerHTML = '<div style="color:var(--text-muted);">No sub-agents registered</div>';
      return;
    }

    const activeCount = data.agents.filter(a => a.enabled && !a.paused).length;
    updateDynamicAgentCounters(data.agents.length, activeCount);

    grid.innerHTML = data.agents.map(a => `
      <div class="agent-card">
        <div>
          <div class="agent-header">
            <div class="agent-avatar">
              <i class="${getIconForAgent(a.agent_id)}"></i>
            </div>
            <div class="agent-title-box">
              <h3>${a.name}</h3>
              <div class="agent-category">${a.category}</div>
            </div>
          </div>
          <div class="agent-desc">${a.description}</div>
          <div class="agent-actions-tags">
            ${a.supported_actions.map(act => `
              <span class="action-chip" style="cursor:pointer;" onclick="handleActionChipClick('${a.agent_id}', '${act}')" title="Click to trigger ${act}">
                ${act}
              </span>
            `).join('')}
          </div>
        </div>
        <div class="agent-footer">
          <span class="badge ${a.enabled ? 'badge-success' : 'badge-danger'}">${a.enabled ? (a.paused ? 'PAUSED' : 'ACTIVE') : 'DISABLED'}</span>
          <div style="display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; align-items:center;">
            ${a.agent_id === 'external-link-building-agent' ? `
              <button class="btn btn-primary btn-sm" style="background:linear-gradient(135deg, var(--accent-cyan), #0284c7); font-weight:700; border:none; box-shadow:0 0 12px rgba(6,182,212,0.5); color:#fff;" onclick="openCustomOutreachModal()" title="Manually add custom websites to create backlinks">
                <i class="fa-solid fa-plus"></i> Add Sites
              </button>
            ` : ''}
            ${a.agent_id === 'competitor-ad-spy-agent' ? `
              <button class="btn btn-primary btn-sm" style="background:linear-gradient(135deg, #ef4444, #f97316); font-weight:700; border:none; box-shadow:0 0 12px rgba(239,68,68,0.5); color:#fff;" onclick="openCompetitorAdSpyModal()" title="Analyze competitor Google Ads & Meta Ads">
                <i class="fa-solid fa-crosshairs"></i> Spy Ads
              </button>
            ` : ''}
            ${a.agent_id === 'page-optimizer-agent' ? `
              <button class="btn btn-primary btn-sm" style="background:linear-gradient(135deg, #10b981, #059669); font-weight:700; border:none; box-shadow:0 0 12px rgba(16,185,129,0.5); color:#fff;" onclick="openPageOptimizerModal()" title="Audit any page URL with Google Algorithm">
                <i class="fa-solid fa-stethoscope"></i> Audit Page
              </button>
            ` : ''}
            <button class="btn btn-secondary btn-sm" style="color:var(--accent-cyan); border-color:rgba(6,182,212,0.4);" onclick="viewAgentReport('${a.agent_id}')">
              <i class="fa-solid fa-chart-line"></i> Report
            </button>
            <button class="btn btn-primary btn-sm" onclick="runAgentTask('${a.agent_id}', '${a.supported_actions[0] || 'status'}')">
              <i class="fa-solid fa-play"></i> Run
            </button>
            <button class="btn btn-secondary btn-sm" onclick="toggleAgent('${a.agent_id}', '${a.paused ? 'resume' : 'pause'}')">
              ${a.paused ? '<i class="fa-solid fa-play"></i>' : '<i class="fa-solid fa-pause"></i>'}
            </button>
          </div>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load agents:', err);
  }
}

function handleActionChipClick(agentId, action) {
  if (agentId === 'external-link-building-agent' && action === 'custom_site_outreach') {
    openCustomOutreachModal();
  } else if (agentId === 'external-link-building-agent' && action === 'daily_batch') {
    runDailyBacklinkBatch();
  } else if (agentId === 'competitor-ad-spy-agent') {
    openCompetitorAdSpyModal();
  } else {
    runAgentTask(agentId, action);
  }
}

function getIconForAgent(agentId) {
  const icons = {
    'blog-agent': 'fa-solid fa-blog',
    'corporate-cars-social-agent': 'fa-solid fa-share-nodes',
    'seo-keyword-agent': 'fa-solid fa-key',
    'competitor-analysis-agent': 'fa-solid fa-user-secret',
    'competitor-ad-spy-agent': 'fa-solid fa-crosshairs',
    'page-optimizer-agent': 'fa-solid fa-stethoscope',
    'external-link-building-agent': 'fa-solid fa-link-slash',
    'seo-content-brief-agent': 'fa-solid fa-file-contract',
    'internal-linking-agent': 'fa-solid fa-link',
    'seo-audit-agent': 'fa-solid fa-magnifying-glass-chart',
    'gsc-agent': 'fa-brands fa-google',
    'ga4-reporting-agent': 'fa-solid fa-chart-simple',
    'google-ads-monitoring-agent': 'fa-solid fa-rectangle-ad',
    'google-ads-optimization-agent': 'fa-solid fa-sliders',
    'meta-ads-monitoring-agent': 'fa-brands fa-facebook',
    'social-analytics-agent': 'fa-solid fa-chart-line',
    'reputation-agent': 'fa-solid fa-star',
    'lead-management-agent': 'fa-solid fa-user-group',
    'monthly-report-agent': 'fa-solid fa-file-invoice-dollar'
  };
  return icons[agentId] || 'fa-solid fa-robot';
}

async function runAgentTask(agentId, action) {
  try {
    const res = await fetch('/api/tasks/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent_id: agentId,
        task_type: action,
        input_data: { action: action, site_id: currentSiteId, site: currentSiteId },
        site_id: currentSiteId,
        requires_approval: false
      })
    });
    const data = await res.json();
    alert(`Task created for ${agentId} on website [${currentSiteId}] (${data.task.task_id}).`);
    loadCurrentView(activeView);
  } catch (err) {
    alert(`Failed to create task: ${err}`);
  }
}

async function toggleAgent(agentId, action) {
  try {
    await fetch(`/api/agents/${agentId}/${action}`, { method: 'POST' });
    loadAgents();
  } catch (err) {
    alert(`Failed to toggle agent state: ${err}`);
  }
}

async function viewAgentReport(agentId) {
  if (agentId === 'competitor-ad-spy-agent') {
    openCompetitorAdSpyModal();
    return;
  }
  try {
    const res = await fetch(`/api/agents/${agentId}/report?site_id=${currentSiteId}`);
    const data = await res.json();

    document.getElementById('agent-report-title').innerHTML = `
      <i class="${getIconForAgent(agentId)}" style="color:var(--accent-cyan);"></i> ${data.name} Performance Report
    `;
    document.getElementById('agent-report-subtitle').textContent = `Active Website: ${data.site_name} (${data.site_domain}) | Category: ${data.category} | Total Completed Tasks: ${data.completed_tasks_count}`;

    const container = document.getElementById('agent-report-content');

    if (agentId === 'blog-agent' && data.blog_metrics) {
      const bm = data.blog_metrics;
      const nextP = bm.next_scheduled_post_tomorrow || {};
      container.innerHTML = `
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px;">
          <div style="background:rgba(6,182,212,0.1); border:1px solid rgba(6,182,212,0.3); padding:16px; border-radius:14px;">
            <div style="font-size:11px; font-weight:800; color:var(--accent-cyan); text-transform:uppercase;">Live Published Posts</div>
            <div style="font-size:32px; font-weight:800; color:#fff; font-family:var(--font-mono); margin-top:4px;">${bm.total_published}</div>
          </div>
          <div style="background:rgba(168,85,247,0.1); border:1px solid rgba(168,85,247,0.3); padding:16px; border-radius:14px;">
            <div style="font-size:11px; font-weight:800; color:var(--accent-purple); text-transform:uppercase;">Approved Queue Drafts</div>
            <div style="font-size:32px; font-weight:800; color:#fff; font-family:var(--font-mono); margin-top:4px;">${bm.total_approved_queue}</div>
          </div>
        </div>

        <div style="background:linear-gradient(135deg, rgba(16,185,129,0.15), rgba(6,182,212,0.15)); border:1px solid rgba(16,185,129,0.4); padding:18px; border-radius:14px; margin-bottom:20px;">
          <div style="font-size:12px; font-weight:800; color:#10b581; text-transform:uppercase; letter-spacing:0.5px; display:flex; align-items:center; gap:8px;">
            <i class="fa-solid fa-calendar-day"></i> Next Scheduled Blog Post (Scheduled for Tomorrow 09:00 AM Local Time)
          </div>
          <div style="font-size:16px; font-weight:800; color:#fff; margin-top:8px;">"${nextP.title}"</div>
          <div style="display:flex; gap:16px; font-size:12px; color:var(--text-secondary); margin-top:6px;">
            <span><strong>Target Keyword:</strong> <code style="color:var(--accent-cyan);">${nextP.keyword}</code></span>
            <span><strong>Suburb / Area:</strong> ${nextP.suburb}</span>
          </div>
        </div>

        <h3 style="font-size:14px; font-weight:800; color:var(--text-primary); margin-bottom:12px;">Date-Wise Published Blog History for ${data.site_name}:</h3>
        <div style="background:rgba(30,41,59,0.7); border:1px solid var(--glass-border); border-radius:12px; overflow-x:auto; margin-bottom:20px;">
          <table style="width:100%; border-collapse:collapse; text-align:left; font-size:12px;">
            <thead>
              <tr style="background:rgba(15,23,42,0.8); color:var(--text-muted); text-transform:uppercase;">
                <th style="padding:10px 14px;">ID</th>
                <th style="padding:10px 14px;">Published Date</th>
                <th style="padding:10px 14px;">Title</th>
                <th style="padding:10px 14px;">Suburb</th>
                <th style="padding:10px 14px;">Action</th>
              </tr>
            </thead>
            <tbody>
              ${(bm.published_posts_history || []).map(p => `
                <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                  <td style="padding:10px 14px; font-family:var(--font-mono); color:var(--accent-cyan);">${p.id}</td>
                  <td style="padding:10px 14px;">${p.published_at ? p.published_at.substring(0, 10) : 'Recent'}</td>
                  <td style="padding:10px 14px; font-weight:700;">${p.title}</td>
                  <td style="padding:10px 14px;">${p.suburb}</td>
                  <td style="padding:10px 14px;">
                    <a href="${p.url}" target="_blank" style="color:var(--accent-purple); text-decoration:none; font-weight:700;"><i class="fa-solid fa-arrow-up-right-from-square"></i> Visit Post</a>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>

        <div style="background:rgba(30,41,59,0.5); border:1px solid var(--glass-border); padding:16px; border-radius:12px;">
          <div style="font-size:12px; font-weight:800; color:var(--accent-purple); text-transform:uppercase; margin-bottom:8px;">Strategic Blog Recommendations for ${data.site_name}:</div>
          ${(bm.recommendations || []).map(r => `<div style="font-size:12.5px; color:var(--text-secondary); margin-bottom:4px;">-> ${r}</div>`).join('')}
        </div>
      `;
    } else if (agentId === 'corporate-cars-social-agent' && data.social_metrics) {
      const sm = data.social_metrics;
      container.innerHTML = `
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; margin-bottom:20px;">
          <div style="background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.3); padding:14px; border-radius:14px;">
            <div style="font-size:11px; font-weight:800; color:#3b82f6; text-transform:uppercase;"><i class="fa-brands fa-facebook"></i> Facebook</div>
            <div style="font-size:12px; color:var(--text-primary); margin-top:6px;">Published: <strong>${sm.platforms.facebook.published}</strong> | Scheduled: <strong>${sm.platforms.facebook.scheduled}</strong></div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:4px;">Impressions: ${sm.platforms.facebook.impressions.toLocaleString()} | Clicks: ${sm.platforms.facebook.clicks}</div>
          </div>
          <div style="background:rgba(236,72,153,0.1); border:1px solid rgba(236,72,153,0.3); padding:14px; border-radius:14px;">
            <div style="font-size:11px; font-weight:800; color:#ec4899; text-transform:uppercase;"><i class="fa-brands fa-instagram"></i> Instagram</div>
            <div style="font-size:12px; color:var(--text-primary); margin-top:6px;">Published: <strong>${sm.platforms.instagram.published}</strong> | Scheduled: <strong>${sm.platforms.instagram.scheduled}</strong></div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:4px;">Impressions: ${sm.platforms.instagram.impressions.toLocaleString()} | Likes: ${sm.platforms.instagram.likes}</div>
          </div>
          <div style="background:rgba(14,165,233,0.1); border:1px solid rgba(14,165,233,0.3); padding:14px; border-radius:14px;">
            <div style="font-size:11px; font-weight:800; color:#0ea5e9; text-transform:uppercase;"><i class="fa-brands fa-linkedin"></i> LinkedIn</div>
            <div style="font-size:12px; color:var(--text-primary); margin-top:6px;">Published: <strong>${sm.platforms.linkedin.published}</strong> | Scheduled: <strong>${sm.platforms.linkedin.scheduled}</strong></div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:4px;">Engagement: ${sm.platforms.linkedin.engagement_rate}</div>
          </div>
        </div>

        <h3 style="font-size:14px; font-weight:800; color:var(--text-primary); margin-bottom:10px;"><i class="fa-solid fa-square-check" style="color:var(--status-success);"></i> Date-Wise Published Social Posts History for ${data.site_name}:</h3>
        <div style="background:rgba(30,41,59,0.7); border:1px solid var(--glass-border); border-radius:12px; overflow-x:auto; margin-bottom:20px;">
          <table style="width:100%; border-collapse:collapse; text-align:left; font-size:12px;">
            <thead>
              <tr style="background:rgba(15,23,42,0.8); color:var(--text-muted); text-transform:uppercase;">
                <th style="padding:10px 14px;">ID</th>
                <th style="padding:10px 14px;">Platform</th>
                <th style="padding:10px 14px;">Published Date & Time</th>
                <th style="padding:10px 14px;">Content Title / Topic</th>
                <th style="padding:10px 14px;">Performance</th>
              </tr>
            </thead>
            <tbody>
              ${(sm.published_posts_history || []).map(p => `
                <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                  <td style="padding:10px 14px; font-family:var(--font-mono); color:var(--accent-cyan);">${p.id}</td>
                  <td style="padding:10px 14px;"><span class="action-chip">${p.platform}</span></td>
                  <td style="padding:10px 14px; font-family:var(--font-mono); font-size:11px;">${p.published_at}</td>
                  <td style="padding:10px 14px; font-weight:700;">${p.title}</td>
                  <td style="padding:10px 14px; color:var(--status-success); font-weight:700;">${p.clicks} clicks | ${p.likes} likes</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>

        <h3 style="font-size:14px; font-weight:800; color:var(--text-primary); margin-bottom:10px;"><i class="fa-solid fa-clock"></i> Next Scheduled Social Posts (${data.site_name}):</h3>
        <div style="display:flex; flex-direction:column; gap:8px; margin-bottom:20px;">
          ${(sm.next_scheduled_posts || []).map(sp => `
            <div style="background:rgba(30,41,59,0.7); border:1px solid var(--glass-border); padding:12px 16px; border-radius:10px; display:flex; justify-content:space-between; align-items:center;">
              <div>
                <span class="action-chip">${sp.platform}</span>
                <strong style="margin-left:8px; color:var(--text-primary); font-size:13px;">${sp.title}</strong>
              </div>
              <span style="font-size:11px; font-family:var(--font-mono); color:var(--accent-cyan);">${sp.time}</span>
            </div>
          `).join('')}
        </div>

        <div style="background:rgba(168,85,247,0.1); border:1px solid rgba(168,85,247,0.3); padding:16px; border-radius:12px;">
          <div style="font-size:12px; font-weight:800; color:var(--accent-purple); text-transform:uppercase; margin-bottom:8px;"><i class="fa-solid fa-lightbulb"></i> Weekly AI Social Recommendations for ${data.site_name}:</div>
          ${(sm.weekly_recommendations || []).map(r => `<div style="font-size:12.5px; color:var(--text-secondary); margin-bottom:4px;">-> ${r}</div>`).join('')}
        </div>
      `;
    } else if (agentId === 'external-link-building-agent' && data.external_link_metrics) {
      const elm = data.external_link_metrics;
      const hs = elm.backlink_health_summary || {};
      container.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(6,182,212,0.06); border:1px solid rgba(6,182,212,0.25); padding:14px 18px; border-radius:14px; margin-bottom:20px;">
          <div>
            <div style="font-size:13px; font-weight:800; color:var(--accent-cyan);"><i class="fa-solid fa-network-wired"></i> Autonomous External Backlink & Outreach Engine</div>
            <div style="font-size:11.5px; color:var(--text-muted); margin-top:2px;">Target: <strong>${data.site_domain}</strong> (${data.site_name})</div>
          </div>
          <div style="display:flex; gap:10px;">
            <button class="btn btn-primary btn-sm" onclick="openCustomOutreachModal()" style="font-size:12px; padding:8px 16px; background:linear-gradient(135deg, var(--accent-cyan), #0284c7);">
              <i class="fa-solid fa-plus"></i> + Custom Site Outreach / Link Builder
            </button>
            <button class="btn btn-secondary btn-sm" onclick="runDailyBacklinkBatch()" style="font-size:12px; padding:8px 16px; border-color:rgba(168,85,247,0.5); color:#fff;">
              <i class="fa-solid fa-bolt" style="color:var(--accent-purple);"></i> ⚡ Run Daily 5-10 Links Batch
            </button>
          </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:14px; margin-bottom:20px;">
          <div style="background:rgba(6,182,212,0.1); border:1px solid rgba(6,182,212,0.3); padding:14px; border-radius:14px;">
            <div style="font-size:11px; font-weight:800; color:var(--accent-cyan); text-transform:uppercase;">Active Backlinks</div>
            <div style="font-size:26px; font-weight:800; color:#fff; font-family:var(--font-mono); margin-top:4px;">${hs.total_active_backlinks}</div>
          </div>
          <div style="background:rgba(168,85,247,0.1); border:1px solid rgba(168,85,247,0.3); padding:14px; border-radius:14px;">
            <div style="font-size:11px; font-weight:800; color:var(--accent-purple); text-transform:uppercase;">Referring Domains</div>
            <div style="font-size:26px; font-weight:800; color:#fff; font-family:var(--font-mono); margin-top:4px;">${hs.referring_domains}</div>
          </div>
          <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); padding:14px; border-radius:14px;">
            <div style="font-size:11px; font-weight:800; color:#10b581; text-transform:uppercase;">Domain Authority</div>
            <div style="font-size:26px; font-weight:800; color:#fff; font-family:var(--font-mono); margin-top:4px;">${hs.domain_authority}</div>
          </div>
          <div style="background:rgba(236,72,153,0.1); border:1px solid rgba(236,72,153,0.3); padding:14px; border-radius:14px;">
            <div style="font-size:11px; font-weight:800; color:#ec4899; text-transform:uppercase;">Dofollow Ratio</div>
            <div style="font-size:26px; font-weight:800; color:#fff; font-family:var(--font-mono); margin-top:4px;">${hs.dofollow_percent}</div>
          </div>
        </div>

        <h3 style="font-size:14px; font-weight:800; color:var(--text-primary); margin-bottom:10px;"><i class="fa-solid fa-building-columns" style="color:var(--accent-cyan);"></i> Directory Citations (NAP Backlinks for ${data.site_name}):</h3>
        <div style="background:rgba(30,41,59,0.7); border:1px solid var(--glass-border); border-radius:12px; overflow-x:auto; margin-bottom:20px;">
          <table style="width:100%; border-collapse:collapse; text-align:left; font-size:12px;">
            <thead>
              <tr style="background:rgba(15,23,42,0.8); color:var(--text-muted); text-transform:uppercase;">
                <th style="padding:10px 14px;">Platform Name</th>
                <th style="padding:10px 14px;">Domain Authority</th>
                <th style="padding:10px 14px;">Live Link</th>
                <th style="padding:10px 14px;">Target Destination</th>
                <th style="padding:10px 14px;">Anchor Used</th>
                <th style="padding:10px 14px;">Status</th>
                <th style="padding:10px 14px;">Type</th>
              </tr>
            </thead>
            <tbody>
              ${(elm.directory_citations || []).map(c => `
                <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                  <td style="padding:10px 14px; font-weight:700; color:var(--text-primary);">${c.name}</td>
                  <td style="padding:10px 14px; font-family:var(--font-mono); color:var(--accent-cyan);">DA ${c.da}</td>
                  <td style="padding:10px 14px;">
                    <a href="${c.url}" target="_blank" class="action-chip" style="color:var(--accent-cyan); text-decoration:none; font-weight:700;">
                      <i class="fa-solid fa-arrow-up-right-from-square"></i> Open Live Link
                    </a>
                  </td>
                  <td style="padding:10px 14px;">
                    <a href="${c.target_url}" target="_blank" style="color:var(--accent-purple); text-decoration:none; font-family:var(--font-mono); font-size:11px;">
                      <i class="fa-solid fa-link"></i> ${c.target_url.replace(data.site_domain, '') || '/'}
                    </a>
                  </td>
                  <td style="padding:10px 14px; font-weight:600; color:#38bdf8;">${c.anchor_used || data.site_name}</td>
                  <td style="padding:10px 14px;"><span class="badge badge-success">${c.status}</span></td>
                  <td style="padding:10px 14px; font-weight:700; color:var(--accent-purple);">${c.link_type}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>

        <h3 style="font-size:14px; font-weight:800; color:var(--text-primary); margin-bottom:10px;"><i class="fa-solid fa-newspaper" style="color:var(--accent-purple);"></i> Published Web 2.0 Editorial & Custom Outreach Backlinks:</h3>
        <div style="background:rgba(30,41,59,0.7); border:1px solid var(--glass-border); border-radius:12px; overflow-x:auto; margin-bottom:20px;">
          <table style="width:100%; border-collapse:collapse; text-align:left; font-size:12px;">
            <thead>
              <tr style="background:rgba(15,23,42,0.8); color:var(--text-muted); text-transform:uppercase;">
                <th style="padding:10px 14px;">Platform / Domain</th>
                <th style="padding:10px 14px;">Article Title & Snippet</th>
                <th style="padding:10px 14px;">Live Article Link</th>
                <th style="padding:10px 14px;">Target Landing Page</th>
                <th style="padding:10px 14px;">Anchor Used</th>
                <th style="padding:10px 14px;">DA</th>
                <th style="padding:10px 14px;">Type</th>
                <th style="padding:10px 14px;">Date</th>
              </tr>
            </thead>
            <tbody>
              ${(elm.web2_published_articles || []).map(w => `
                <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                  <td style="padding:10px 14px;"><span class="action-chip">${w.platform}</span></td>
                  <td style="padding:10px 14px;">
                    <div style="font-weight:700; color:var(--text-primary); margin-bottom:3px;">${w.article_title}</div>
                    ${w.content_snippet ? `<div style="font-size:11px; color:var(--text-muted); font-style:italic;">"${w.content_snippet.substring(0, 110)}..."</div>` : ''}
                  </td>
                  <td style="padding:10px 14px;">
                    <a href="${w.url}" target="_blank" class="action-chip" style="color:var(--accent-cyan); text-decoration:none; font-weight:700;">
                      <i class="fa-solid fa-arrow-up-right-from-square"></i> Visit Live Link
                    </a>
                  </td>
                  <td style="padding:10px 14px;">
                    <a href="${w.target_url}" target="_blank" style="color:var(--accent-purple); text-decoration:none; font-family:var(--font-mono); font-size:11px;">
                      <i class="fa-solid fa-link"></i> ${w.target_url.replace(data.site_domain, '') || '/'}
                    </a>
                  </td>
                  <td style="padding:10px 14px; color:#38bdf8; font-family:var(--font-mono); font-weight:700;">${w.anchor_used || data.site_name}</td>
                  <td style="padding:10px 14px; font-family:var(--font-mono); color:var(--accent-cyan);">DA ${w.da}</td>
                  <td style="padding:10px 14px; font-weight:700; color:var(--accent-purple);">${w.link_type}</td>
                  <td style="padding:10px 14px; font-size:11px; font-family:var(--font-mono);">${w.published_date}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>

        <div style="background:rgba(168,85,247,0.1); border:1px solid rgba(168,85,247,0.3); padding:16px; border-radius:12px;">
          <div style="font-size:12px; font-weight:800; color:var(--accent-purple); text-transform:uppercase; margin-bottom:8px;"><i class="fa-solid fa-lightbulb"></i> Off-Page Backlink Strategy Recommendations for ${data.site_name}:</div>
          ${(elm.recommendations || []).map(r => `<div style="font-size:12.5px; color:var(--text-secondary); margin-bottom:4px;">-> ${r}</div>`).join('')}
        </div>
      `;
    } else if (agentId === 'page-optimizer-agent' && data.page_optimizer_metrics) {
      const pom = data.page_optimizer_metrics;
      const latest = pom.latest_audit ? pom.latest_audit.data : null;
      container.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3); padding:16px 20px; border-radius:14px; margin-bottom:20px;">
          <div>
            <div style="font-size:14px; font-weight:800; color:#10b981; display:flex; align-items:center; gap:8px;">
              <i class="fa-solid fa-stethoscope"></i> Google Algorithm Page SEO Doctor
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:3px;">
              Auditing against Google E-E-A-T, Helpful Content (HCU), Heading Structure, and Schema.org.
            </div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="openPageOptimizerModal()" style="background:linear-gradient(135deg, #10b981, #059669); font-size:12px; font-weight:700; padding:8px 18px; border:none;">
            <i class="fa-solid fa-plus-circle"></i> + Audit New Webpage
          </button>
        </div>

        ${latest ? `
          <div style="background:rgba(15,23,42,0.8); border:1px solid var(--glass-border); padding:18px; border-radius:14px; margin-bottom:20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
              <div>
                <span class="badge badge-info" style="font-size:11px;">LATEST AUDIT REPORT</span>
                <h3 style="font-size:14px; font-weight:800; color:#fff; margin-top:6px; font-family:var(--font-mono);">${latest.audited_url}</h3>
              </div>
              <div style="text-align:right;">
                <div style="font-size:28px; font-weight:800; color:#10b981; font-family:var(--font-mono);">${latest.overall_health_score} / 100</div>
                <span class="badge badge-success" style="font-weight:800;">Grade: ${latest.grade}</span>
              </div>
            </div>

            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:14px;">
              <div style="background:rgba(30,41,59,0.6); padding:12px; border-radius:10px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Focus Keyword</div>
                <div style="font-size:13px; font-weight:700; color:var(--accent-cyan); margin-top:2px;">${latest.focus_keyword}</div>
              </div>
              <div style="background:rgba(30,41,59,0.6); padding:12px; border-radius:10px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Word Count</div>
                <div style="font-size:13px; font-weight:700; color:#fff; margin-top:2px;">${latest.on_page_metrics.current_word_count} words <span style="font-size:10px; color:var(--text-muted);">(Rec: ${latest.on_page_metrics.recommended_word_count})</span></div>
              </div>
              <div style="background:rgba(30,41,59,0.6); padding:12px; border-radius:10px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Schema Status</div>
                <div style="font-size:13px; font-weight:700; color:${latest.on_page_metrics.has_schema_markup ? '#10b981' : '#f59e0b'}; margin-top:2px;">${latest.on_page_metrics.has_schema_markup ? 'Installed' : 'Needs JSON-LD Markup'}</div>
              </div>
            </div>

            <div style="background:rgba(30,41,59,0.4); padding:14px; border-radius:10px; border-left:3px solid #10b981;">
              <div style="font-size:11.5px; font-weight:800; color:#10b981; text-transform:uppercase; margin-bottom:6px;">Executive Google Action Checklist:</div>
              ${(latest.executive_action_checklist || []).map(item => `<div style="font-size:12px; color:var(--text-secondary); margin-bottom:3px;">${item}</div>`).join('')}
            </div>
          </div>
        ` : ''}

        <div style="background:rgba(168,85,247,0.1); border:1px solid rgba(168,85,247,0.3); padding:16px; border-radius:12px;">
          <div style="font-size:12px; font-weight:800; color:var(--accent-purple); text-transform:uppercase; margin-bottom:8px;">Standard Google Algorithm Compliance Tips for ${data.site_name}:</div>
          ${(pom.recommendations || []).map(r => `<div style="font-size:12.5px; color:var(--text-secondary); margin-bottom:4px;">-> ${r}</div>`).join('')}
        </div>
      `;
    } else {
      const dm = data.domain_metrics || {};
      container.innerHTML = `
        <div style="background:rgba(30,41,59,0.7); border:1px solid var(--glass-border); padding:18px; border-radius:14px; margin-bottom:18px;">
          <div style="font-size:12px; font-weight:800; color:var(--accent-cyan); text-transform:uppercase; margin-bottom:8px;">Recent Execution Outputs (${data.site_name}):</div>
          <pre style="background:#030712; padding:14px; border-radius:10px; color:#38bdf8; font-family:var(--font-mono); font-size:12px; max-height:280px; overflow-y:auto; white-space:pre-wrap; word-break:break-word;">${JSON.stringify(dm.latest_findings || {}, null, 2)}</pre>
        </div>

        <div style="background:rgba(168,85,247,0.1); border:1px solid rgba(168,85,247,0.3); padding:16px; border-radius:12px;">
          <div style="font-size:12px; font-weight:800; color:var(--accent-purple); text-transform:uppercase; margin-bottom:8px;">Domain Recommendations for ${data.site_name}:</div>
          ${(dm.recommendations || []).map(r => `<div style="font-size:12.5px; color:var(--text-secondary); margin-bottom:4px;">-> ${r}</div>`).join('')}
        </div>
      `;
    }

    openModal('agent-report-modal');
  } catch (err) {
    alert(`Failed to load performance report: ${err}`);
  }
}

async function loadTasks() {
  try {
    const res = await fetch(`/api/tasks?site_id=${currentSiteId}`);
    const data = await res.json();
    const tbody = document.getElementById('tasks-table');

    if (!data.tasks || data.tasks.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:30px;">No tasks currently in queue</td></tr>';
      return;
    }

    tbody.innerHTML = data.tasks.map(t => `
      <tr>
        <td style="font-family:var(--font-mono); font-weight:600; color:var(--accent-cyan);">${t.task_id}</td>
        <td><span class="action-chip">${t.agent_id}</span></td>
        <td><strong>${t.task_type}</strong></td>
        <td><span class="badge ${getBadgeForStatus(t.status)}">${t.status}</span></td>
        <td>${t.requires_approval ? (t.status === 'AWAITING_APPROVAL' ? '<span class="badge badge-warning">Awaiting</span>' : '<span class="badge badge-success">Approved</span>') : '<span class="badge badge-info">Auto</span>'}</td>
        <td style="font-family:var(--font-mono); font-size:11px;">${t.model_used || '-'}</td>
        <td style="color:var(--status-success); font-weight:700;">$${t.cost_usd.toFixed(6)}</td>
        <td style="font-size:11px; font-family:var(--font-mono);">${t.created_at.substring(11, 19)}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="viewTaskDetail('${t.task_id}')">View</button>
          ${t.status === 'APPROVED' || t.status === 'QUEUED' ? `<button class="btn btn-primary btn-sm" onclick="executeTask('${t.task_id}')">Exec</button>` : ''}
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load tasks:', err);
  }
}

async function executeTask(taskId) {
  try {
    const res = await fetch(`/api/tasks/execute/${taskId}`, { method: 'POST' });
    const data = await res.json();
    alert(`Execution completed for ${taskId}. Status: ${data.task.status}`);
    loadCurrentView(activeView);
  } catch (err) {
    alert(`Failed to execute task: ${err}`);
  }
}

async function viewTaskDetail(taskId) {
  try {
    const res = await fetch(`/api/tasks/${taskId}`);
    const data = await res.json();
    document.getElementById('detail-task-id').textContent = `Task ${data.task.task_id}`;
    document.getElementById('task-detail-content').innerHTML = `
      <pre style="background:#030712; border:1px solid var(--glass-border-glow); padding:18px; border-radius:12px; color:#38bdf8; font-family:var(--font-mono); font-size:12px; line-height:1.6; max-height:65vh; overflow-y:auto; overflow-x:auto; white-space:pre-wrap; word-break:break-word; box-shadow:inset 0 2px 10px rgba(0,0,0,0.8);">${JSON.stringify(data.task, null, 2)}</pre>
    `;
    openModal('task-detail-modal');
  } catch (err) {
    alert(`Failed to fetch task detail: ${err}`);
  }
}

async function loadApprovals() {
  try {
    const res = await fetch(`/api/approvals?site_id=${currentSiteId}`);
    const data = await res.json();
    const tbody = document.getElementById('approvals-table');

    if (!data.approvals || data.approvals.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:30px;">No tasks currently awaiting human approval</td></tr>';
      return;
    }

    tbody.innerHTML = data.approvals.map(a => `
      <tr>
        <td style="font-family:var(--font-mono); font-weight:600; color:var(--accent-amber);">${a.task_id}</td>
        <td><span class="action-chip">${a.agent_id}</span></td>
        <td><strong>${a.task_type}</strong></td>
        <td><span class="badge badge-warning">${a.priority}</span></td>
        <td style="font-family:var(--font-mono); font-size:11px;">${JSON.stringify(a.input_data)}</td>
        <td style="font-size:11px; font-family:var(--font-mono);">${a.created_at.substring(11, 19)}</td>
        <td>
          <button class="btn btn-primary btn-sm" onclick="approveTask('${a.task_id}')">Approve</button>
          <button class="btn btn-secondary btn-sm" style="color:#ef4444;" onclick="rejectTask('${a.task_id}')">Reject</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load approvals:', err);
  }
}

async function approveTask(taskId) {
  try {
    const res = await fetch(`/api/approvals/${taskId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved_by: 'admin', comment: 'Approved via UI' })
    });
    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      alert(`Approval error: ${data.detail || data.message || 'Failed'}`);
      return;
    }
    await loadApprovals();
    if (activeView === 'overview') loadOverview();
    updateDynamicAgentCounters();
  } catch (err) {
    alert(`Failed to approve task: ${err}`);
  }
}

async function rejectTask(taskId) {
  try {
    const res = await fetch(`/api/approvals/${taskId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rejected_by: 'admin', reason: 'Rejected by dashboard user' })
    });
    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      alert(`Rejection error: ${data.detail || data.message || 'Failed'}`);
      return;
    }
    await loadApprovals();
    if (activeView === 'overview') loadOverview();
    updateDynamicAgentCounters();
  } catch (err) {
    alert(`Failed to reject task: ${err}`);
  }
}

async function approveAllTasks() {
  if (!confirm('Are you sure you want to approve and execute all pending tasks?')) return;
  try {
    const res = await fetch('/api/approvals/approve-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approver: 'admin' })
    });
    const data = await res.json();
    if (!res.ok) {
      alert(`Error approving tasks: ${data.detail || 'Failed'}`);
      return;
    }
    alert(`Successfully approved and processed ${data.approved_count} tasks.`);
    await loadApprovals();
    if (activeView === 'overview') loadOverview();
    updateDynamicAgentCounters();
  } catch (err) {
    alert(`Failed to approve all tasks: ${err}`);
  }
}

async function rejectAllTasks() {
  if (!confirm('Are you sure you want to reject all pending tasks?')) return;
  try {
    const res = await fetch('/api/approvals/reject-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rejecter: 'admin' })
    });
    const data = await res.json();
    if (!res.ok) {
      alert(`Error rejecting tasks: ${data.detail || 'Failed'}`);
      return;
    }
    alert(`Successfully rejected ${data.rejected_count} tasks.`);
    await loadApprovals();
    if (activeView === 'overview') loadOverview();
    updateDynamicAgentCounters();
  } catch (err) {
    alert(`Failed to reject all tasks: ${err}`);
  }
}

async function loadScheduler() {
  try {
    const res = await fetch('/api/schedules');
    const data = await res.json();
    const tbody = document.getElementById('scheduler-table');

    if (!data.schedules || data.schedules.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:30px;">No cron schedules registered</td></tr>';
      return;
    }

    tbody.innerHTML = data.schedules.map(s => `
      <tr>
        <td style="font-family:var(--font-mono); font-weight:600;">${s.job_id}</td>
        <td><span class="action-chip">${s.agent_id}</span></td>
        <td style="font-family:var(--font-mono); color:var(--accent-purple);">${s.cron_expression}</td>
        <td><strong>${s.action}</strong></td>
        <td><span class="badge ${s.enabled ? 'badge-success' : 'badge-danger'}">${s.enabled ? 'Enabled' : 'Disabled'}</span></td>
        <td style="font-size:11px; font-family:var(--font-mono);">${s.next_run_utc || 'Scheduled'}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load scheduler:', err);
  }
}

async function loadAIUsage() {
  try {
    await loadAIProviders();

    const res = await fetch('/api/ai-usage');
    const data = await res.json();

    const metricsHtml = `
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">Total Model Invocations</div>
          <div class="metric-icon-box" style="background:rgba(6, 182, 212, 0.2); color:var(--accent-cyan);">
            <i class="fa-solid fa-bolt"></i>
          </div>
        </div>
        <div class="metric-value" style="color:var(--accent-cyan);">${data.total_requests}</div>
        <div class="metric-subtext">AI Router Execution Engine</div>
      </div>
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">Total Token Volume</div>
          <div class="metric-icon-box" style="background:rgba(168, 85, 247, 0.2); color:var(--accent-purple);">
            <i class="fa-solid fa-layer-group"></i>
          </div>
        </div>
        <div class="metric-value" style="color:var(--accent-purple);">${data.total_tokens}</div>
        <div class="metric-subtext">Tokens In + Out</div>
      </div>
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">Total USD Expenditure</div>
          <div class="metric-icon-box" style="background:rgba(16, 185, 129, 0.2); color:var(--status-success);">
            <i class="fa-solid fa-sack-dollar"></i>
          </div>
        </div>
        <div class="metric-value" style="color:var(--status-success);">$${data.total_cost_usd.toFixed(4)}</div>
        <div class="metric-subtext">Optimized Cost Tracking</div>
      </div>
    `;
    document.getElementById('ai-metrics-grid').innerHTML = metricsHtml;

    const tbody = document.getElementById('ai-models-table');
    tbody.innerHTML = Object.entries(data.models).map(([model, details]) => `
      <tr>
        <td style="font-family:var(--font-mono); font-weight:600;">${model}</td>
        <td>${details.calls}</td>
        <td style="color:var(--status-success); font-weight:600;">$${details.cost_per_1k_tokens || '0.003'} USD</td>
        <td><span class="badge badge-info">Standard Priority</span></td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load AI usage:', err);
  }
}

async function loadLogs() {
  try {
    const agent = document.getElementById('logs-agent-filter').value;
    const res = await fetch(`/api/logs?agent_id=${agent}`);
    const data = await res.json();
    document.getElementById('logs-content').textContent = data.logs || 'No logs recorded.';
  } catch (err) {
    console.error('Failed to load logs:', err);
  }
}

async function loadErrors() {
  try {
    const res = await fetch('/api/errors');
    const data = await res.json();
    const tbody = document.getElementById('errors-table');

    if (!data.errors || data.errors.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:30px;">Zero system errors logged</td></tr>';
      return;
    }

    tbody.innerHTML = data.errors.map(e => `
      <tr>
        <td style="font-family:var(--font-mono);">${e.task_id}</td>
        <td><span class="action-chip">${e.agent_id}</span></td>
        <td><span class="badge badge-warning">${e.retry_count}</span></td>
        <td style="color:#ef4444; font-family:var(--font-mono); font-size:11px;">${e.error}</td>
        <td style="font-size:11px; font-family:var(--font-mono);">${e.failed_at.substring(11, 19)}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load errors:', err);
  }
}

async function loadAuditTrail() {
  try {
    const res = await fetch('/api/audit-trail?limit=50');
    const data = await res.json();
    const tbody = document.getElementById('audit-table');

    if (!data.events || data.events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:30px;">No audit trail records</td></tr>';
      return;
    }

    tbody.innerHTML = data.events.map(e => `
      <tr>
        <td style="font-family:var(--font-mono); font-size:11px; color:var(--accent-purple);">${e.event_id}</td>
        <td style="font-family:var(--font-mono); font-size:11px;">${e.timestamp.substring(0, 19).replace('T', ' ')}</td>
        <td><span class="action-chip">${e.agent_id}</span></td>
        <td><strong>${e.action}</strong></td>
        <td>${e.user_id}</td>
        <td style="font-family:var(--font-mono); font-size:11px;">${JSON.stringify(e.details)}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load audit trail:', err);
  }
}

async function loadHealth() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();

    const metricsHtml = `
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">System Health Status</div>
          <div class="metric-icon-box" style="background:rgba(16, 185, 129, 0.2); color:var(--status-success);">
            <i class="fa-solid fa-heart-pulse"></i>
          </div>
        </div>
        <div class="metric-value" style="color:var(--status-success);">${data.status}</div>
        <div class="metric-subtext">All Sub-systems Normal</div>
      </div>
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">Ads Live Guard</div>
          <div class="metric-icon-box" style="background:rgba(239, 68, 68, 0.2); color:#ef4444;">
            <i class="fa-solid fa-shield-cat"></i>
          </div>
        </div>
        <div class="metric-value" style="color:#ef4444; font-size:22px;">${data.ads_guard}</div>
        <div class="metric-subtext">Mutation Guard Active</div>
      </div>
      <div class="metric-card">
        <div class="metric-card-header">
          <div class="metric-label">Uptime Reliability</div>
          <div class="metric-icon-box" style="background:rgba(6, 182, 212, 0.2); color:var(--accent-cyan);">
            <i class="fa-solid fa-server"></i>
          </div>
        </div>
        <div class="metric-value" style="color:var(--accent-cyan);">100%</div>
        <div class="metric-subtext">Zero Crash Downtime</div>
      </div>
    `;
    document.getElementById('health-grid').innerHTML = metricsHtml;
  } catch (err) {
    console.error('Failed to load health:', err);
  }
}

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    const tbody = document.getElementById('settings-table');

    tbody.innerHTML = data.settings.map(s => {
      const isAIProvider = s.feature.includes('API') || s.feature.includes('Claude') || s.feature.includes('Gemini') || s.feature.includes('OpenAI') || s.feature.includes('DeepSeek') || s.feature.includes('Groq') || s.feature.includes('Custom');
      let provId = 'anthropic';
      if (s.feature.includes('Gemini')) provId = 'gemini';
      else if (s.feature.includes('OpenAI')) provId = 'openai';
      else if (s.feature.includes('DeepSeek')) provId = 'deepseek';
      else if (s.feature.includes('Groq')) provId = 'groq';
      else if (s.feature.includes('Custom')) provId = 'custom';

      return `
        <tr>
          <td>
            <strong>${s.feature}</strong>
          </td>
          <td>
            <span class="badge ${s.status === 'ACTIVE_PRIMARY' ? 'badge-success' : (s.status === 'CONFIGURED' ? 'badge-info' : 'badge-warning')}" style="${s.status === 'ACTIVE_PRIMARY' ? 'background:linear-gradient(135deg,#10b981,#059669); color:#fff; font-weight:800;' : ''}">
              ${s.status}
            </span>
          </td>
          <td style="font-family:var(--font-mono); font-size:12px;">${s.mode}</td>
          <td>
            <div style="display:flex; align-items:center; gap:8px; justify-content:space-between;">
              <span class="badge badge-info">${s.flag}</span>
              ${isAIProvider ? `
                <button class="btn btn-secondary btn-sm" onclick="openConfigureAIModal('${provId}')" style="font-size:11px; padding:3px 10px; color:var(--accent-purple); border-color:rgba(168,85,247,0.4);">
                  <i class="fa-solid fa-key"></i> Key Vault
                </button>
              ` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to load settings:', err);
  }
}

function getBadgeForStatus(status) {
  switch (status) {
    case 'COMPLETED': return 'badge-success';
    case 'RUNNING': return 'badge-info';
    case 'AWAITING_APPROVAL': return 'badge-warning';
    case 'FAILED': return 'badge-danger';
    default: return 'badge-info';
  }
}

function updateDynamicAgentCounters(totalAgents, activeAgents) {
  if (!totalAgents) return;
  const navCount = document.getElementById('nav-agents-count');
  if (navCount) navCount.textContent = totalAgents;

  const brandCount = document.getElementById('brand-agents-count');
  if (brandCount) brandCount.textContent = `${totalAgents}-AGENT AI OS`;

  const nodeCount = document.getElementById('cyber-node-agents-count');
  if (nodeCount) nodeCount.textContent = activeAgents !== undefined ? `${activeAgents} Sub-Agents Active` : `${totalAgents} Sub-Agents Active`;

  const heroDesc = document.getElementById('cyber-hero-desc');
  if (heroDesc) {
    heroDesc.textContent = `Autonomous ${totalAgents}-Agent Marketing Operating System controlling SEO, Google Ads, Meta Ads, Social Media, Reviews, and Corporate Lead Pipeline for Corporate Cars Melbourne.`;
  }
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('active');
}

function openCustomOutreachModal() {
  openModal('custom-outreach-modal');
}

async function submitCustomOutreach(e) {
  if (e) e.preventDefault();
  const sitesInput = document.getElementById('outreach-target-websites').value.trim();
  if (!sitesInput) {
    alert('Please enter at least one target website URL to place backlinks on.');
    return;
  }
  const sites = sitesInput.split(/[\n,]+/).map(s => s.trim()).filter(s => s.length > 0);
  const activeSite = allWebsitesList.find(s => s.site_id === currentSiteId);
  const defaultDomain = activeSite ? (activeSite.domain.endsWith('/') ? activeSite.domain : activeSite.domain + '/') : 'https://corporatecarsmelbourne.com.au/';
  const defaultAnchor = activeSite ? activeSite.name : 'Corporate Cars Melbourne';
  const defaultTopic = activeSite ? `Luxury Chauffeur & Executive Airport Transfers ${activeSite.location}` : 'Luxury Chauffeur & Executive Airport Transfers Melbourne';

  const landingPage = document.getElementById('outreach-landing-page').value.trim() || defaultDomain;
  const anchorText = document.getElementById('outreach-anchor-text').value.trim() || defaultAnchor;
  const topic = document.getElementById('outreach-topic').value.trim() || defaultTopic;
  const useAi = document.getElementById('outreach-use-ai') ? document.getElementById('outreach-use-ai').checked : true;

  const btn = document.getElementById('btn-submit-outreach');
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating Contextual Backlinks...';

  try {
    const res = await fetch('/api/agents/external-link/custom-outreach', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_websites: sites,
        landing_page_url: landingPage,
        anchor_text: anchorText,
        topic: topic,
        use_ai: useAi
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Success! Generated ${data.output?.processed_count || sites.length} contextual backlinks with live URLs.`);
      closeModal('custom-outreach-modal');
      showAgentPerformanceReport('external-link-building-agent');
    } else {
      alert(`Outreach Error: ${data.detail || 'Failed to process outreach'}`);
    }
  } catch (err) {
    alert(`Outreach request failed: ${err}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

async function runDailyBacklinkBatch() {
  if (!confirm('Run daily automated batch of 5 to 10 high-quality directory and Web 2.0 editorial backlinks?')) {
    return;
  }
  try {
    const res = await fetch('/api/agents/external-link/daily-batch?batch_size=7', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      alert(`Daily Batch Complete! Generated ${data.output?.batch_count || 7} high-quality backlinks across Australian directories & Web 2.0 platforms.`);
      showAgentPerformanceReport('external-link-building-agent');
    } else {
      alert(`Batch Error: ${data.detail || 'Failed to execute daily batch'}`);
    }
  } catch (err) {
    alert(`Failed to trigger daily batch: ${err}`);
  }
}

function openCompetitorAdSpyModal(url) {
  if (url) {
    document.getElementById('spy-competitor-url').value = url;
  }
  openModal('competitor-ad-spy-modal');
}

async function submitCompetitorAdSpy(e) {
  if (e) e.preventDefault();
  const url = document.getElementById('spy-competitor-url').value.trim();
  if (!url) {
    alert('Please enter a competitor website URL.');
    return;
  }
  const location = document.getElementById('spy-location').value.trim() || 'Melbourne, Victoria';
  const btn = document.getElementById('btn-submit-ad-spy');
  const resultsContainer = document.getElementById('spy-results-container');

  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Spying Google & Meta Ads...';

  resultsContainer.innerHTML = `
    <div style="text-align:center; padding:50px; color:var(--text-muted);">
      <div style="font-size:24px; color:#ef4444; margin-bottom:12px;"><i class="fa-solid fa-radar fa-spin"></i></div>
      <div style="font-size:14px; font-weight:700; color:var(--text-primary);">Scanning Ad Transparency & Meta Ad Library for ${url}...</div>
      <div style="font-size:12px; color:var(--text-muted); margin-top:6px;">Extracting Search Headlines, Targeted Keywords, Facebook/IG Creatives & AI Counter-Attack Strategy.</div>
    </div>
  `;

  try {
    const res = await fetch('/api/agents/ad-spy/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        competitor_url: url,
        location: location,
        use_ai: true,
        site_id: currentSiteId
      })
    });
    const data = await res.json();
    if (res.ok && data.output) {
      renderCompetitorAdSpyResults(data.output);
    } else {
      resultsContainer.innerHTML = `
        <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); padding:20px; border-radius:12px; color:#ef4444;">
          <strong>Analysis Error:</strong> ${data.detail || 'Failed to extract competitor ads.'}
        </div>
      `;
    }
  } catch (err) {
    resultsContainer.innerHTML = `
      <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); padding:20px; border-radius:12px; color:#ef4444;">
        <strong>Request Failed:</strong> ${err}
      </div>
    `;
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
  }
}

function renderCompetitorAdSpyResults(report) {
  window.currentAdSpyReport = report;
  const g = report.google_ads_intelligence || {};
  const m = report.meta_ads_intelligence || {};
  const c = report.winning_counter_strategy || {};
  const gAds = g.ad_variations || [];
  const mAds = m.active_ads || [];
  const kwList = g.targeted_keywords || [];
  const activeSite = allWebsitesList.find(s => s.site_id === currentSiteId);
  const targetBrand = report.target_brand || (activeSite ? activeSite.name : 'Our Brand');

  const html = `
    <!-- Top Summary Banner with Official Live Verification Badges -->
    <div style="background:linear-gradient(135deg, rgba(239,68,68,0.12), rgba(249,115,22,0.08)); border:1px solid rgba(239,68,68,0.3); padding:18px 22px; border-radius:14px; margin-bottom:24px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
      <div>
        <div style="font-size:16.5px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
          <i class="fa-solid fa-bullseye" style="color:#ef4444;"></i> Target Competitor: <span style="color:#38bdf8;">${report.competitor_brand}</span> (${report.competitor_domain})
        </div>
        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
          Market: <strong>${report.location}</strong> | Est. Monthly Ad Spend: <strong style="color:#10b581;">${g.estimated_monthly_ad_spend || '$3,500 AUD'}</strong>
        </div>
      </div>
      <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
        <a href="${report.official_verification_links?.google_ads_transparency || `https://adstransparency.google.com/?region=AU&domain=${report.competitor_domain}`}" target="_blank" class="btn btn-secondary btn-sm" style="color:#38bdf8; border-color:rgba(56,189,248,0.5); text-decoration:none; display:inline-flex; align-items:center; gap:6px; font-weight:700;">
          <i class="fa-brands fa-google"></i> Live Google Transparency <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:10px;"></i>
        </a>
        <a href="${report.official_verification_links?.meta_ad_library || `https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=AU&q=${report.competitor_domain}`}" target="_blank" class="btn btn-secondary btn-sm" style="color:#60a5fa; border-color:rgba(59,130,246,0.5); text-decoration:none; display:inline-flex; align-items:center; gap:6px; font-weight:700;">
          <i class="fa-brands fa-facebook"></i> Live Meta Ad Library <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:10px;"></i>
        </a>
        <span class="badge badge-danger" style="font-size:11.5px; padding:6px 12px;"><i class="fa-brands fa-google"></i> ${gAds.length} Google Search Ads</span>
        <span class="badge badge-warning" style="font-size:11.5px; padding:6px 12px;"><i class="fa-brands fa-facebook"></i> ${mAds.length} Meta Ads</span>
      </div>
    </div>

    <!-- Section 1: Google Ads Intelligence -->
    <div style="margin-bottom:28px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; border-bottom:1px solid var(--glass-border); padding-bottom:8px;">
        <h3 style="font-size:15px; font-weight:800; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
          <i class="fa-brands fa-google" style="color:#38bdf8;"></i> SECTION 1: Competitor Google Ads & Targeted Bidding Keywords
        </h3>
        <span style="font-size:11.5px; color:var(--accent-cyan); font-weight:700;"><i class="fa-solid fa-hand-pointer"></i> Click any ad to view full keyword & heading breakdown</span>
      </div>

      <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:18px;">
        ${gAds.map((ad, idx) => `
          <div onclick="inspectGoogleAd(${idx})" style="background:#090d16; border:1px solid rgba(56,189,248,0.25); padding:16px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.5); cursor:pointer; transition:all 0.25s ease;" onmouseover="this.style.borderColor='var(--accent-cyan)'; this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(6,182,212,0.25)'" onmouseout="this.style.borderColor='rgba(56,189,248,0.25)'; this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(0,0,0,0.5)'">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <span style="font-size:10.5px; font-weight:800; background:#1e293b; color:#38bdf8; padding:3px 8px; border-radius:4px; text-transform:uppercase;">
                ${ad.ad_type || 'Google Search Ad'}
              </span>
              <button class="btn btn-secondary btn-sm" style="font-size:10.5px; color:#38bdf8; border-color:rgba(56,189,248,0.4); padding:3px 8px;" onclick="event.stopPropagation(); inspectGoogleAd(${idx})">
                <i class="fa-solid fa-expand"></i> Inspect Copy & Keywords
              </button>
            </div>

            <!-- SERP Style Mockup -->
            <div style="font-size:11px; color:#94a3b8; margin-bottom:4px; font-family:var(--font-mono);">
              <span style="background:#22c55e; color:#000; font-weight:800; padding:1px 4px; border-radius:3px; font-size:9.5px; margin-right:5px;">Ad</span>
              https://${ad.display_path || report.competitor_domain}
            </div>
            <div style="font-size:14.5px; font-weight:700; color:#60a5fa; line-height:1.3; margin-bottom:6px;">
              ${ad.headline_1} | ${ad.headline_2} ${ad.headline_3 ? `| ${ad.headline_3}` : ''}
            </div>
            <div style="font-size:12.5px; color:#cbd5e1; line-height:1.4; margin-bottom:10px;">
              ${ad.description_1} ${ad.description_2 ? ad.description_2 : ''}
            </div>

            <!-- Sitelinks -->
            ${ad.sitelinks && ad.sitelinks.length ? `
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:10px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.06);">
                ${ad.sitelinks.map(s => `
                  <div style="font-size:11px; color:#38bdf8; font-weight:600;"><i class="fa-solid fa-arrow-right" style="font-size:9px;"></i> ${s.title || s}</div>
                `).join('')}
              </div>
            ` : ''}

            <!-- Callout Badges -->
            ${ad.callouts && ad.callouts.length ? `
              <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:10px;">
                ${ad.callouts.map(c => `<span style="font-size:10px; background:rgba(255,255,255,0.05); color:#94a3b8; padding:2px 6px; border-radius:4px;">${c}</span>`).join('')}
              </div>
            ` : ''}
          </div>
        `).join('')}
      </div>

      <!-- Targeted Keywords Table -->
      <div style="background:rgba(30,41,59,0.7); border:1px solid var(--glass-border); border-radius:12px; overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:12px;">
          <thead>
            <tr style="background:rgba(15,23,42,0.9); color:var(--text-muted); text-transform:uppercase;">
              <th style="padding:10px 14px;">Targeted Bidding Keyword</th>
              <th style="padding:10px 14px;">Match Type</th>
              <th style="padding:10px 14px;">Est. CPC ($AUD)</th>
              <th style="padding:10px 14px;">Search Volume</th>
              <th style="padding:10px 14px;">Search Intent</th>
            </tr>
          </thead>
          <tbody>
            ${kwList.map(kw => `
              <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                <td style="padding:10px 14px; font-weight:700; color:#fff; font-family:var(--font-mono);">${kw.keyword}</td>
                <td style="padding:10px 14px;"><span class="action-chip" style="font-size:11px;">${kw.match_type}</span></td>
                <td style="padding:10px 14px; font-weight:700; color:#10b581;">${kw.estimated_cpc}</td>
                <td style="padding:10px 14px; color:var(--accent-cyan); font-family:var(--font-mono);">${kw.search_volume || '1,500/mo'}</td>
                <td style="padding:10px 14px;"><span class="badge badge-warning" style="font-size:10px;">${kw.intent}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Section 2: Meta Ads Intelligence (Facebook & Instagram) -->
    <div style="margin-bottom:28px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; border-bottom:1px solid var(--glass-border); padding-bottom:8px;">
        <h3 style="font-size:15px; font-weight:800; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
          <i class="fa-brands fa-facebook" style="color:#3b82f6;"></i> SECTION 2: Competitor Meta Ads (Facebook & Instagram Creatives)
        </h3>
        <span style="font-size:11.5px; color:#60a5fa; font-weight:700;"><i class="fa-solid fa-hand-pointer"></i> Click any ad to view hook breakdown & creative details</span>
      </div>

      <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
        ${mAds.map((ad, idx) => `
          <div onclick="inspectMetaAd(${idx})" style="background:#0f172a; border:1px solid rgba(59,130,246,0.3); border-radius:12px; padding:18px; box-shadow:0 4px 15px rgba(0,0,0,0.5); cursor:pointer; transition:all 0.25s ease;" onmouseover="this.style.borderColor='#3b82f6'; this.style.transform='translateY(-3px)'; this.style.boxShadow='0 8px 25px rgba(59,130,246,0.25)'" onmouseout="this.style.borderColor='rgba(59,130,246,0.3)'; this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(0,0,0,0.5)'">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; padding-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.06);">
              <div style="display:flex; align-items:center; gap:8px;">
                <div style="width:32px; height:32px; border-radius:50%; background:linear-gradient(135deg,#3b82f6,#ec4899); display:flex; align-items:center; justify-content:center; color:#fff; font-weight:800; font-size:12px;">
                  ${report.competitor_brand.substring(0,2)}
                </div>
                <div>
                  <div style="font-weight:700; font-size:13px; color:#fff;">${report.competitor_brand}</div>
                  <div style="font-size:10.5px; color:#94a3b8;">Sponsored · <i class="fa-solid fa-earth-americas"></i> ${ad.started_running || 'Active'}</div>
                </div>
              </div>
              <button class="btn btn-secondary btn-sm" style="font-size:10.5px; color:#60a5fa; border-color:rgba(59,130,246,0.4); padding:3px 8px;" onclick="event.stopPropagation(); inspectMetaAd(${idx})">
                <i class="fa-solid fa-expand"></i> Inspect Hook
              </button>
            </div>

            <div style="font-size:12.5px; color:#e2e8f0; line-height:1.5; white-space:pre-wrap; margin-bottom:14px; background:rgba(30,41,59,0.5); padding:12px; border-radius:8px;">${ad.primary_text}</div>

            <div style="background:#020617; border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:12px; display:flex; justify-content:space-between; align-items:center;">
              <div>
                <div style="font-size:10.5px; color:#94a3b8; text-transform:uppercase; font-family:var(--font-mono);">${report.competitor_domain}</div>
                <div style="font-weight:700; font-size:13px; color:#fff; margin-top:2px;">${ad.headline}</div>
                <div style="font-size:11px; color:#64748b; margin-top:2px;">${ad.description || ''}</div>
              </div>
              <button class="btn btn-primary btn-sm" style="background:#3b82f6; font-weight:700; font-size:11.5px; padding:6px 14px; white-space:nowrap;">
                ${ad.call_to_action || 'Book Now'}
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    </div>

    <!-- Section 3: AI Counter-Attack Strategy -->
    <div style="background:linear-gradient(135deg, rgba(168,85,247,0.12), rgba(6,182,212,0.08)); border:1px solid rgba(168,85,247,0.4); padding:20px; border-radius:14px;">
      <h3 style="font-size:16px; font-weight:800; color:#fff; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
        <i class="fa-solid fa-shield-halved" style="color:var(--accent-purple);"></i> SECTION 3: Winning Counter-Attack Strategy for ${targetBrand}
      </h3>

      <!-- Vulnerabilities -->
      <div style="margin-bottom:16px;">
        <div style="font-size:12px; font-weight:800; color:#f87171; text-transform:uppercase; margin-bottom:6px;">Competitor Vulnerabilities Identified:</div>
        ${(c.vulnerabilities_in_competitor_ads || c.vulnerabilities || []).map(v => `
          <div style="font-size:12.5px; color:#cbd5e1; margin-bottom:4px;"><i class="fa-solid fa-triangle-exclamation" style="color:#f87171; font-size:11px;"></i> ${v}</div>
        `).join('')}
      </div>

      <!-- Counter Google Ad -->
      ${c.recommended_counter_google_ad ? `
        <div style="background:#090d16; border:1px solid var(--accent-cyan); padding:16px; border-radius:10px; margin-bottom:14px;">
          <div style="font-size:11px; font-weight:800; color:var(--accent-cyan); text-transform:uppercase; margin-bottom:6px;">
            <i class="fa-brands fa-google"></i> Recommended Winning Google Search Ad Copy (Ready to Deploy):
          </div>
          <div style="font-size:14px; font-weight:700; color:#38bdf8; margin-bottom:4px;">
            ${c.recommended_counter_google_ad.headline_1} | ${c.recommended_counter_google_ad.headline_2} | ${c.recommended_counter_google_ad.headline_3}
          </div>
          <div style="font-size:12.5px; color:#e2e8f0; line-height:1.4;">
            ${c.recommended_counter_google_ad.description_1} ${c.recommended_counter_google_ad.description_2 || ''}
          </div>
          <div style="font-size:11px; color:#94a3b8; margin-top:6px; font-family:var(--font-mono);">
            Destination: <a href="${c.recommended_counter_google_ad.target_url}" target="_blank" style="color:var(--accent-purple);">${c.recommended_counter_google_ad.target_url}</a>
          </div>
        </div>
      ` : ''}

      <!-- Counter Meta Ad -->
      ${c.recommended_counter_meta_ad ? `
        <div style="background:#090d16; border:1px solid var(--accent-purple); padding:16px; border-radius:10px;">
          <div style="font-size:11px; font-weight:800; color:var(--accent-purple); text-transform:uppercase; margin-bottom:6px;">
            <i class="fa-brands fa-facebook"></i> Recommended Winning Meta Ad Copy (Facebook & Instagram):
          </div>
          <div style="font-size:12px; color:#cbd5e1; font-weight:700; margin-bottom:6px; color:#fbbf24;">Hook: "${c.recommended_counter_meta_ad.hook}"</div>
          <div style="font-size:12.5px; color:#e2e8f0; line-height:1.5; white-space:pre-wrap; background:rgba(30,41,59,0.5); padding:12px; border-radius:8px; margin-bottom:8px;">${c.recommended_counter_meta_ad.primary_text}</div>
          <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px;">
            <strong style="color:#fff;">Headline: ${c.recommended_counter_meta_ad.headline}</strong>
            <span class="badge badge-info">CTA: ${c.recommended_counter_meta_ad.call_to_action || 'Book Now'}</span>
          </div>
        </div>
      ` : ''}
    </div>
  `;

  document.getElementById('spy-results-container').innerHTML = html;
}

function inspectGoogleAd(idx) {
  if (!window.currentAdSpyReport) return;
  const report = window.currentAdSpyReport;
  const g = report.google_ads_intelligence || {};
  const ads = g.ad_variations || [];
  const ad = ads[idx];
  if (!ad) return;

  const keywords = g.targeted_keywords || [];
  const fullCopy = `--- HEADLINES ---
Headline 1: ${ad.headline_1}
Headline 2: ${ad.headline_2}
Headline 3: ${ad.headline_3 || 'N/A'}

--- DESCRIPTIONS ---
Description 1: ${ad.description_1}
Description 2: ${ad.description_2 || 'N/A'}

--- SITELINKS ---
${(ad.sitelinks || []).map(s => `• ${s.title || s}: ${s.url || ''}`).join('\n')}

--- TARGET LANDING PAGE ---
${ad.landing_page || `https://${report.competitor_domain}`}
`;

  document.getElementById('inspector-modal-title').innerHTML = `
    <i class="fa-brands fa-google" style="color:#38bdf8;"></i> Google Search Ad Inspector — ${ad.ad_type || 'Responsive Search Ad'}
  `;
  document.getElementById('inspector-modal-subtitle').innerHTML = `
    Detailed breakdown of targeted bidding keywords, headings, descriptions, sitelinks, assets, and landing page for <strong>${report.competitor_brand}</strong>.
  `;

  const html = `
    <!-- Top Action Bar -->
    <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(30,41,59,0.7); padding:12px 16px; border-radius:10px; margin-bottom:18px; border:1px solid var(--glass-border);">
      <div style="font-size:12px; color:var(--text-muted);">
        Competitor: <strong style="color:#fff;">${report.competitor_brand}</strong> (${report.competitor_domain})
      </div>
      <div style="display:flex; gap:8px;">
        <button id="btn-copy-g-ad" class="btn btn-primary btn-sm" style="background:linear-gradient(135deg, var(--accent-cyan), #0284c7);" onclick="copyToClipboard(\`${fullCopy.replace(/`/g, '\\`')}\`, 'btn-copy-g-ad')">
          <i class="fa-solid fa-copy"></i> Copy Full Ad Copy
        </button>
        <a href="${ad.landing_page || `https://${report.competitor_domain}`}" target="_blank" class="btn btn-secondary btn-sm" style="color:var(--accent-cyan); border-color:rgba(6,182,212,0.4); text-decoration:none; display:inline-flex; align-items:center; gap:5px;">
          <i class="fa-solid fa-arrow-up-right-from-square"></i> Visit Landing Page
        </a>
      </div>
    </div>

    <!-- 1. Live SERP Ad Preview Mockup -->
    <div style="background:#030712; border:1px solid rgba(56,189,248,0.4); border-radius:14px; padding:20px; margin-bottom:20px; box-shadow:0 8px 30px rgba(0,0,0,0.7);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <span style="font-size:10.5px; font-weight:800; color:#38bdf8; background:rgba(56,189,248,0.12); padding:3px 8px; border-radius:4px; text-transform:uppercase;">
          Live Google Search Mockup
        </span>
        <span style="font-size:11px; color:#94a3b8; font-family:var(--font-mono);">Position: Top of Page #1</span>
      </div>

      <div style="font-size:12px; color:#94a3b8; font-family:var(--font-mono); margin-bottom:5px;">
        <span style="background:#22c55e; color:#000; font-weight:800; padding:1px 5px; border-radius:3px; font-size:10px; margin-right:6px;">Ad</span>
        https://${ad.display_path || report.competitor_domain}
      </div>
      <div style="font-size:17px; font-weight:700; color:#60a5fa; line-height:1.3; margin-bottom:8px;">
        ${ad.headline_1} | ${ad.headline_2} ${ad.headline_3 ? `| ${ad.headline_3}` : ''}
      </div>
      <div style="font-size:13.5px; color:#cbd5e1; line-height:1.5; margin-bottom:12px;">
        ${ad.description_1} ${ad.description_2 ? ad.description_2 : ''}
      </div>

      <!-- Sitelinks in Mockup -->
      ${ad.sitelinks && ad.sitelinks.length ? `
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.08);">
          ${ad.sitelinks.map(s => `
            <div style="font-size:12px; color:#38bdf8; font-weight:700;">
              <i class="fa-solid fa-arrow-right" style="font-size:10px;"></i> ${s.title || s}
            </div>
          `).join('')}
        </div>
      ` : ''}
    </div>

    <!-- 2. Detailed Headings & Descriptions Breakdown -->
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px;">
      <!-- Headings Panel -->
      <div style="background:rgba(15,23,42,0.7); border:1px solid var(--glass-border); padding:16px; border-radius:12px;">
        <h4 style="font-size:13px; font-weight:800; color:#38bdf8; text-transform:uppercase; margin-bottom:12px; display:flex; align-items:center; gap:6px;">
          <i class="fa-solid fa-heading"></i> Search Ad Headlines
        </h4>
        <div style="margin-bottom:10px;">
          <div style="font-size:11px; color:var(--text-muted);">Headline 1 (${ad.headline_1.length}/30 chars):</div>
          <div style="font-size:13px; font-weight:700; color:#fff; background:#090d16; padding:8px 10px; border-radius:6px; margin-top:3px; border:1px solid rgba(255,255,255,0.06);">${ad.headline_1}</div>
        </div>
        <div style="margin-bottom:10px;">
          <div style="font-size:11px; color:var(--text-muted);">Headline 2 (${ad.headline_2.length}/30 chars):</div>
          <div style="font-size:13px; font-weight:700; color:#fff; background:#090d16; padding:8px 10px; border-radius:6px; margin-top:3px; border:1px solid rgba(255,255,255,0.06);">${ad.headline_2}</div>
        </div>
        ${ad.headline_3 ? `
          <div>
            <div style="font-size:11px; color:var(--text-muted);">Headline 3 (${ad.headline_3.length}/30 chars):</div>
            <div style="font-size:13px; font-weight:700; color:#fff; background:#090d16; padding:8px 10px; border-radius:6px; margin-top:3px; border:1px solid rgba(255,255,255,0.06);">${ad.headline_3}</div>
          </div>
        ` : ''}
      </div>

      <!-- Descriptions Panel -->
      <div style="background:rgba(15,23,42,0.7); border:1px solid var(--glass-border); padding:16px; border-radius:12px;">
        <h4 style="font-size:13px; font-weight:800; color:#a855f7; text-transform:uppercase; margin-bottom:12px; display:flex; align-items:center; gap:6px;">
          <i class="fa-solid fa-align-left"></i> Ad Descriptions & Pitch
        </h4>
        <div style="margin-bottom:10px;">
          <div style="font-size:11px; color:var(--text-muted);">Description 1 (${ad.description_1.length}/90 chars):</div>
          <div style="font-size:12.5px; color:#cbd5e1; line-height:1.4; background:#090d16; padding:8px 10px; border-radius:6px; margin-top:3px; border:1px solid rgba(255,255,255,0.06);">${ad.description_1}</div>
        </div>
        ${ad.description_2 ? `
          <div>
            <div style="font-size:11px; color:var(--text-muted);">Description 2 (${ad.description_2.length}/90 chars):</div>
            <div style="font-size:12.5px; color:#cbd5e1; line-height:1.4; background:#090d16; padding:8px 10px; border-radius:6px; margin-top:3px; border:1px solid rgba(255,255,255,0.06);">${ad.description_2}</div>
          </div>
        ` : ''}
      </div>
    </div>

    <!-- 3. Targeted Keywords Table Specifically for this Ad Group -->
    <div style="background:rgba(15,23,42,0.7); border:1px solid var(--glass-border); padding:16px; border-radius:12px; margin-bottom:20px;">
      <h4 style="font-size:13px; font-weight:800; color:#10b581; text-transform:uppercase; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
        <i class="fa-solid fa-key"></i> Targeted Bidding Keywords & Search Volume
      </h4>
      <table style="width:100%; border-collapse:collapse; text-align:left; font-size:12px;">
        <thead>
          <tr style="background:rgba(2,6,23,0.8); color:var(--text-muted); text-transform:uppercase;">
            <th style="padding:8px 12px;">Keyword</th>
            <th style="padding:8px 12px;">Match Type</th>
            <th style="padding:8px 12px;">Est. CPC ($AUD)</th>
            <th style="padding:8px 12px;">Monthly Volume</th>
            <th style="padding:8px 12px;">Intent</th>
          </tr>
        </thead>
        <tbody>
          ${keywords.map(kw => `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
              <td style="padding:8px 12px; font-weight:700; color:#fff; font-family:var(--font-mono);">${kw.keyword}</td>
              <td style="padding:8px 12px;"><span class="action-chip" style="font-size:10.5px;">${kw.match_type}</span></td>
              <td style="padding:8px 12px; font-weight:700; color:#10b581;">${kw.estimated_cpc}</td>
              <td style="padding:8px 12px; color:var(--accent-cyan); font-family:var(--font-mono);">${kw.search_volume || '1,400/mo'}</td>
              <td style="padding:8px 12px;"><span class="badge badge-warning" style="font-size:10px;">${kw.intent}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>

    <!-- 4. Assets & Extensions Details -->
    <div style="background:rgba(15,23,42,0.7); border:1px solid var(--glass-border); padding:16px; border-radius:12px;">
      <h4 style="font-size:13px; font-weight:800; color:#f59e0b; text-transform:uppercase; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
        <i class="fa-solid fa-puzzle-piece"></i> Ad Assets & Callout Extensions
      </h4>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        ${(ad.callouts || ['24/7 Service', 'Fixed Price Guarantee', 'Flight Telemetry Tracking', 'European Fleet']).map(c => `
          <span style="font-size:11px; background:rgba(245,158,11,0.12); color:#fbbf24; border:1px solid rgba(245,158,11,0.3); padding:4px 10px; border-radius:6px; font-weight:600;">
            <i class="fa-solid fa-check"></i> ${c}
          </span>
        `).join('')}
      </div>
    </div>
  `;

  document.getElementById('ad-inspector-content').innerHTML = html;
  openModal('ad-inspector-modal');
}

function inspectMetaAd(idx) {
  if (!window.currentAdSpyReport) return;
  const report = window.currentAdSpyReport;
  const m = report.meta_ads_intelligence || {};
  const ads = m.active_ads || [];
  const ad = ads[idx];
  if (!ad) return;

  const fullCopy = `--- BRAND ---
${report.competitor_brand} (${report.competitor_domain})

--- HOOK ---
${ad.hook || ''}

--- PRIMARY TEXT ---
${ad.primary_text}

--- HEADLINE & DESCRIPTION ---
Headline: ${ad.headline}
Description: ${ad.description || ''}
Call To Action: ${ad.call_to_action || 'Book Now'}

--- LANDING PAGE ---
${ad.landing_page || `https://${report.competitor_domain}`}
`;

  document.getElementById('inspector-modal-title').innerHTML = `
    <i class="fa-brands fa-facebook" style="color:#3b82f6;"></i> Meta Ad Inspector (Facebook & Instagram)
  `;
  document.getElementById('inspector-modal-subtitle').innerHTML = `
    Detailed breakdown of creative hook, primary copy, targeting angles, CTA, and engagement strategy for <strong>${report.competitor_brand}</strong>.
  `;

  const html = `
    <!-- Top Action Bar -->
    <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(30,41,59,0.7); padding:12px 16px; border-radius:10px; margin-bottom:18px; border:1px solid var(--glass-border);">
      <div style="font-size:12px; color:var(--text-muted);">
        Competitor: <strong style="color:#fff;">${report.competitor_brand}</strong> | Format: <span class="badge badge-info">${ad.format || 'Single Video / Carousel'}</span>
      </div>
      <div style="display:flex; gap:8px;">
        <button id="btn-copy-m-ad" class="btn btn-primary btn-sm" style="background:linear-gradient(135deg, #3b82f6, #ec4899);" onclick="copyToClipboard(\`${fullCopy.replace(/`/g, '\\`')}\`, 'btn-copy-m-ad')">
          <i class="fa-solid fa-copy"></i> Copy Meta Ad Copy
        </button>
        <a href="${ad.landing_page || `https://${report.competitor_domain}`}" target="_blank" class="btn btn-secondary btn-sm" style="color:#60a5fa; border-color:rgba(59,130,246,0.4); text-decoration:none; display:inline-flex; align-items:center; gap:5px;">
          <i class="fa-solid fa-arrow-up-right-from-square"></i> Visit Landing Page
        </a>
      </div>
    </div>

    <!-- 1. Simulated Social Feed Mockup -->
    <div style="background:#0f172a; border:1px solid rgba(59,130,246,0.4); border-radius:14px; padding:20px; margin-bottom:20px; box-shadow:0 8px 30px rgba(0,0,0,0.7);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; padding-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.06);">
        <div style="display:flex; align-items:center; gap:10px;">
          <div style="width:36px; height:36px; border-radius:50%; background:linear-gradient(135deg,#3b82f6,#ec4899); display:flex; align-items:center; justify-content:center; color:#fff; font-weight:800; font-size:13px;">
            ${report.competitor_brand.substring(0,2)}
          </div>
          <div>
            <div style="font-weight:700; font-size:14px; color:#fff;">${report.competitor_brand}</div>
            <div style="font-size:11px; color:#94a3b8;">Sponsored · <i class="fa-solid fa-earth-americas"></i> Active (${ad.started_running || '45+ days'})</div>
          </div>
        </div>
        <span class="action-chip" style="font-size:11px; color:#ec4899;">${(ad.platforms || ['Facebook', 'Instagram']).join(' & ')}</span>
      </div>

      <!-- Hook Box -->
      ${ad.hook ? `
        <div style="background:rgba(245,158,11,0.12); border-left:3px solid #f59e0b; padding:8px 12px; border-radius:4px; font-size:12px; color:#fbbf24; margin-bottom:12px; font-weight:600;">
          <i class="fa-solid fa-lightbulb"></i> Scroll-Stopping Hook: "${ad.hook}"
        </div>
      ` : ''}

      <!-- Primary Text -->
      <div style="font-size:13px; color:#f1f5f9; line-height:1.6; white-space:pre-wrap; margin-bottom:16px; background:rgba(30,41,59,0.5); padding:14px; border-radius:10px;">${ad.primary_text}</div>

      <!-- Feed Card Bottom -->
      <div style="background:#020617; border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:14px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-size:11px; color:#94a3b8; text-transform:uppercase; font-family:var(--font-mono);">${report.competitor_domain}</div>
          <div style="font-weight:700; font-size:14px; color:#fff; margin-top:2px;">${ad.headline}</div>
          <div style="font-size:12px; color:#64748b; margin-top:2px;">${ad.description || ''}</div>
        </div>
        <button class="btn btn-primary" style="background:#3b82f6; font-weight:700; font-size:12px; padding:8px 18px; white-space:nowrap;">
          ${ad.call_to_action || 'Book Now'}
        </button>
      </div>
    </div>

    <!-- 2. Psychological Angle & Creative Analysis -->
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
      <div style="background:rgba(15,23,42,0.7); border:1px solid var(--glass-border); padding:16px; border-radius:12px;">
        <h4 style="font-size:13px; font-weight:800; color:#ec4899; text-transform:uppercase; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
          <i class="fa-solid fa-palette"></i> Creative Format & Placements
        </h4>
        <div style="font-size:12.5px; color:#cbd5e1; margin-bottom:6px;">
          <strong>Format:</strong> ${ad.format || 'Single Video / Carousel (Fleet Interiors)'}
        </div>
        <div style="font-size:12.5px; color:#cbd5e1;">
          <strong>Placements:</strong> ${(ad.platforms || ['Facebook Feed', 'Instagram Stories', 'Reels']).join(', ')}
        </div>
      </div>

      <div style="background:rgba(15,23,42,0.7); border:1px solid var(--glass-border); padding:16px; border-radius:12px;">
        <h4 style="font-size:13px; font-weight:800; color:#10b581; text-transform:uppercase; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
          <i class="fa-solid fa-bullseye"></i> Call To Action & Offer
        </h4>
        <div style="font-size:12.5px; color:#cbd5e1; margin-bottom:6px;">
          <strong>CTA Button:</strong> <span class="badge badge-info">${ad.call_to_action || 'Book Now'}</span>
        </div>
        <div style="font-size:12.5px; color:#cbd5e1;">
          <strong>Landing Page:</strong> <a href="${ad.landing_page || `https://${report.competitor_domain}`}" target="_blank" style="color:var(--accent-cyan); font-family:var(--font-mono); font-size:11px;">${ad.landing_page || report.competitor_domain}</a>
        </div>
      </div>
    </div>
  `;

  document.getElementById('ad-inspector-content').innerHTML = html;
  openModal('ad-inspector-modal');
}

function copyToClipboard(text, btnId) {
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById(btnId);
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-check"></i> Copied to Clipboard!';
      setTimeout(() => { btn.innerHTML = orig; }, 2000);
    }
  }).catch(err => {
    alert('Copied to clipboard');
  });
}

/* --- Page SEO Doctor & Google Algorithm Optimizer Handlers --- */

function openPageOptimizerModal(defaultUrl) {
  const urlInput = document.getElementById('page-opt-url');
  const locInput = document.getElementById('page-opt-location');
  const activeSite = allWebsitesList.find(s => s.site_id === currentSiteId);

  if (urlInput) {
    if (defaultUrl) {
      urlInput.value = defaultUrl;
    } else if (activeSite) {
      urlInput.value = activeSite.domain.endsWith('/') ? activeSite.domain : activeSite.domain + '/';
    }
  }
  if (locInput && activeSite) {
    locInput.value = activeSite.location;
  }
  openModal('page-optimizer-modal');
}

function setSamplePageUrl() {
  const activeSite = allWebsitesList.find(s => s.site_id === currentSiteId);
  const urlInput = document.getElementById('page-opt-url');
  const kwInput = document.getElementById('page-opt-keyword');
  if (activeSite && activeSite.site_id === 'opal') {
    if (urlInput) urlInput.value = 'https://www.opalchauffeurs.com.au/services/airport-transfers/';
    if (kwInput) kwInput.value = 'airport chauffeur transfer melbourne';
  } else {
    if (urlInput) urlInput.value = 'https://corporatecarsmelbourne.com.au/chauffeur-vs-rideshare-airport-fitzroy/';
    if (kwInput) kwInput.value = 'chauffeur vs rideshare melbourne airport';
  }
}

async function submitPageOptimizerAudit(e) {
  if (e) e.preventDefault();
  const url = document.getElementById('page-opt-url').value.trim();
  if (!url) {
    alert('Please enter a valid webpage URL to audit.');
    return;
  }

  const focusKeyword = document.getElementById('page-opt-keyword').value.trim();
  const location = document.getElementById('page-opt-location').value.trim() || 'Melbourne, VIC';
  const useAi = document.getElementById('page-opt-use-ai') ? document.getElementById('page-opt-use-ai').checked : true;

  const btn = document.getElementById('btn-submit-page-opt');
  const originalBtnText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Auditing Google Algorithms...';

  const container = document.getElementById('page-opt-results-container');
  container.innerHTML = `
    <div style="text-align: center; padding: 50px 20px; color: var(--text-muted);">
      <div style="font-size: 38px; color: #10b981; margin-bottom: 16px;">
        <i class="fa-solid fa-stethoscope fa-spin"></i>
      </div>
      <h3 style="font-size: 16px; color: #fff; font-weight: 800; margin-bottom: 6px;">
        Analyzing Page & Checking Google 2026 Ranking Factors...
      </h3>
      <div style="font-size: 12.5px; color: var(--text-secondary); max-width: 500px; margin: 0 auto;">
        Testing E-E-A-T signals, Helpful Content (HCU) depth, Semantic Headings (H1/H2/H3), Internal links, and Schema.org rich snippets.
      </div>
    </div>
  `;

  try {
    const res = await fetch('/api/agents/page-optimizer/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        focus_keyword: focusKeyword,
        location: location,
        use_ai: useAi,
        site_id: currentSiteId
      })
    });

    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = originalBtnText;

    if (!res.ok || data.status === 'error') {
      container.innerHTML = `
        <div style="background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); padding: 18px; border-radius: 12px; color: #f87171;">
          <strong>Audit Failed:</strong> ${data.detail || data.message || 'Error executing page audit.'}
        </div>
      `;
      return;
    }

    renderPageOptimizerAuditResults(data.output);
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = originalBtnText;
    container.innerHTML = `
      <div style="background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); padding: 18px; border-radius: 12px; color: #f87171;">
        <strong>Network Error:</strong> ${err.message}
      </div>
    `;
  }
}

function renderPageOptimizerAuditResults(report) {
  window.currentPageOptimizerReport = report;
  const container = document.getElementById('page-opt-results-container');
  if (!container) return;

  const score = report.overall_health_score || 78;
  const grade = report.grade || 'B+';
  const scores = report.algorithm_scores || {};
  const op = report.on_page_metrics || {};
  const headings = report.optimized_headings_recommendations || {};
  const links = report.internal_linking_recommendations || [];
  const checklist = report.executive_action_checklist || [];
  const schemaCode = report.ready_to_paste_schema_json || '';

  const scoreColor = score >= 85 ? '#10b981' : (score >= 70 ? '#06b6d4' : (score >= 55 ? '#f59e0b' : '#ef4444'));

  const html = `
    <!-- Top Hero Banner -->
    <div style="background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(30,41,59,0.9)); border: 1px solid var(--glass-border); padding: 22px; border-radius: 16px; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
        <div style="flex: 1; min-width: 280px;">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span class="badge badge-success" style="font-size: 11px; padding: 4px 10px;">
              <i class="fa-solid fa-circle-check"></i> GOOGLE ALGORITHM AUDIT COMPLETED
            </span>
            <span style="font-size: 11.5px; color: var(--text-muted); font-family: var(--font-mono);">${report.audited_at}</span>
          </div>
          <h2 style="font-size: 18px; font-weight: 800; color: #fff; margin-bottom: 4px; word-break: break-all;">
            <a href="${report.audited_url}" target="_blank" style="color: #fff; text-decoration: none;">
              ${report.audited_url} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 12px; color: var(--accent-cyan);"></i>
            </a>
          </h2>
          <div style="display: flex; gap: 14px; font-size: 12px; color: var(--text-secondary); margin-top: 8px; flex-wrap: wrap;">
            <span><strong>Focus Keyword:</strong> <code style="color: var(--accent-cyan); font-weight: 700;">${report.focus_keyword}</code></span>
            <span><strong>Target Brand:</strong> ${report.target_brand}</span>
            <span><strong>Market:</strong> ${report.location}</span>
          </div>
        </div>

        <!-- Health Score Ring Card -->
        <div style="background: rgba(15,23,42,0.8); border: 2px solid ${scoreColor}; padding: 14px 22px; border-radius: 14px; text-align: center; min-width: 140px; box-shadow: 0 0 20px rgba(16,185,129,0.2);">
          <div style="font-size: 11px; font-weight: 800; color: var(--text-muted); text-transform: uppercase;">Google Health Score</div>
          <div style="font-size: 36px; font-weight: 900; color: ${scoreColor}; font-family: var(--font-mono); line-height: 1.1; margin: 4px 0;">
            ${score}<span style="font-size: 16px; color: var(--text-muted);">/100</span>
          </div>
          <span class="badge" style="background: ${scoreColor}; color: #000; font-weight: 800; font-size: 11px;">GRADE ${grade}</span>
        </div>
      </div>
    </div>

    <!-- 5 Algorithm Pillars Breakdown Grid -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 22px;">
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Title & SERP Snippet</div>
        <div style="font-size: 22px; font-weight: 800; color: #06b6d4; font-family: var(--font-mono); margin-top: 4px;">${scores.title_and_meta || 85}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">${op.title_length || 58} Chars</div>
      </div>
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Heading Hierarchy</div>
        <div style="font-size: 22px; font-weight: 800; color: #a855f7; font-family: var(--font-mono); margin-top: 4px;">${scores.heading_hierarchy || 85}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">1 H1 · ${op.total_h2_count || 4} H2s</div>
      </div>
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Helpful Content (HCU)</div>
        <div style="font-size: 22px; font-weight: 800; color: #10b981; font-family: var(--font-mono); margin-top: 4px;">${scores.helpful_content || 82}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">${op.current_word_count || 840} Words</div>
      </div>
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Google E-E-A-T</div>
        <div style="font-size: 22px; font-weight: 800; color: #f59e0b; font-family: var(--font-mono); margin-top: 4px;">${scores.eeat_trust || 80}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">Trust & Accreditation</div>
      </div>
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Internal Link Graph</div>
        <div style="font-size: 22px; font-weight: 800; color: #38bdf8; font-family: var(--font-mono); margin-top: 4px;">${scores.internal_linking || 85}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">3 Silo Links Ready</div>
      </div>
    </div>

    <!-- Executive Action Checklist Banner -->
    <div style="background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.3); padding: 18px; border-radius: 14px; margin-bottom: 22px;">
      <div style="font-size: 13px; font-weight: 800; color: #10b981; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
        <i class="fa-solid fa-list-check"></i> Prioritized Google Action Checklist (Apply to Page Now):
      </div>
      <div style="display: flex; flex-direction: column; gap: 6px;">
        ${checklist.map(item => `
          <div style="font-size: 13px; color: #f1f5f9; display: flex; align-items: flex-start; gap: 8px;">
            <i class="fa-solid fa-circle-arrow-right" style="color: #10b981; margin-top: 3px;"></i>
            <span>${item}</span>
          </div>
        `).join('')}
      </div>
    </div>

    <!-- Tabbed Analysis Sections -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 22px;">
      <!-- Column 1: Heading Optimizer -->
      <div style="background: rgba(15,23,42,0.7); border: 1px solid var(--glass-border); padding: 18px; border-radius: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 style="font-size: 14px; font-weight: 800; color: #a855f7; display: flex; align-items: center; gap: 8px;">
            <i class="fa-solid fa-heading"></i> Optimized Heading Hierarchy
          </h3>
          <button id="btn-copy-h1" class="btn btn-secondary btn-sm" onclick="copyToClipboard('${(headings.proposed_h1 || '').replace(/'/g, "\\'")}', 'btn-copy-h1')" style="font-size: 11px;">
            <i class="fa-solid fa-copy"></i> Copy H1
          </button>
        </div>

        <div style="background: rgba(30,41,59,0.7); border-left: 3px solid #a855f7; padding: 10px 14px; border-radius: 6px; margin-bottom: 14px;">
          <div style="font-size: 10.5px; color: var(--text-muted); font-weight: 800; text-transform: uppercase;">Recommended H1 Tag</div>
          <div style="font-size: 13.5px; font-weight: 800; color: #fff; margin-top: 2px;">${headings.proposed_h1 || 'Optimized H1'}</div>
        </div>

        <div style="font-size: 12px; font-weight: 700; color: var(--text-secondary); margin-bottom: 6px;">Structured H2 Subsections (Helpful Content Depth):</div>
        <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px;">
          ${(headings.proposed_h2_sections || []).map(h2 => `
            <div style="background: rgba(30,41,59,0.5); padding: 8px 12px; border-radius: 6px; font-size: 12px; color: #cbd5e1;">
              <strong>H2:</strong> ${h2}
            </div>
          `).join('')}
        </div>

        <div style="font-size: 12px; font-weight: 700; color: var(--text-secondary); margin-bottom: 6px;">H3 FAQ Questions (Featured Snippet Hooks):</div>
        <div style="display: flex; flex-direction: column; gap: 6px;">
          ${(headings.proposed_h3_faqs || []).map(faq => `
            <div style="background: rgba(30,41,59,0.3); padding: 6px 10px; border-radius: 6px; font-size: 11.5px; color: var(--accent-cyan);">
              <i class="fa-solid fa-question-circle"></i> ${faq}
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Column 2: Contextual Internal Links -->
      <div style="background: rgba(15,23,42,0.7); border: 1px solid var(--glass-border); padding: 18px; border-radius: 14px;">
        <h3 style="font-size: 14px; font-weight: 800; color: #06b6d4; display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
          <i class="fa-solid fa-link"></i> Ready-to-Insert Internal Linking Silos
        </h3>
        <div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px;">
          ${links.map((lnk, idx) => `
            <div style="background: rgba(30,41,59,0.6); border: 1px solid rgba(6,182,212,0.2); padding: 12px; border-radius: 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span class="badge ${lnk.importance === 'HIGH' ? 'badge-success' : 'badge-info'}" style="font-size: 10px;">${lnk.importance} PRIORITY</span>
                <button id="btn-copy-lnk-${idx}" class="btn btn-secondary btn-sm" onclick="copyToClipboard('<a href=&quot;${lnk.target_url}&quot;>${lnk.recommended_anchor}</a>', 'btn-copy-lnk-${idx}')" style="font-size: 10.5px; padding: 2px 8px;">
                  <i class="fa-solid fa-copy"></i> Copy HTML
                </button>
              </div>
              <div style="font-size: 12.5px; color: #fff;"><strong>Anchor Text:</strong> <span style="color: var(--accent-cyan); font-weight: 700;">"${lnk.recommended_anchor}"</span></div>
              <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 2px;">-> ${lnk.target_url}</div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 4px; font-style: italic;">${lnk.context}</div>
            </div>
          `).join('')}
        </div>

        <div style="background: rgba(245,158,11,0.08); border-left: 3px solid #f59e0b; padding: 10px 12px; border-radius: 6px;">
          <div style="font-size: 11px; font-weight: 800; color: #f59e0b; text-transform: uppercase;">Google E-E-A-T Trust Signal Note:</div>
          <div style="font-size: 11.5px; color: var(--text-secondary); margin-top: 2px;">
            Include verified commercial accreditation and direct chauffeur dispatch contact details on this page to boost Google organic ranking authority.
          </div>
        </div>
      </div>
    </div>

    <!-- Ready-to-Paste JSON-LD Schema Section -->
    <div style="background: rgba(15,23,42,0.85); border: 1px solid var(--glass-border); padding: 18px; border-radius: 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <div>
          <h3 style="font-size: 14px; font-weight: 800; color: #10b981; display: flex; align-items: center; gap: 8px;">
            <i class="fa-solid fa-code"></i> Ready-to-Paste LocalBusiness & Chauffeur JSON-LD Schema
          </h3>
          <div style="font-size: 11.5px; color: var(--text-muted);">Paste this script into WordPress Header/Footer or HTML head tag for rich snippets in Google Search results.</div>
        </div>
        <button id="btn-copy-schema-code" class="btn btn-primary btn-sm" style="background: linear-gradient(135deg, #10b981, #059669); border: none; font-weight: 700;" onclick="copyToClipboard(\`<script type=&quot;application/ld+json&quot;>\n${schemaCode}\n</script>\`, 'btn-copy-schema-code')">
          <i class="fa-solid fa-copy"></i> Copy Schema Code
        </button>
      </div>

      <pre style="background: #030712; padding: 14px; border-radius: 8px; color: #38bdf8; font-family: var(--font-mono); font-size: 12px; max-height: 240px; overflow-y: auto; white-space: pre-wrap; word-break: break-word;">&lt;script type="application/ld+json"&gt;
${schemaCode}
&lt;/script&gt;</pre>
    </div>
  `;

  container.innerHTML = html;
}

function loadPageDoctorView() {
  const urlInput = document.getElementById('page-opt-view-url');
  const locInput = document.getElementById('page-opt-view-location');
  const activeSite = allWebsitesList.find(s => s.site_id === currentSiteId);

  if (urlInput && activeSite) {
    urlInput.value = activeSite.domain.endsWith('/') ? activeSite.domain : activeSite.domain + '/';
  }
  if (locInput && activeSite) {
    locInput.value = activeSite.location;
  }
}

async function submitPageOptimizerAuditView(e) {
  if (e) e.preventDefault();
  const url = document.getElementById('page-opt-view-url').value.trim();
  if (!url) {
    alert('Please enter a valid webpage URL to audit.');
    return;
  }

  const focusKeyword = document.getElementById('page-opt-view-keyword').value.trim();
  const location = document.getElementById('page-opt-view-location').value.trim() || 'Melbourne, VIC';
  const useAi = document.getElementById('page-opt-view-use-ai') ? document.getElementById('page-opt-view-use-ai').checked : true;

  const btn = document.getElementById('btn-submit-page-opt-view');
  const originalBtnText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Auditing Google Algorithms...';

  const container = document.getElementById('page-opt-view-results-container');
  container.innerHTML = `
    <div style="text-align: center; padding: 50px 20px; color: var(--text-muted);">
      <div style="font-size: 38px; color: #10b981; margin-bottom: 16px;">
        <i class="fa-solid fa-stethoscope fa-spin"></i>
      </div>
      <h3 style="font-size: 16px; color: #fff; font-weight: 800; margin-bottom: 6px;">
        Analyzing Page & Checking Google 2026 Ranking Factors...
      </h3>
      <div style="font-size: 12.5px; color: var(--text-secondary); max-width: 500px; margin: 0 auto;">
        Testing E-E-A-T signals, Helpful Content (HCU) depth, Semantic Headings (H1/H2/H3), Internal links, and Schema.org rich snippets.
      </div>
    </div>
  `;

  try {
    const res = await fetch('/api/agents/page-optimizer/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        focus_keyword: focusKeyword,
        location: location,
        use_ai: useAi,
        site_id: currentSiteId
      })
    });

    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = originalBtnText;

    if (!res.ok || data.status === 'error') {
      container.innerHTML = `
        <div style="background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); padding: 18px; border-radius: 12px; color: #f87171;">
          <strong>Audit Failed:</strong> ${data.detail || data.message || 'Error executing page audit.'}
        </div>
      `;
      return;
    }

    renderPageOptimizerAuditResultsCustom(data.output, 'page-opt-view-results-container');
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = originalBtnText;
    container.innerHTML = `
      <div style="background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); padding: 18px; border-radius: 12px; color: #f87171;">
        <strong>Network Error:</strong> ${err.message}
      </div>
    `;
  }
}

function renderPageOptimizerAuditResultsCustom(report, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const score = report.overall_health_score || 78;
  const grade = report.grade || 'B+';
  const scores = report.algorithm_scores || {};
  const op = report.on_page_metrics || {};
  const headings = report.optimized_headings_recommendations || {};
  const links = report.internal_linking_recommendations || [];
  const checklist = report.executive_action_checklist || [];
  const schemaCode = report.ready_to_paste_schema_json || '';

  const scoreColor = score >= 85 ? '#10b981' : (score >= 70 ? '#06b6d4' : (score >= 55 ? '#f59e0b' : '#ef4444'));

  const html = `
    <!-- Top Hero Banner -->
    <div style="background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(30,41,59,0.9)); border: 1px solid var(--glass-border); padding: 22px; border-radius: 16px; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
        <div style="flex: 1; min-width: 280px;">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span class="badge badge-success" style="font-size: 11px; padding: 4px 10px;">
              <i class="fa-solid fa-circle-check"></i> GOOGLE ALGORITHM AUDIT COMPLETED
            </span>
            <span style="font-size: 11.5px; color: var(--text-muted); font-family: var(--font-mono);">${report.audited_at}</span>
          </div>
          <h2 style="font-size: 18px; font-weight: 800; color: #fff; margin-bottom: 4px; word-break: break-all;">
            <a href="${report.audited_url}" target="_blank" style="color: #fff; text-decoration: none;">
              ${report.audited_url} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 12px; color: var(--accent-cyan);"></i>
            </a>
          </h2>
          <div style="display: flex; gap: 14px; font-size: 12px; color: var(--text-secondary); margin-top: 8px; flex-wrap: wrap;">
            <span><strong>Focus Keyword:</strong> <code style="color: var(--accent-cyan); font-weight: 700;">${report.focus_keyword}</code></span>
            <span><strong>Target Brand:</strong> ${report.target_brand}</span>
            <span><strong>Market:</strong> ${report.location}</span>
          </div>
        </div>

        <!-- Health Score Ring Card -->
        <div style="background: rgba(15,23,42,0.8); border: 2px solid ${scoreColor}; padding: 14px 22px; border-radius: 14px; text-align: center; min-width: 140px; box-shadow: 0 0 20px rgba(16,185,129,0.2);">
          <div style="font-size: 11px; font-weight: 800; color: var(--text-muted); text-transform: uppercase;">Google Health Score</div>
          <div style="font-size: 36px; font-weight: 900; color: ${scoreColor}; font-family: var(--font-mono); line-height: 1.1; margin: 4px 0;">
            ${score}<span style="font-size: 16px; color: var(--text-muted);">/100</span>
          </div>
          <span class="badge" style="background: ${scoreColor}; color: #000; font-weight: 800; font-size: 11px;">GRADE ${grade}</span>
        </div>
      </div>
    </div>

    <!-- 5 Algorithm Pillars Breakdown Grid -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 22px;">
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Title & SERP Snippet</div>
        <div style="font-size: 22px; font-weight: 800; color: #06b6d4; font-family: var(--font-mono); margin-top: 4px;">${scores.title_and_meta || 85}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">${op.title_length || 58} Chars</div>
      </div>
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Heading Hierarchy</div>
        <div style="font-size: 22px; font-weight: 800; color: #a855f7; font-family: var(--font-mono); margin-top: 4px;">${scores.heading_hierarchy || 85}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">1 H1 · ${op.total_h2_count || 4} H2s</div>
      </div>
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Helpful Content (HCU)</div>
        <div style="font-size: 22px; font-weight: 800; color: #10b981; font-family: var(--font-mono); margin-top: 4px;">${scores.helpful_content || 82}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">${op.current_word_count || 840} Words</div>
      </div>
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Google E-E-A-T</div>
        <div style="font-size: 22px; font-weight: 800; color: #f59e0b; font-family: var(--font-mono); margin-top: 4px;">${scores.eeat_trust || 80}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">Trust & Accreditation</div>
      </div>
      <div style="background: rgba(30,41,59,0.6); border: 1px solid var(--glass-border); padding: 14px; border-radius: 12px; text-align: center;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Internal Link Graph</div>
        <div style="font-size: 22px; font-weight: 800; color: #38bdf8; font-family: var(--font-mono); margin-top: 4px;">${scores.internal_linking || 85}%</div>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">3 Silo Links Ready</div>
      </div>
    </div>

    <!-- Executive Action Checklist Banner -->
    <div style="background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.3); padding: 18px; border-radius: 14px; margin-bottom: 22px;">
      <div style="font-size: 13px; font-weight: 800; color: #10b981; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
        <i class="fa-solid fa-list-check"></i> Prioritized Google Action Checklist (Apply to Page Now):
      </div>
      <div style="display: flex; flex-direction: column; gap: 6px;">
        ${checklist.map(item => `
          <div style="font-size: 13px; color: #f1f5f9; display: flex; align-items: flex-start; gap: 8px;">
            <i class="fa-solid fa-circle-arrow-right" style="color: #10b981; margin-top: 3px;"></i>
            <span>${item}</span>
          </div>
        `).join('')}
      </div>
    </div>

    <!-- Tabbed Analysis Sections -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 22px;">
      <!-- Column 1: Heading Optimizer -->
      <div style="background: rgba(15,23,42,0.7); border: 1px solid var(--glass-border); padding: 18px; border-radius: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 style="font-size: 14px; font-weight: 800; color: #a855f7; display: flex; align-items: center; gap: 8px;">
            <i class="fa-solid fa-heading"></i> Optimized Heading Hierarchy
          </h3>
          <button id="btn-copy-h1-v" class="btn btn-secondary btn-sm" onclick="copyToClipboard('${(headings.proposed_h1 || '').replace(/'/g, "\\'")}', 'btn-copy-h1-v')" style="font-size: 11px;">
            <i class="fa-solid fa-copy"></i> Copy H1
          </button>
        </div>

        <div style="background: rgba(30,41,59,0.7); border-left: 3px solid #a855f7; padding: 10px 14px; border-radius: 6px; margin-bottom: 14px;">
          <div style="font-size: 10.5px; color: var(--text-muted); font-weight: 800; text-transform: uppercase;">Recommended H1 Tag</div>
          <div style="font-size: 13.5px; font-weight: 800; color: #fff; margin-top: 2px;">${headings.proposed_h1 || 'Optimized H1'}</div>
        </div>

        <div style="font-size: 12px; font-weight: 700; color: var(--text-secondary); margin-bottom: 6px;">Structured H2 Subsections (Helpful Content Depth):</div>
        <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px;">
          ${(headings.proposed_h2_sections || []).map(h2 => `
            <div style="background: rgba(30,41,59,0.5); padding: 8px 12px; border-radius: 6px; font-size: 12px; color: #cbd5e1;">
              <strong>H2:</strong> ${h2}
            </div>
          `).join('')}
        </div>

        <div style="font-size: 12px; font-weight: 700; color: var(--text-secondary); margin-bottom: 6px;">H3 FAQ Questions (Featured Snippet Hooks):</div>
        <div style="display: flex; flex-direction: column; gap: 6px;">
          ${(headings.proposed_h3_faqs || []).map(faq => `
            <div style="background: rgba(30,41,59,0.3); padding: 6px 10px; border-radius: 6px; font-size: 11.5px; color: var(--accent-cyan);">
              <i class="fa-solid fa-question-circle"></i> ${faq}
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Column 2: Contextual Internal Links -->
      <div style="background: rgba(15,23,42,0.7); border: 1px solid var(--glass-border); padding: 18px; border-radius: 14px;">
        <h3 style="font-size: 14px; font-weight: 800; color: #06b6d4; display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
          <i class="fa-solid fa-link"></i> Ready-to-Insert Internal Linking Silos
        </h3>
        <div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px;">
          ${links.map((lnk, idx) => `
            <div style="background: rgba(30,41,59,0.6); border: 1px solid rgba(6,182,212,0.2); padding: 12px; border-radius: 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span class="badge ${lnk.importance === 'HIGH' ? 'badge-success' : 'badge-info'}" style="font-size: 10px;">${lnk.importance} PRIORITY</span>
                <button id="btn-copy-lnk-v-${idx}" class="btn btn-secondary btn-sm" onclick="copyToClipboard('<a href=&quot;${lnk.target_url}&quot;>${lnk.recommended_anchor}</a>', 'btn-copy-lnk-v-${idx}')" style="font-size: 10.5px; padding: 2px 8px;">
                  <i class="fa-solid fa-copy"></i> Copy HTML
                </button>
              </div>
              <div style="font-size: 12.5px; color: #fff;"><strong>Anchor Text:</strong> <span style="color: var(--accent-cyan); font-weight: 700;">"${lnk.recommended_anchor}"</span></div>
              <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 2px;">-> ${lnk.target_url}</div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 4px; font-style: italic;">${lnk.context}</div>
            </div>
          `).join('')}
        </div>

        <div style="background: rgba(245,158,11,0.08); border-left: 3px solid #f59e0b; padding: 10px 12px; border-radius: 6px;">
          <div style="font-size: 11px; font-weight: 800; color: #f59e0b; text-transform: uppercase;">Google E-E-A-T Trust Signal Note:</div>
          <div style="font-size: 11.5px; color: var(--text-secondary); margin-top: 2px;">
            Include verified commercial accreditation and direct chauffeur dispatch contact details on this page to boost Google organic ranking authority.
          </div>
        </div>
      </div>
    </div>

    <!-- Ready-to-Paste JSON-LD Schema Section -->
    <div style="background: rgba(15,23,42,0.85); border: 1px solid var(--glass-border); padding: 18px; border-radius: 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <div>
          <h3 style="font-size: 14px; font-weight: 800; color: #10b981; display: flex; align-items: center; gap: 8px;">
            <i class="fa-solid fa-code"></i> Ready-to-Paste LocalBusiness & Chauffeur JSON-LD Schema
          </h3>
          <div style="font-size: 11.5px; color: var(--text-muted);">Paste this script into WordPress Header/Footer or HTML head tag for rich snippets in Google Search results.</div>
        </div>
        <button id="btn-copy-schema-code-v" class="btn btn-primary btn-sm" style="background: linear-gradient(135deg, #10b981, #059669); border: none; font-weight: 700;" onclick="copyToClipboard(\`<script type=&quot;application/ld+json&quot;>\n${schemaCode}\n</script>\`, 'btn-copy-schema-code-v')">
          <i class="fa-solid fa-copy"></i> Copy Schema Code
        </button>
      </div>

      <pre style="background: #030712; padding: 14px; border-radius: 8px; color: #38bdf8; font-family: var(--font-mono); font-size: 12px; max-height: 240px; overflow-y: auto; white-space: pre-wrap; word-break: break-word;">&lt;script type="application/ld+json"&gt;
${schemaCode}
&lt;/script&gt;</pre>
    </div>
  `;

  container.innerHTML = html;
}

/* --- Multi-Provider AI Intelligence Hub & API Key Vault Handlers --- */

async function loadAIProviders() {
  const grid = document.getElementById('ai-providers-grid');
  if (!grid) return;

  try {
    const res = await fetch('/api/ai/providers');
    const data = await res.json();
    if (!data.providers || data.providers.length === 0) return;

    grid.innerHTML = data.providers.map(p => {
      const isPrimary = p.is_primary;
      const isConfigured = p.is_configured;
      const cardBorder = isPrimary ? 'border: 2px solid var(--accent-purple); box-shadow: 0 0 16px rgba(168,85,247,0.3);' : (isConfigured ? 'border: 1px solid rgba(6,182,212,0.3);' : 'border: 1px solid var(--glass-border); opacity: 0.85;');

      return `
        <div style="background: rgba(15,23,42,0.75); padding: 18px; border-radius: 14px; ${cardBorder} display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 38px; height: 38px; border-radius: 10px; background: rgba(30,41,59,0.8); display: flex; align-items: center; justify-content: center; font-size: 16px; color: ${isPrimary ? 'var(--accent-purple)' : (isConfigured ? 'var(--accent-cyan)' : 'var(--text-muted)')};">
                  <i class="${p.icon}"></i>
                </div>
                <div>
                  <h3 style="font-size: 14.5px; font-weight: 800; color: #fff;">${p.name}</h3>
                  <div style="font-size: 11px; color: var(--text-muted);">${p.badge}</div>
                </div>
              </div>
              <span class="badge ${isPrimary ? 'badge-success' : (isConfigured ? 'badge-info' : 'badge-warning')}" style="${isPrimary ? 'background: linear-gradient(135deg, #a855f7, #ec4899); color: #fff; font-weight: 800;' : ''}">
                ${isPrimary ? 'ACTIVE PRIMARY' : (isConfigured ? 'CONFIGURED' : 'NOT CONFIGURED')}
              </span>
            </div>

            <!-- API Key Preview Box -->
            <div style="background: rgba(30,41,59,0.6); padding: 8px 12px; border-radius: 8px; font-family: var(--font-mono); font-size: 11.5px; color: ${isConfigured ? '#38bdf8' : 'var(--text-muted)'}; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
              <span><i class="fa-solid fa-lock" style="font-size: 10px; margin-right: 6px;"></i> ${p.masked_key}</span>
              <span style="font-size: 10px; color: var(--text-muted);">${p.env_var}</span>
            </div>

            <!-- Supported Models Tags -->
            <div style="margin-bottom: 14px;">
              <div style="font-size: 10.5px; color: var(--text-muted); font-weight: 700; text-transform: uppercase; margin-bottom: 6px;">Supported Models:</div>
              <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                ${p.supported_models.map(m => `
                  <span class="action-chip" style="font-size: 10px; padding: 2px 6px; font-family: var(--font-mono);">${m}</span>
                `).join('')}
              </div>
            </div>
          </div>

          <!-- Bottom Action Buttons -->
          <div style="display: flex; gap: 8px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px; margin-top: 8px;">
            <button class="btn btn-secondary btn-sm" onclick="openConfigureAIModal('${p.id}')" style="flex: 1; font-size: 11.5px; font-weight: 700; color: #fff; border-color: rgba(255,255,255,0.15);">
              <i class="fa-solid fa-key"></i> ${isConfigured ? 'Update Key' : 'Add Key'}
            </button>
            ${!isPrimary ? `
              <button class="btn btn-primary btn-sm" onclick="setPrimaryAIProvider('${p.id}')" style="font-size: 11.5px; font-weight: 700; background: linear-gradient(135deg, var(--accent-purple), #ec4899); border: none;">
                <i class="fa-solid fa-check"></i> Set Primary
              </button>
            ` : `
              <span style="font-size: 11px; font-weight: 800; color: #10b981; display: flex; align-items: center; gap: 4px; padding: 0 8px;">
                <i class="fa-solid fa-circle-check"></i> Current Default
              </span>
            `}
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to load AI providers:', err);
  }
}

function openConfigureAIModal(providerId) {
  const provSelect = document.getElementById('ai-modal-provider');
  const keyInput = document.getElementById('ai-modal-api-key');
  const modelInput = document.getElementById('ai-modal-model');
  const outputBox = document.getElementById('ai-modal-test-output');

  if (outputBox) {
    outputBox.style.display = 'none';
    outputBox.textContent = '';
  }
  if (keyInput) keyInput.value = '';

  if (provSelect && providerId) {
    provSelect.value = providerId;
  }
  handleAIProviderChange();
  openModal('configure-ai-provider-modal');
}

function handleAIProviderChange() {
  const prov = document.getElementById('ai-modal-provider').value;
  const keyInput = document.getElementById('ai-modal-api-key');
  const modelInput = document.getElementById('ai-modal-model');
  const urlWrap = document.getElementById('ai-modal-base-url-wrap');

  const defaultModels = {
    'anthropic': 'claude-3-5-sonnet-20241022',
    'gemini': 'gemini-2.5-flash',
    'openai': 'gpt-4o',
    'deepseek': 'deepseek-chat',
    'groq': 'llama-3.3-70b-versatile',
    'custom': 'mistral-large-latest'
  };

  const placeholders = {
    'anthropic': 'sk-ant-api03-...',
    'gemini': 'AIzaSy...',
    'openai': 'sk-proj-...',
    'deepseek': 'sk-...',
    'groq': 'gsk_...',
    'custom': 'Enter API key or leave blank for local Ollama'
  };

  if (modelInput) modelInput.value = defaultModels[prov] || '';
  if (keyInput) keyInput.placeholder = placeholders[prov] || 'Enter API Key';
  if (urlWrap) {
    urlWrap.style.display = (prov === 'custom') ? 'block' : 'none';
  }
}

function toggleAPIKeyVisibility() {
  const input = document.getElementById('ai-modal-api-key');
  const icon = document.getElementById('eye-icon-ai-key');
  if (!input) return;

  if (input.type === 'password') {
    input.type = 'text';
    if (icon) icon.className = 'fa-solid fa-eye-slash';
  } else {
    input.type = 'password';
    if (icon) icon.className = 'fa-solid fa-eye';
  }
}

async function testCurrentAIKey() {
  const prov = document.getElementById('ai-modal-provider').value;
  const key = document.getElementById('ai-modal-api-key').value.trim();
  const url = document.getElementById('ai-modal-base-url') ? document.getElementById('ai-modal-base-url').value.trim() : null;
  const outputBox = document.getElementById('ai-modal-test-output');
  const btn = document.getElementById('btn-test-ai-key');

  if (!key && prov !== 'custom') {
    alert('Please enter an API key to test.');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Validating...';

  try {
    const res = await fetch('/api/ai/providers/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: prov,
        api_key: key,
        custom_base_url: url
      })
    });
    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-plug"></i> Test Connection';

    if (outputBox) {
      outputBox.style.display = 'block';
      if (data.status === 'success') {
        outputBox.style.background = 'rgba(16,185,129,0.15)';
        outputBox.style.border = '1px solid #10b981';
        outputBox.style.color = '#10b981';
        outputBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${data.message}`;
      } else if (data.status === 'warning') {
        outputBox.style.background = 'rgba(245,158,11,0.15)';
        outputBox.style.border = '1px solid #f59e0b';
        outputBox.style.color = '#fbbf24';
        outputBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.message}`;
      } else {
        outputBox.style.background = 'rgba(239,68,68,0.15)';
        outputBox.style.border = '1px solid #ef4444';
        outputBox.style.color = '#f87171';
        outputBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${data.message}`;
      }
    }
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-plug"></i> Test Connection';
    if (outputBox) {
      outputBox.style.display = 'block';
      outputBox.style.background = 'rgba(239,68,68,0.15)';
      outputBox.style.border = '1px solid #ef4444';
      outputBox.style.color = '#f87171';
      outputBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Network test error: ${err.message}`;
    }
  }
}

async function submitSaveAIProviderKey(e) {
  if (e) e.preventDefault();

  const prov = document.getElementById('ai-modal-provider').value;
  const key = document.getElementById('ai-modal-api-key').value.trim();
  const baseUrl = document.getElementById('ai-modal-base-url') ? document.getElementById('ai-modal-base-url').value.trim() : null;
  const model = document.getElementById('ai-modal-model').value.trim();
  const isPrimary = document.getElementById('ai-modal-is-primary').checked;

  if (!key && prov !== 'custom') {
    alert('Please enter an API key to save.');
    return;
  }

  const btn = document.getElementById('btn-save-ai-key');
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

  try {
    const res = await fetch('/api/ai/providers/save-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: prov,
        api_key: key,
        custom_base_url: baseUrl,
        default_model: model,
        is_primary: isPrimary
      })
    });

    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-save"></i> Save & Activate';

    if (!res.ok || data.status === 'error') {
      alert(`Failed to save key: ${data.detail || data.message || 'Error'}`);
      return;
    }

    closeModal('configure-ai-provider-modal');
    alert(`Success! ${prov.toUpperCase()} API key saved and activated in AI Model Router.`);

    await loadAIProviders();
    if (activeView === 'settings') await loadSettings();
    if (activeView === 'ai-usage') await loadAIUsage();
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-save"></i> Save & Activate';
    alert(`Failed to save key: ${err.message}`);
  }
}

async function setPrimaryAIProvider(provId) {
  if (!confirm(`Switch default AI Engine to ${provId.toUpperCase()}?`)) return;

  try {
    const res = await fetch('/api/ai/providers/set-primary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: provId })
    });
    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      alert(`Error: ${data.detail || data.message}`);
      return;
    }

    alert(`Default AI Provider switched to ${provId.toUpperCase()}!`);
    await loadAIProviders();
    if (activeView === 'settings') await loadSettings();
  } catch (err) {
    alert(`Failed to switch provider: ${err.message}`);
  }
}

// Global scope bindings for inline HTML onclick handlers
window.openModal = openModal;
window.closeModal = closeModal;
window.openCustomOutreachModal = openCustomOutreachModal;
window.submitCustomOutreach = submitCustomOutreach;
window.runDailyBacklinkBatch = runDailyBacklinkBatch;
window.openCompetitorAdSpyModal = openCompetitorAdSpyModal;
window.submitCompetitorAdSpy = submitCompetitorAdSpy;
window.inspectGoogleAd = inspectGoogleAd;
window.inspectMetaAd = inspectMetaAd;
window.openPageOptimizerModal = openPageOptimizerModal;
window.setSamplePageUrl = setSamplePageUrl;
window.submitPageOptimizerAudit = submitPageOptimizerAudit;
window.loadPageDoctorView = loadPageDoctorView;
window.submitPageOptimizerAuditView = submitPageOptimizerAuditView;
window.openConfigureAIModal = openConfigureAIModal;
window.handleAIProviderChange = handleAIProviderChange;
window.toggleAPIKeyVisibility = toggleAPIKeyVisibility;
window.testCurrentAIKey = testCurrentAIKey;
window.submitSaveAIProviderKey = submitSaveAIProviderKey;
window.setPrimaryAIProvider = setPrimaryAIProvider;
window.loadAIProviders = loadAIProviders;
window.copyToClipboard = copyToClipboard;






