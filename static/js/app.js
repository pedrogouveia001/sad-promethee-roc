/**
 * B3 SmarterInvestor — Main Client Application Orchestrator
 * Integrates SmarterUI, Dashboard, AppCharts and performs all REST API coordination.
 */

const App = {
  problemId: null,

  async init() {
    // 1. Setup Tab Switching Navigation
    this.setupNavigation();
    
    // 2. Initialize Decision Problem Session
    await this.initDecisionProblem();
    
    // 3. Load UI Components
    PrometheeUI.init();
    Dashboard.init();
    
    // 4. Load Initial Data
    await this.loadSystemStatus();
    await Dashboard.loadSectors();
    await PrometheeUI.loadCriteria();
    await this.refreshDecisionMatrixView();
    
    // 5. Setup Action Buttons
    this.setupActionListeners();

    // 6. Update nav badge
    this.updateCompanyBadge();

    // 7. Setup Mobile Menu
    this.setupMobileMenu();
  },

  /**
   * Toast notification system — replaces browser alerts for a premium UX
   */
  showToast(type, title, message, duration = 5000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
      success: 'fa-solid fa-circle-check',
      error: 'fa-solid fa-circle-xmark',
      warning: 'fa-solid fa-triangle-exclamation',
      info: 'fa-solid fa-circle-info'
    };

    toast.innerHTML = `
      <i class="toast-icon ${icons[type] || icons.info}"></i>
      <div class="toast-content">
        <div class="toast-title">${title}</div>
        ${message ? `<div class="toast-message">${message}</div>` : ''}
      </div>
      <button class="toast-close"><i class="fa-solid fa-xmark"></i></button>
    `;

    toast.querySelector('.toast-close').addEventListener('click', () => {
      toast.classList.add('toast-exit');
      setTimeout(() => toast.remove(), 300);
    });

    container.appendChild(toast);

    // Auto-dismiss
    setTimeout(() => {
      if (toast.parentNode) {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
      }
    }, duration);
  },

  /**
   * Update the company count badge in navigation
   */
  updateCompanyBadge() {
    const badge = document.getElementById('nav-badge-companies');
    const count = Dashboard.selectedTickers.size;
    if (count > 0) {
      badge.style.display = 'inline';
      badge.textContent = count;
    } else {
      badge.style.display = 'none';
    }
  },

  /**
   * Simple client-side router for switching active divs
   */
  setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', (e) => {
        const nav = e.currentTarget;
        const tab = nav.dataset.tab;
        
        // Remove active class from navigation menus
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        nav.classList.add('active');
        
        // Hide all tabs, show target tab
        document.querySelectorAll('.tab-content').forEach(content => {
          content.classList.remove('active');
        });
        
        const targetTab = document.getElementById(`tab-${tab}`);
        if (targetTab) {
          targetTab.classList.add('active');
        }

        // Update header headers
        const pageTitle = document.getElementById('page-title');
        const pageSubtitle = document.getElementById('page-subtitle');

        const headers = {
          'dashboard': ['Dashboard', 'Visão geral do mercado e desempenho multicritério'],
          'alternatives': ['Seleção de Empresas', 'Selecione as empresas da B3 estruturadas por setores comerciais'],
          'promethee': ['Análise PROMETHEE', 'Ordene os critérios de decisão fundamentalistas e calcule os pesos ROC'],
          'analysis': ['Séries Temporais', 'Avalie a associação estatística entre o Valor Global e o Preço Histórico'],
          'recommendations': ['Recomendações', 'Recomendações e scores de investimento baseados nas correlações']
        };

        if (headers[tab]) {
          pageTitle.textContent = headers[tab][0];
          pageSubtitle.textContent = headers[tab][1];
        }

        // Trigger context re-loads if user moves to specific tabs
        if (tab === 'dashboard') {
          this.refreshDashboardData();
        } else if (tab === 'recommendations') {
          this.loadRecommendations();
        } else if (tab === 'promethee') {
          this.refreshDecisionMatrixView();
        }

        // Close mobile sidebar on navigation
        this.closeMobileSidebar();
      });
    });
  },

  /**
   * Mobile hamburger menu toggle
   */
  setupMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const openBtn = document.getElementById('mobile-menu-btn');
    const closeBtn = document.getElementById('mobile-menu-close');
    const overlay = document.getElementById('drawer-overlay');

    if (openBtn) {
      openBtn.addEventListener('click', () => {
        sidebar.classList.add('open');
        // Reuse drawer overlay for sidebar backdrop
        overlay.classList.add('active');
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.closeMobileSidebar());
    }

    // Close sidebar when clicking overlay (only if sidebar is open)
    if (overlay) {
      overlay.addEventListener('click', () => {
        if (sidebar.classList.contains('open')) {
          this.closeMobileSidebar();
        }
      });
    }
  },

  closeMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('drawer-overlay');
    sidebar.classList.remove('open');
    // Only remove overlay if the company drawer is not open
    const drawer = document.getElementById('company-detail-drawer');
    if (!drawer.classList.contains('open')) {
      overlay.classList.remove('active');
    }
  },

  /**
   * Set up or retrieve Flask database DecisionProblem ID session from localStorage
   */
  async initDecisionProblem() {
    let storedId = localStorage.getItem('current_decision_problem_id');
    
    if (!storedId) {
      try {
        const res = await fetch('/api/decision', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: 'Análise de Investimentos Principal',
            description: 'Análise multicritério fundamentalista B3'
          })
        });
        const problem = await res.json();
        storedId = problem.id;
        localStorage.setItem('current_decision_problem_id', storedId);
      } catch (err) {
        console.error("Failed to create decision problem session:", err);
      }
    }
    
    this.problemId = parseInt(storedId);
    console.log(`Using decision problem ID: ${this.problemId}`);

    // If decision problem is set up, load selection checkboxes inside sector tree if already saved
    await this.restoreSavedAlternatives();
  },

  /**
   * Restore alternative checkboxes on reload
   */
  async restoreSavedAlternatives() {
    if (!this.problemId) return;

    try {
      const res = await fetch(`/api/decision/${this.problemId}`);
      if (!res.ok) return;
      const data = await res.json();

      if (data.alternatives && data.alternatives.length > 0) {
        Dashboard.selectedTickers = new Set(data.alternatives.map(a => a.company ? a.company.ticker : null).filter(t => t));
      }
    } catch (e) {
      console.warn("Could not restore saved alternatives:", e);
    }
  },

  async loadSystemStatus() {
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');

    try {
      const res = await fetch('/api/system/status');
      const data = await res.json();
      
      statusDot.className = 'status-indicator';
      statusText.textContent = `Online | ${data.companies} empresas`;
    } catch (e) {
      statusDot.className = 'status-indicator offline';
      statusText.textContent = 'Servidor Offline';
    }
  },

  setupActionListeners() {
    // 1. Data Sync Button
    const syncBtn = document.getElementById('sync-data-btn');
    syncBtn.addEventListener('click', async () => {
      syncBtn.disabled = true;
      syncBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Sincronizando...`;
      
      try {
        // Collect data for a few free/test tickers to prevent brapi.dev quota exhaust in dev mode
        const res = await fetch('/api/system/collect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tickers: ['PETR4', 'VALE3', 'ITUB4', 'MGLU3', 'WEGE3', 'BBAS3', 'B3SA3', 'ABEV3', 'GGBR4', 'RENT3']
          })
        });

        if (res.ok) {
          const stats = await res.json();
          this.showToast('success', 'Sincronização Concluída', 
            `${stats.total} empresas sincronizadas | Indicadores: ${stats.indicators_success} | Preços: ${stats.prices_success}`);
          await this.loadSystemStatus();
          await Dashboard.loadSectors();
        } else {
          this.showToast('error', 'Erro na Sincronização', 'Não foi possível concluir a sincronização de dados.');
        }
      } catch (e) {
        console.error(e);
        this.showToast('error', 'Falha de Conexão', 'Não foi possível conectar ao servidor.');
      } finally {
        syncBtn.disabled = false;
        syncBtn.innerHTML = `<i class="fa-solid fa-rotate"></i> Sincronizar Dados`;
      }
    });

    // 2. PROMETHEE Calculation trigger
    const calcBtn = document.getElementById('calculate-promethee-btn');
    calcBtn.addEventListener('click', async () => {
      if (Dashboard.selectedTickers.size === 0) {
        this.showToast('warning', 'Nenhuma Empresa Selecionada', 
          'Selecione pelo menos uma empresa na aba "Empresas" antes de calcular.');
        return;
      }

      calcBtn.disabled = true;
      calcBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Calculando...`;

      try {
        // Step A: Save criteria ranks first
        const criteriaData = PrometheeUI.getCriteriaDataForSubmit();
        const criteriaRes = await fetch(`/api/decision/${this.problemId}/criteria`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ criteria: criteriaData })
        });
        if (!criteriaRes.ok) throw new Error("Falha ao atualizar critérios no servidor");

        // Step B: Save selected alternatives
        const altRes = await fetch(`/api/decision/${this.problemId}/alternatives`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tickers: [...Dashboard.selectedTickers] })
        });
        if (!altRes.ok) throw new Error("Falha ao atualizar empresas no servidor");

        // Step C: Trigger calculations
        const runRes = await fetch(`/api/decision/${this.problemId}/calculate`, {
          method: 'POST'
        });
        const summary = await runRes.json();

        if (summary.error) {
          this.showToast('error', 'Erro no Cálculo', summary.error);
        } else {
          this.showToast('success', 'Cálculos Finalizados!', 
            `${summary.total_calculated} registros calculados com sucesso para ${summary.companies} empresas.`);
          
          // Update workflow step indicator
          this.updateWorkflowStep(3);
          
          // Refresh decision matrix rendering
          await this.refreshDecisionMatrixView();
        }
      } catch (err) {
        console.error(err);
        this.showToast('error', 'Erro no Processamento', err.message);
      } finally {
        calcBtn.disabled = false;
        calcBtn.innerHTML = `<i class="fa-solid fa-calculator"></i> Calcular Valores Globais`;
      }
    });

    // 3. Run Statistical Analysis button (Analysis tab)
    const runAnalysisBtn = document.getElementById('run-analysis-btn');
    runAnalysisBtn.addEventListener('click', async () => {
      const windowSelect = document.getElementById('analysis-window');
      const companySelect = document.getElementById('analysis-company-select');
      const selectedTicker = companySelect.value;
      const windowDays = parseInt(windowSelect.value);

      if (!selectedTicker) {
        this.showToast('warning', 'Empresa Não Selecionada', 
          'Selecione uma empresa para visualizar a série temporal.');
        return;
      }

      runAnalysisBtn.disabled = true;
      runAnalysisBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Analisando...`;

      try {
        // First run analysis for all selected alternatives
        const runRes = await fetch(`/api/analysis/${this.problemId}/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ window_days: windowDays })
        });
        
        if (!runRes.ok) throw new Error("Erro ao executar análise estatística");

        // Fetch dual timeseries charts
        await this.loadAndRenderTimeseries(selectedTicker);
        
        // Fetch scatter plot charts
        await this.loadAndRenderScatterPlot(selectedTicker);

        // Fetch recommendations scorecard to show correlation metrics
        await this.loadSingleAnalysisStats(selectedTicker);

        this.showToast('success', 'Análise Concluída', 
          `Análise temporal de ${selectedTicker} (${windowDays} dias) finalizada.`);

      } catch (e) {
        console.error(e);
        this.showToast('error', 'Erro na Análise', e.message);
      } finally {
        runAnalysisBtn.disabled = false;
        runAnalysisBtn.innerHTML = `<i class="fa-solid fa-play"></i> Analisar`;
      }
    });
  },

  /**
   * Update workflow step indicators
   */
  updateWorkflowStep(completedStep) {
    for (let i = 1; i <= 4; i++) {
      const el = document.getElementById(`step-${i}`);
      if (!el) continue;
      el.classList.remove('active', 'completed');
      if (i < completedStep) {
        el.classList.add('completed');
      } else if (i === completedStep) {
        el.classList.add('active');
      }
    }
  },

  /**
   * Load global values and draw decision matrix table
   */
  async refreshDecisionMatrixView() {
    try {
      const probRes = await fetch(`/api/decision/${this.problemId}`);
      const problem = await probRes.json();

      const resRes = await fetch(`/api/decision/${this.problemId}/results`);
      const results = await resRes.json();

      Dashboard.renderDecisionMatrix(problem.criteria, problem.alternatives, results.results);
      
      // Update workflow steps based on state
      if (results.results && results.results.length > 0) {
        this.updateWorkflowStep(4);
      } else if (problem.alternatives && problem.alternatives.length > 0) {
        this.updateWorkflowStep(2);
      }
    } catch (e) {
      console.warn("Could not load decision matrix data:", e);
    }
  },

  /**
   * Load dual-axis timeseries V(a,t) vs Price(a,t)
   */
  async loadAndRenderTimeseries(ticker) {
    try {
      // 1. Fetch V(a, t) series
      const gvRes = await fetch(`/api/decision/${this.problemId}/results/timeseries?ticker=${ticker}`);
      const gvData = await gvRes.json();
      
      const vSeries = gvData.series[ticker] || [];
      
      // 2. Fetch Price history close prices
      const priceRes = await fetch(`/api/companies/${ticker}/prices?limit=365`);
      const priceData = await priceRes.json();
      const pSeries = priceData.prices || [];

      // Align dates
      const alignedDates = vSeries.map(s => s.date);
      const alignedGV = vSeries.map(s => s.value);
      
      // For each aligned date, find the nearest price close
      const alignedPrices = alignedDates.map(dateStr => {
        const targetDate = new Date(dateStr);
        // Find closest date in pSeries
        let closestPrice = null;
        let minDiff = Infinity;
        
        pSeries.forEach(p => {
          const pDate = new Date(p.date);
          const diff = Math.abs(pDate - targetDate);
          if (diff < minDiff) {
            minDiff = diff;
            closestPrice = p.close;
          }
        });
        
        return closestPrice;
      });

      // Format human-readable dates (e.g., Q1-2024 or standard formats)
      const formattedDates = alignedDates.map(d => new Date(d).toLocaleDateString());

      AppCharts.updateTimeseriesChart('timeseries-chart', formattedDates, alignedGV, alignedPrices, ticker);

    } catch (e) {
      console.error(e);
      this.showToast('error', 'Erro no Gráfico', `Falha ao renderizar gráfico temporal para ${ticker}.`);
    }
  },

  /**
   * Load scatter points and regression parameters
   */
  async loadAndRenderScatterPlot(ticker) {
    try {
      const res = await fetch(`/api/analysis/${this.problemId}/scatter/${ticker}`);
      if (!res.ok) throw new Error("Insufficient data points for scatter plot");
      const data = await res.json();
      
      AppCharts.updateScatterChart('scatter-chart', data.scatter, data.pearson_r);
    } catch (e) {
      console.warn(e.message);
    }
  },

  /**
   * Load statistics card values for selected company
   */
  async loadSingleAnalysisStats(ticker) {
    const statsContainer = document.getElementById('analysis-stats-container');
    statsContainer.innerHTML = '';

    try {
      const res = await fetch(`/api/analysis/${this.problemId}/results`);
      const data = await res.json();
      
      const stat = data.results.find(r => r.company_ticker === ticker);
      if (!stat) {
        statsContainer.innerHTML = `
          <div class="empty-state-inline compact">
            <i class="fa-solid fa-chart-simple"></i>
            <p>Sem dados estatísticos para esta empresa.</p>
          </div>`;
        return;
      }

      const makeStatRow = (label, value, colorCondition) => `
        <div class="stat-row">
          <span class="stat-label">${label}</span>
          <span class="stat-value" style="${colorCondition || ''}">${value}</span>
        </div>`;

      statsContainer.innerHTML = 
        makeStatRow('Coeficiente Pearson (r)', stat.pearson_correlation.toFixed(4), 
          `color:${stat.pearson_correlation >= 0 ? 'var(--color-success)' : 'var(--color-danger)'}`) +
        makeStatRow('Coeficiente Spearman (ρ)', stat.spearman_correlation.toFixed(4)) +
        makeStatRow('P-Valor (Significância)', 
          `${stat.p_value_pearson.toFixed(4)} ${stat.p_value_pearson < 0.05 ? '✓ Significativo' : '✗ Não sig.'}`,
          `color:${stat.p_value_pearson < 0.05 ? 'var(--color-success)' : 'var(--color-warning)'}`) +
        makeStatRow('Coeficiente R²', `${(stat.r_squared * 100).toFixed(2)}%`) +
        makeStatRow('Coeficiente Angular β', stat.beta_coefficient.toFixed(4));
    } catch(e) {
      console.error(e);
    }
  },

  /**
   * Load all recommendations and render in target div grid
   */
  async loadRecommendations() {
    const container = document.getElementById('recommendations-container');
    container.innerHTML = `
      <div class="empty-state-full">
        <i class="fa-solid fa-spinner fa-spin" style="opacity:0.6;"></i>
        <p>Gerando painel de recomendações...</p>
      </div>`;

    try {
      const res = await fetch(`/api/recommendations/${this.problemId}`);
      const data = await res.json();
      
      const recs = data.recommendations || [];
      
      if (recs.length === 0) {
        container.innerHTML = `
          <div class="empty-state-full">
            <i class="fa-solid fa-lightbulb"></i>
            <h3>Sem Recomendações Ainda</h3>
            <p>Calcule os valores globais e execute a análise temporal para gerar recomendações de investimento.</p>
            <button class="btn btn-secondary btn-sm" onclick="document.querySelector('[data-tab=smarter]').click()">
              Começar Análise <i class="fa-solid fa-arrow-right"></i>
            </button>
          </div>`;
        return;
      }

      container.innerHTML = '';
      recs.forEach(rec => {
        const card = document.createElement('div');
        card.className = 'rec-card';
        
        const badgeClass = rec.recommendation_label.toLowerCase().replace(' ', '-');
        const score = rec.recommendation_score;
        
        card.innerHTML = `
          <div class="rec-badge ${badgeClass}">${rec.recommendation_label}</div>
          <div class="rec-header">
            <div class="rec-logo">${rec.company_ticker.slice(0, 4)}</div>
            <div class="rec-company-info">
              <h3>${rec.company_ticker}</h3>
              <p>${rec.company_name || 'B3 Listed'}</p>
            </div>
          </div>
          <div class="rec-score-section">
            <span style="font-size:0.85rem; color:var(--text-secondary)">Score Composto:</span>
            <span class="rec-score-value">${score > 0 ? '+' : ''}${score.toFixed(4)}</span>
          </div>
          <div class="rec-stats">
            <div class="rec-stat-item">
              <span class="rec-stat-label">Pearson r</span>
              <span class="rec-stat-val" style="color:${rec.pearson_correlation >= 0 ? 'var(--color-success)' : 'var(--color-danger)'}">
                ${rec.pearson_correlation.toFixed(3)}
              </span>
            </div>
            <div class="rec-stat-item">
              <span class="rec-stat-label">Significância</span>
              <span class="rec-stat-val">${rec.p_value_pearson < 0.05 ? '✓ Relevante' : '✗ Irrelevante'}</span>
            </div>
            <div class="rec-stat-item">
              <span class="rec-stat-label">Coef. Beta</span>
              <span class="rec-stat-val">${rec.beta_coefficient.toFixed(3)}</span>
            </div>
            <div class="rec-stat-item">
              <span class="rec-stat-label">R² Ajustado</span>
              <span class="rec-stat-val">${(rec.r_squared * 100).toFixed(1)}%</span>
            </div>
          </div>
        `;

        card.addEventListener('click', () => {
          Dashboard.openCompanyDetailsDrawer(rec.company_ticker);
        });

        container.appendChild(card);
      });
    } catch(e) {
      console.error(e);
      container.innerHTML = `
        <div class="empty-state-full">
          <i class="fa-solid fa-circle-exclamation" style="color:var(--color-danger);"></i>
          <h3>Falha ao Carregar</h3>
          <p>Não foi possível carregar as recomendações do servidor.</p>
        </div>`;
    }
  },

  /**
   * Refreshes dynamic fields on the main landing dashboard
   */
  async refreshDashboardData() {
    try {
      // Refresh top ranking
      const listContainer = document.getElementById('top-companies-list');
      const resultsRes = await fetch(`/api/decision/${this.problemId}/results`);
      const resultsData = await resultsRes.json();
      
      const list = resultsData.results || [];
      
      if (list.length === 0) {
        listContainer.innerHTML = `
          <div class="empty-state-inline compact">
            <i class="fa-solid fa-chart-column"></i>
            <p>Nenhum cálculo efetuado.</p>
          </div>`;
        return;
      }

      listContainer.innerHTML = '';
      
      // Top 5 sorted by global value desc
      const top5 = list.slice(0, 5);
      const positionClasses = ['gold', 'silver', 'bronze', '', ''];
      
      top5.forEach((item, index) => {
        const row = document.createElement('div');
        row.className = 'ranking-row';
        
        row.innerHTML = `
          <div class="ranking-position ${positionClasses[index]}">#${index + 1}</div>
          <div class="ranking-ticker">${item.company_ticker}</div>
          <div class="ranking-value">${item.global_value.toFixed(4)}</div>
        `;
        listContainer.appendChild(row);
      });

      // Refresh Heatmap
      const heatmapContainer = document.getElementById('market-heatmap');
      heatmapContainer.innerHTML = '';
      
      list.forEach(item => {
        const cell = document.createElement('div');
        cell.className = 'heatmap-cell';
        const val = item.global_value; // range 0 to 1
        
        // HSL Color gradient mapping: 0 -> deep red HSL(0, 70%, 40%), 0.5 -> dark amber HSL(35, 70%, 40%), 1.0 -> deep green HSL(120, 70%, 40%)
        const hue = Math.round(val * 120);
        cell.style.background = `hsla(${hue}, 70%, 25%, 0.45)`;
        cell.style.border = `1px solid hsla(${hue}, 70%, 35%, 0.8)`;
        
        cell.innerHTML = `
          <span class="ticker">${item.company_ticker}</span>
          <span class="value">${val.toFixed(4)}</span>
        `;
        
        cell.addEventListener('click', () => {
          Dashboard.openCompanyDetailsDrawer(item.company_ticker);
        });

        heatmapContainer.appendChild(cell);
      });

    } catch (e) {
      console.warn("Could not refresh landing dashboard elements:", e);
    }
  }
};

// Start application coordinator when page finishes loading
window.addEventListener('DOMContentLoaded', () => {
  App.init();
});
