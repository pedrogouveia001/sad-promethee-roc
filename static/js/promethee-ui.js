/**
 * PrometheeInvestor — PROMETHEE ROC Elicitation & UI Module
 * Handles criteria selection, drag-and-drop sorting, and ROC weight visual updates.
 */

const PrometheeUI = {
  selectedCriteria: [], // Array of {code, name, type, default_type, category}

  init() {
    this.setupDragAndDrop();
    this.setupResetButton();
  },

  /**
   * Set up HTML5 Drag and Drop events for reordering criteria
   */
  setupDragAndDrop() {
    const container = document.getElementById('criteria-drag-list');
    
    container.addEventListener('dragstart', (e) => {
      const card = e.target.closest('.criteria-card');
      if (card) {
        card.classList.add('dragging');
        e.dataTransfer.setData('text/plain', card.dataset.code);
      }
    });

    container.addEventListener('dragend', (e) => {
      const card = e.target.closest('.criteria-card');
      if (card) {
        card.classList.remove('dragging');
        this.updateCriteriaOrderingFromDOM();
      }
    });

    container.addEventListener('dragover', (e) => {
      e.preventDefault();
      const draggingEl = container.querySelector('.dragging');
      if (!draggingEl) return;

      const afterElement = this.getDragAfterElement(container, e.clientY);
      if (afterElement == null) {
        container.appendChild(draggingEl);
      } else {
        container.insertBefore(draggingEl, afterElement);
      }
    });
  },

  setupResetButton() {
    document.getElementById('reset-criteria-btn').addEventListener('click', () => {
      this.resetToDefaultCriteria();
    });
  },

  /**
   * Get the element immediately after the current drag position
   */
  getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.criteria-card:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset: offset, element: child };
      } else {
        return closest;
      }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
  },

  /**
   * Load available criteria definitions from the backend and populate the panel
   */
  async loadCriteria() {
    try {
      const response = await fetch('/api/indicators');
      const data = await response.json();
      
      // Flatten grouped indicators into a single array for our state
      let allIndicators = [];
      Object.keys(data).forEach(category => {
        allIndicators = allIndicators.concat(data[category]);
      });

      // Default: select a subset of popular indicators
      const defaultSelected = ['trailing_pe', 'price_to_book', 'roe', 'dividend_yield', 'current_ratio'];
      
      this.selectedCriteria = allIndicators.map(ind => ({
        code: ind.code,
        name: ind.name,
        category: ind.category,
        default_type: ind.default_type,
        type: ind.default_type, // active setting (cost/benefit)
        selected: defaultSelected.includes(ind.code)
      }));

      this.renderCriteria();
    } catch (error) {
      console.error("Failed to load criteria:", error);
    }
  },

  /**
   * Reset criteria to defaults
   */
  resetToDefaultCriteria() {
    const defaultSelected = ['trailing_pe', 'price_to_book', 'roe', 'dividend_yield', 'current_ratio'];
    this.selectedCriteria.forEach(c => {
      c.selected = defaultSelected.includes(c.code);
      c.type = c.default_type;
    });
    this.renderCriteria();
  },

  /**
   * Render criteria checkboxes and sorting cards
   */
  renderCriteria() {
    const listContainer = document.getElementById('criteria-drag-list');
    listContainer.innerHTML = '';

    // Filter to selected criteria and sort them according to their ordering in selectedCriteria
    const activeCriteria = this.selectedCriteria.filter(c => c.selected);
    const n = activeCriteria.length;
    const weights = this.calculateROC(n);

    activeCriteria.forEach((crit, index) => {
      const weight = weights[index];
      const isChecked = crit.type === 'benefit';

      const card = document.createElement('div');
      card.className = 'criteria-card';
      card.draggable = true;
      card.dataset.code = crit.code;
      
      card.innerHTML = `
        <div class="criteria-card-left">
          <span class="drag-handle"><i class="fa-solid fa-grip-vertical"></i></span>
          <span class="criteria-rank">${index + 1}</span>
          <span class="criteria-name">${crit.name}</span>
        </div>
        <div class="criteria-card-right">
          <div class="toggle-container">
            <span class="toggle-label">${crit.type === 'benefit' ? 'Benefício' : 'Custo'}</span>
            <label class="toggle-switch">
              <input type="checkbox" class="crit-type-toggle" ${isChecked ? 'checked' : ''} data-code="${crit.code}">
              <span class="slider"></span>
            </label>
          </div>
          <span class="criteria-weight">${(weight * 100).toFixed(2)}%</span>
        </div>
      `;

      // Event listener for the cost/benefit toggle
      card.querySelector('.crit-type-toggle').addEventListener('change', (e) => {
        const code = e.target.dataset.code;
        const checked = e.target.checked;
        const newType = checked ? 'benefit' : 'cost';
        
        // Update model
        const target = this.selectedCriteria.find(c => c.code === code);
        if (target) {
          target.type = newType;
        }

        // Update card label
        card.querySelector('.toggle-label').textContent = checked ? 'Benefício' : 'Custo';
      });

      listContainer.appendChild(card);
    });

    // Also render visual checklist of all available criteria below or inside
    // (for this demo, we'll expose a checklist selector at the top or in modal if requested)
    
    // Draw weights chart
    const labels = activeCriteria.map(c => c.name);
    AppCharts.updateWeightsChart('weights-chart', labels, weights);
  },

  /**
   * Recalculate weights and list indices when DOM drag actions end
   */
  updateCriteriaOrderingFromDOM() {
    const cards = [...document.querySelectorAll('.criteria-card')];
    const orderedCodes = cards.map(c => c.dataset.code);

    // Reorder our internal array to match the DOM
    const reordered = [];
    
    // First, place active items in order
    orderedCodes.forEach(code => {
      const item = this.selectedCriteria.find(c => c.code === code);
      if (item) reordered.push(item);
    });

    // Then, append inactive items to the back
    this.selectedCriteria.forEach(item => {
      if (!orderedCodes.includes(item.code)) {
        reordered.push(item);
      }
    });

    this.selectedCriteria = reordered;
    this.renderCriteria(); // Re-render to update ranks, weights, and chart
  },

  /**
   * Compute Rank Order Centroid (ROC) weights
   */
  calculateROC(n) {
    const weights = [];
    if (n <= 0) return weights;

    for (let i = 1; i <= n; i++) {
      let sum = 0;
      for (let j = i; j <= n; j++) {
        sum += 1 / j;
      }
      weights.push(sum / n);
    }
    return weights;
  },

  /**
   * Return the JSON body representation of the current active criteria
   */
  getCriteriaDataForSubmit() {
    const active = this.selectedCriteria.filter(c => c.selected);
    return active.map((c, index) => ({
      indicator_code: c.code,
      rank: index + 1,
      type: c.type
    }));
  }
};
