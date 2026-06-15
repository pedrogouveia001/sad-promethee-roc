/**
 * B3 SmarterInvestor — Chart Management Module
 * Wraps Chart.js instances and updating logic.
 */

const AppCharts = {
  instances: {
    weights: null,
    timeseries: null,
    scatter: null
  },

  /**
   * Render or update the ROC criteria weights bar chart
   */
  updateWeightsChart(canvasId, labels, weights) {
    if (this.instances.weights) {
      this.instances.weights.destroy();
    }

    const ctx = document.getElementById(canvasId).getContext('2d');
    
    this.instances.weights = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Peso ROC',
          data: weights,
          backgroundColor: 'rgba(99, 102, 241, 0.4)',
          borderColor: '#6366f1',
          borderWidth: 2,
          borderRadius: 6,
          hoverBackgroundColor: 'rgba(99, 102, 241, 0.65)',
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0c1020',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            titleFont: { family: 'Outfit', weight: 'bold' },
            bodyFont: { family: 'Plus Jakarta Sans' },
            callbacks: {
              label: function(context) {
                return ` Peso: ${(context.raw * 100).toFixed(2)}%`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans' } }
          },
          y: {
            beginAtZero: true,
            max: 1.0,
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { 
              color: '#94a3b8', 
              font: { family: 'Plus Jakarta Sans' },
              callback: value => `${(value * 100).toFixed(0)}%`
            }
          }
        }
      }
    });
  },

  /**
   * Render or update the dual-axis historical time series comparison
   */
  updateTimeseriesChart(canvasId, dates, globalValues, priceValues, ticker) {
    if (this.instances.timeseries) {
      this.instances.timeseries.destroy();
    }

    const ctx = document.getElementById(canvasId).getContext('2d');
    
    this.instances.timeseries = new Chart(ctx, {
      type: 'line',
      data: {
        labels: dates,
        datasets: [
          {
            label: 'Valor Global V(a)',
            data: globalValues,
            borderColor: '#6366f1',
            backgroundColor: 'rgba(99, 102, 241, 0.05)',
            borderWidth: 3,
            yAxisID: 'yGlobal',
            tension: 0.2,
            fill: true,
            pointBackgroundColor: '#6366f1',
            pointHoverRadius: 6
          },
          {
            label: `Preço de Fechamento (${ticker})`,
            data: priceValues,
            borderColor: '#10b981',
            borderWidth: 2,
            borderDash: [5, 5],
            yAxisID: 'yPrice',
            tension: 0.1,
            fill: false,
            pointRadius: 0,
            pointHoverRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false,
        },
        plugins: {
          legend: {
            position: 'top',
            labels: { color: '#f8fafc', font: { family: 'Outfit', size: 12 } }
          },
          tooltip: {
            backgroundColor: '#0c1020',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            titleFont: { family: 'Outfit', weight: 'bold' },
            bodyFont: { family: 'Plus Jakarta Sans' },
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.03)' },
            ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans' } }
          },
          yGlobal: {
            type: 'linear',
            display: true,
            position: 'left',
            min: -1,
            max: 1,
            title: {
              display: true,
              text: 'Valor Global [0, 1]',
              color: '#6366f1',
              font: { family: 'Outfit', weight: 'bold' }
            },
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#94a3b8' }
          },
          yPrice: {
            type: 'linear',
            display: true,
            position: 'right',
            title: {
              display: true,
              text: 'Preço (R$)',
              color: '#10b981',
              font: { family: 'Outfit', weight: 'bold' }
            },
            grid: { drawOnChartArea: false }, // avoid grid overlaps
            ticks: { 
              color: '#94a3b8',
              callback: value => `R$ ${value.toFixed(2)}`
            }
          }
        }
      }
    });
  },

  /**
   * Render or update the scatter plot (Delta V vs Delta Price)
   */
  updateScatterChart(canvasId, scatterPoints, pearsonR) {
    if (this.instances.scatter) {
      this.instances.scatter.destroy();
    }

    const ctx = document.getElementById(canvasId).getContext('2d');

    // Parse scatter data format
    const dataPoints = scatterPoints.map(p => ({
      x: p.delta_v,
      y: p.delta_price * 100 // convert to percentage
    }));

    // Calculate trendline endpoints using regression line estimation
    let trendDataset = [];
    if (dataPoints.length > 1) {
      const xs = dataPoints.map(p => p.x);
      const ys = dataPoints.map(p => p.y);
      
      const xMean = xs.reduce((a, b) => a + b, 0) / xs.length;
      const yMean = ys.reduce((a, b) => a + b, 0) / ys.length;
      
      let num = 0;
      let den = 0;
      for (let i = 0; i < xs.length; i++) {
        num += (xs[i] - xMean) * (ys[i] - yMean);
        den += Math.pow(xs[i] - xMean, 2);
      }
      
      const slope = den === 0 ? 0 : num / den;
      const intercept = yMean - slope * xMean;

      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      
      trendDataset = [
        { x: minX, y: slope * minX + intercept },
        { x: maxX, y: slope * maxX + intercept }
      ];
    }

    this.instances.scatter = new Chart(ctx, {
      type: 'scatter',
      data: {
        datasets: [
          {
            label: 'Observações',
            data: dataPoints,
            backgroundColor: 'rgba(16, 185, 129, 0.6)',
            borderColor: '#10b981',
            borderWidth: 1,
            pointRadius: 5,
            pointHoverRadius: 7
          },
          {
            label: 'Linha de Tendência',
            data: trendDataset,
            type: 'line',
            borderColor: '#f59e0b',
            borderWidth: 1.5,
            fill: false,
            pointRadius: 0,
            showLine: true
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0c1020',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            titleFont: { family: 'Outfit', weight: 'bold' },
            bodyFont: { family: 'Plus Jakarta Sans' },
            callbacks: {
              label: function(context) {
                return `ΔV: ${context.raw.x.toFixed(4)}, ΔPreço: ${context.raw.y.toFixed(2)}%`;
              }
            }
          }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Variação do Valor Global (ΔV)',
              color: '#94a3b8',
              font: { family: 'Plus Jakarta Sans', size: 10 }
            },
            grid: { color: 'rgba(255, 255, 255, 0.03)' },
            ticks: { color: '#94a3b8' }
          },
          y: {
            title: {
              display: true,
              text: 'Variação de Preço (Δ%)',
              color: '#94a3b8',
              font: { family: 'Plus Jakarta Sans', size: 10 }
            },
            grid: { color: 'rgba(255, 255, 255, 0.03)' },
            ticks: { 
              color: '#94a3b8',
              callback: value => `${value.toFixed(1)}%`
            }
          }
        }
      }
    });
  }
};
