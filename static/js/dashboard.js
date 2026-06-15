/**
 * B3 SmarterInvestor — Alternatives Selection & Main Dashboard Panels
 * Manages the sector tree checklist, company cards, and the decision matrix view.
 */

const Dashboard = {
  selectedTickers: new Set(['PETR4', 'VALE3', 'ITUB4', 'MGLU3', 'WEGE3', 'BBAS3']), // Default initial selections
  sectorsData: [],
  companiesCache: {}, // sector_name -> list of companies

  init() {
    this.setupSectorTreeEvents();
    this.setupSearch();
    this.setupSelectionActions();
  },

  /**
   * Fetch and render B3 sectors
   */
  async loadSectors() {
    try {
      const response = await fetch('/api/sectors');
      this.sectorsData = await response.json();
      this.renderSectorTree();
      this.renderSelectedCompanies();
    } catch (error) {
      console.error("Failed to load sectors:", error);
    }
  },

  /**
   * Render the collapsible sector tree
   */
  renderSectorTree() {
    const treeContainer = document.getElementById('sector-tree');
    treeContainer.innerHTML = '';

    if (this.sectorsData.length === 0) {
      treeContainer.innerHTML = `<div style="color: var(--text-muted); text-align:center; padding:1rem;">Nenhum setor encontrado.</div>`;
      return;
    }

    this.sectorsData.forEach(sector => {
      const node = document.createElement('div');
      node.className = 'sector-node';
      node.dataset.sector = sector.name;

      node.innerHTML = `
        <div class="sector-header">
          <i class="fa-solid fa-chevron-right sector-toggle-icon"></i>
          <input type="checkbox" class="sector-checkbox" data-sector="${sector.name}">
          <span style="font-weight:600; flex-grow:1;">${sector.name}</span>
          <span style="font-size:0.75rem; background:var(--bg-tertiary); padding:0.15rem 0.4rem; border-radius:6px; color:var(--text-secondary); border:1px solid var(--border-glass)">
            ${sector.company_count}
          </span>
        </div>
        <div class="sector-children" style="display:none;" id="sector-children-${btoa(sector.name).replace(/=/g, '')}">
          <div style="color:var(--text-muted); font-size:0.8rem; padding: 0.5rem 1rem;">
            <i class="fa-solid fa-spinner fa-spin"></i> Carregando empresas...
          </div>
        </div>
      `;

      // Accordion toggle click handler
      const header = node.querySelector('.sector-header');
      const toggleIcon = node.querySelector('.sector-toggle-icon');
      const childrenContainer = node.querySelector('.sector-children');
      const checkbox = node.querySelector('.sector-checkbox');

      header.addEventListener('click', async (e) => {
        // Prevent toggling accordion if user clicks checkbox
        if (e.target.type === 'checkbox') return;

        const isCollapsed = childrenContainer.style.display === 'none';
        
        if (isCollapsed) {
          childrenContainer.style.display = 'flex';
          toggleIcon.className = 'fa-solid fa-chevron-down sector-toggle-icon';
          await this.loadSectorCompanies(sector.name, childrenContainer);
        } else {
          childrenContainer.style.display = 'none';
          toggleIcon.className = 'fa-solid fa-chevron-right sector-toggle-icon';
        }
      });

      // Sector level checkbox handler
      checkbox.addEventListener('change', async (e) => {
        const checked = e.target.checked;
        await this.toggleSectorCompaniesSelection(sector.name, checked, childrenContainer);
      });

      treeContainer.appendChild(node);
    });
  },

  /**
   * Load companies in a sector (lazy loading)
   */
  async loadSectorCompanies(sectorName, containerElement) {
    if (this.companiesCache[sectorName]) {
      this.renderSectorCompaniesInDOM(sectorName, containerElement);
      return;
    }

    try {
      const response = await fetch(`/api/sectors/${encodeURIComponent(sectorName)}/companies`);
      const companies = await response.json();
      this.companiesCache[sectorName] = companies;
      this.renderSectorCompaniesInDOM(sectorName, containerElement);
    } catch (error) {
      console.error(`Failed to load companies for sector ${sectorName}:`, error);
      containerElement.innerHTML = `<div style="color:var(--color-danger); font-size:0.8rem; padding:0.5rem 1rem;">Erro ao carregar empresas.</div>`;
    }
  },

  /**
   * Render loaded companies into the sector tree DOM
   */
  renderSectorCompaniesInDOM(sectorName, containerElement) {
    containerElement.innerHTML = '';
    const companies = this.companiesCache[sectorName] || [];

    if (companies.length === 0) {
      containerElement.innerHTML = `<div style="color:var(--text-muted); font-size:0.8rem; padding:0.5rem 1rem;">Sem empresas ativas neste setor.</div>`;
      return;
    }

    companies.forEach(company => {
      const row = document.createElement('div');
      row.className = 'company-checkbox-row';
      
      const isChecked = this.selectedTickers.has(company.ticker);

      row.innerHTML = `
        <input type="checkbox" class="company-checkbox" data-ticker="${company.ticker}" data-sector="${sectorName}" ${isChecked ? 'checked' : ''}>
        <span style="font-weight:600; font-family:var(--font-display); width:70px;">${company.ticker}</span>
        <span style="font-size:0.85rem; color:var(--text-secondary); text-overflow:ellipsis; overflow:hidden; white-space:nowrap; flex-grow:1;">
          ${company.name}
        </span>
      `;

      row.querySelector('.company-checkbox').addEventListener('change', (e) => {
        const ticker = e.target.dataset.ticker;
        if (e.target.checked) {
          this.selectedTickers.add(ticker);
        } else {
          this.selectedTickers.delete(ticker);
        }
        this.renderSelectedCompanies();
        this.updateSectorCheckboxState(sectorName);
      });

      containerElement.appendChild(row);
    });

    // Update the master sector checkbox depending on children state
    this.updateSectorCheckboxState(sectorName);
  },

  /**
   * Toggle all company selections inside a sector node
   */
  async toggleSectorCompaniesSelection(sectorName, checked, containerElement) {
    // If not visible or cached, load first
    if (!this.companiesCache[sectorName]) {
      // Force accordion open to display them
      containerElement.style.display = 'flex';
      const toggleIcon = containerElement.parentElement.querySelector('.sector-toggle-icon');
      if (toggleIcon) toggleIcon.className = 'fa-solid fa-chevron-down sector-toggle-icon';
      await this.loadSectorCompanies(sectorName, containerElement);
    }

    const companies = this.companiesCache[sectorName] || [];
    companies.forEach(comp => {
      if (checked) {
        this.selectedTickers.add(comp.ticker);
      } else {
        this.selectedTickers.delete(comp.ticker);
      }
    });

    // Update DOM checkboxes under this node
    containerElement.querySelectorAll('.company-checkbox').forEach(chk => {
      chk.checked = checked;
    });

    this.renderSelectedCompanies();
  },

  /**
   * Align sector level checkbox state with children states
   */
  updateSectorCheckboxState(sectorName) {
    const node = document.querySelector(`.sector-node[data-sector="${sectorName}"]`);
    if (!node) return;

    const sectorCheckbox = node.querySelector('.sector-checkbox');
    const childrenContainer = node.querySelector('.sector-children');
    const childCheckboxes = [...childrenContainer.querySelectorAll('.company-checkbox')];

    if (childCheckboxes.length === 0) return;

    const allChecked = childCheckboxes.every(chk => chk.checked);
    const someChecked = childCheckboxes.some(chk => chk.checked);

    sectorCheckbox.checked = allChecked;
    sectorCheckbox.indeterminate = someChecked && !allChecked;
  },

  /**
   * Render cards list of currently selected companies on the right
   */
  renderSelectedCompanies() {
    const container = document.getElementById('selected-companies-cards');
    document.getElementById('selected-count').textContent = this.selectedTickers.size;

    if (this.selectedTickers.size === 0) {
      container.innerHTML = `
        <div style="color: var(--text-secondary); text-align: center; grid-column: 1 / -1; padding: 3rem; border: 1px dashed var(--border-glass); border-radius: 12px;">
          Nenhuma empresa selecionada. Selecione empresas na árvore setorial.
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    
    // Sort selected tickers alphabetically
    const sortedTickers = [...this.selectedTickers].sort();

    sortedTickers.forEach(ticker => {
      const card = document.createElement('div');
      card.className = 'glass-card interactive';
      card.style.padding = '1rem 1.25rem';
      card.style.display = 'flex';
      card.style.flexDirection = 'column';
      card.style.gap = '0.5rem';

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-family:var(--font-display); font-size:1.15rem; font-weight:800; color:var(--text-primary);">${ticker}</span>
          <button class="remove-ticker-btn" data-ticker="${ticker}" style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:0.9rem;">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </div>
        <div style="font-size:0.75rem; color:var(--text-secondary); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" class="company-card-fullname-${ticker}">
          --
        </div>
        <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem;">
          <span class="company-card-sector-${ticker}">--</span>
        </div>
      `;

      card.querySelector('.remove-ticker-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        const tickerToRemove = e.currentTarget.dataset.ticker;
        this.selectedTickers.delete(tickerToRemove);
        this.renderSelectedCompanies();
        
        // Deselect in the sector tree if loaded
        const chk = document.querySelector(`.company-checkbox[data-ticker="${tickerToRemove}"]`);
        if (chk) {
          chk.checked = false;
          this.updateSectorCheckboxState(chk.dataset.sector);
        }
      });

      // Show details on card click
      card.addEventListener('click', () => {
        this.openCompanyDetailsDrawer(ticker);
      });

      container.appendChild(card);

      // Async load company full details if not already loaded to fill full name/sector card fields
      this.fillCompanyCardDetails(ticker);
    });

    // Also populate company list select options in analysis panel
    this.populateAnalysisSelect();
  },

  async fillCompanyCardDetails(ticker) {
    try {
      const res = await fetch(`/api/companies/${ticker}`);
      if (!res.ok) return;
      const comp = await res.json();
      
      const nameEl = document.querySelector(`.company-card-fullname-${ticker}`);
      if (nameEl) nameEl.textContent = comp.name;
      
      const sectorEl = document.querySelector(`.company-card-sector-${ticker}`);
      if (sectorEl) sectorEl.textContent = comp.sector ? comp.sector.name : 'Outros';
    } catch(e) {
      console.warn(`Failed to fetch details for ${ticker}:`, e);
    }
  },

  populateAnalysisSelect() {
    const select = document.getElementById('analysis-company-select');
    const currentValue = select.value;
    
    select.innerHTML = '<option value="">Selecione...</option>';
    
    const sortedTickers = [...this.selectedTickers].sort();
    sortedTickers.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = t;
      if (t === currentValue) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
  },

  setupSectorTreeEvents() {
    // Select all/clear buttons
    document.getElementById('select-all-sectors').addEventListener('click', async () => {
      // Loop over loaded sectors and toggle them all to selected
      for (const sector of this.sectorsData) {
        const node = document.querySelector(`.sector-node[data-sector="${sector.name}"]`);
        if (node) {
          const chk = node.querySelector('.sector-checkbox');
          const children = node.querySelector('.sector-children');
          chk.checked = true;
          await this.toggleSectorCompaniesSelection(sector.name, true, children);
        }
      }
    });

    document.getElementById('clear-sectors').addEventListener('click', () => {
      this.selectedTickers.clear();
      document.querySelectorAll('.sector-checkbox, .company-checkbox').forEach(chk => {
        chk.checked = false;
        chk.indeterminate = false;
      });
      this.renderSelectedCompanies();
    });
  },

  setupSearch() {
    // Search input handler
    const searchInput = document.getElementById('company-search-input');
    searchInput.addEventListener('input', (e) => {
      const term = e.target.value.toUpperCase();
      const cards = document.querySelectorAll('#selected-companies-cards > div');
      
      cards.forEach(card => {
        const ticker = card.querySelector('span').textContent;
        if (ticker.includes(term)) {
          card.style.display = 'flex';
        } else {
          card.style.display = 'none';
        }
      });
    });
  },

  setupSelectionActions() {
    // Save selection button
    document.getElementById('save-alternatives-btn').addEventListener('click', async () => {
      const problemId = localStorage.getItem('current_decision_problem_id');
      if (!problemId) {
        alert("Crie um problema de decisão ou recalcule para começar.");
        return;
      }

      try {
        const response = await fetch(`/api/decision/${problemId}/alternatives`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tickers: [...this.selectedTickers] })
        });

        if (response.ok) {
          alert("Seleção de empresas salva com sucesso!");
        } else {
          const err = await response.json();
          alert(`Erro ao salvar seleção: ${err.error || 'Erro desconhecido'}`);
        }
      } catch (error) {
        console.error("Failed to save alternatives:", error);
      }
    });
  },

  /**
   * Detail company side drawer drawer
   */
  async openCompanyDetailsDrawer(ticker) {
    const drawer = document.getElementById('company-detail-drawer');
    const title = document.getElementById('drawer-company-name');
    const content = document.getElementById('drawer-content');

    title.textContent = `${ticker} — Detalhes da Empresa`;
    content.innerHTML = `<div style="text-align:center; padding:3rem;"><i class="fa-solid fa-spinner fa-spin fa-2x"></i><p style="margin-top:1rem;">Carregando indicadores fundamentais...</p></div>`;
    drawer.classList.add('open');

    try {
      const res = await fetch(`/api/companies/${ticker}/indicators`);
      const data = await res.json();
      
      content.innerHTML = '';
      
      const grid = document.createElement('div');
      grid.style.display = 'flex';
      grid.style.flexDirection = 'column';
      grid.style.gap = '1.25rem';

      // Header values
      const head = document.createElement('div');
      head.innerHTML = `
        <h4 style="font-family:var(--font-display); font-size:1.1rem; margin-bottom:0.25rem;">${data.name}</h4>
        <span style="font-size:0.75rem; color:var(--text-muted)">Última atualização dos dados: ${new Date(Object.values(data.indicators)[0]?.date).toLocaleDateString()}</span>
      `;
      content.appendChild(head);

      // Category titles helper
      const categories = {
        'valuation': 'Valuation',
        'rentabilidade': 'Rentabilidade',
        'dividendos': 'Retorno & Dividendos',
        'endividamento': 'Endividamento',
        'crescimento': 'Crescimento'
      };

      // Group indicators by category
      const grouped = {};
      Object.keys(data.indicators).forEach(code => {
        const ind = data.indicators[code];
        if (!grouped[ind.category]) grouped[ind.category] = [];
        grouped[ind.category].push({ code, ...ind });
      });

      Object.keys(categories).forEach(cat => {
        if (!grouped[cat]) return;

        const catSec = document.createElement('div');
        catSec.innerHTML = `<h5 style="color:var(--color-accent); font-family:var(--font-display); margin-bottom:0.75rem; border-bottom:1px solid var(--border-glass); padding-bottom:0.25rem;">${categories[cat]}</h5>`;
        
        const catGrid = document.createElement('div');
        catGrid.style.display = 'grid';
        catGrid.style.gridTemplateColumns = '1fr 1fr';
        catGrid.style.gap = '0.75rem';

        grouped[cat].forEach(ind => {
          const valBox = document.createElement('div');
          valBox.style.padding = '0.5rem 0.75rem';
          valBox.style.background = 'rgba(255, 255, 255, 0.02)';
          valBox.style.borderRadius = '8px';
          valBox.style.border = '1px solid var(--border-glass)';

          let formattedVal = ind.value;
          // Formatting based on indicator code
          if (ind.code.includes('margin') || ind.code.includes('growth') || ind.code === 'roe' || ind.code === 'roa' || ind.code === 'dividend_yield' || ind.code === 'payout_ratio') {
            formattedVal = `${(ind.value * 100).toFixed(2)}%`;
          } else if (ind.value > 1000000 || ind.value < -1000000) {
            formattedVal = `R$ ${(ind.value / 1000000).toFixed(2)}M`;
          } else {
            formattedVal = ind.value.toFixed(2);
          }

          valBox.innerHTML = `
            <div style="font-size:0.75rem; color:var(--text-secondary); margin-bottom:0.15rem;">${ind.name}</div>
            <div style="font-family:var(--font-display); font-size:1.05rem; font-weight:700; color:var(--text-primary);">${formattedVal}</div>
          `;
          catGrid.appendChild(valBox);
        });

        catSec.appendChild(catGrid);
        content.appendChild(catSec);
      });

    } catch (e) {
      console.error(e);
      content.innerHTML = `<div style="color:var(--color-danger); text-align:center; padding:3rem;"><i class="fa-solid fa-triangle-exclamation fa-2x"></i><p style="margin-top:1rem;">Erro ao carregar detalhes.</p></div>`;
    }
  },

  /**
   * Render decision matrix table from calculated results
   */
  renderDecisionMatrix(criteria, alternatives, results) {
    const table = document.getElementById('decision-matrix-table');
    table.innerHTML = '';

    if (results.length === 0) {
      table.innerHTML = `<tbody><tr><td style="color: var(--text-secondary); padding: 1.5rem; text-align: center;">Nenhum cálculo efetuado. Insira critérios e alternativas.</td></tr></tbody>`;
      return;
    }

    // Head
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.innerHTML = `
      <th style="padding: 0.75rem; border-bottom: 2px solid var(--border-glass);">Alternativa</th>
    `;
    
    criteria.forEach(crit => {
      const th = document.createElement('th');
      th.style.padding = '0.75rem';
      th.style.borderBottom = '2px solid var(--border-glass)';
      th.innerHTML = `
        <div>${crit.indicator.name}</div>
        <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 500;">
          Peso: ${(crit.roc_weight * 100).toFixed(1)}% | ${crit.criteria_type === 'benefit' ? 'Benefício' : 'Custo'}
        </div>
      `;
      headerRow.appendChild(th);
    });

    headerRow.innerHTML += `<th style="padding: 0.75rem; border-bottom: 2px solid var(--border-glass); text-align:right;">Valor Global V(a)</th>`;
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body
    const tbody = document.createElement('tbody');

    results.forEach(res => {
      const row = document.createElement('tr');
      row.style.borderBottom = '1px solid var(--border-glass)';
      
      const altName = res.company_ticker || `Comp ID ${res.company_id}`;
      row.innerHTML = `
        <td style="padding: 0.85rem 0.75rem; font-family: var(--font-display); font-weight: 700;">${altName}</td>
      `;

      // Normalized indicators list from response
      const normVals = res.normalized_values || {};

      criteria.forEach(crit => {
        const val = normVals[crit.indicator.code];
        const displayVal = val !== undefined ? val.toFixed(4) : '--';
        row.innerHTML += `<td style="padding: 0.85rem 0.75rem; color: var(--text-secondary);">${displayVal}</td>`;
      });

      row.innerHTML += `
        <td style="padding: 0.85rem 0.75rem; font-family: var(--font-display); font-weight: 800; text-align:right; color:var(--color-accent);">
          ${res.global_value.toFixed(4)}
        </td>
      `;

      tbody.appendChild(row);
    });

    table.appendChild(tbody);
  }
};

// Close detail drawer event handler
document.getElementById('drawer-close-btn').addEventListener('click', () => {
  document.getElementById('company-detail-drawer').classList.remove('open');
});
