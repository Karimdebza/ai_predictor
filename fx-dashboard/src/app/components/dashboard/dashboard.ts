import { Component, OnInit, ViewChild, ElementRef, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { FxService } from '../../services/fx.service';
import { FxResponse } from '../../interfaces/FxResponse';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);
@Component({
  selector: 'app-dashboard',
  imports: [CommonModule,FormsModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit, OnDestroy {

@ViewChild('chart') fxChartRef!: ElementRef;

  devises = ['MAD','USD', 'GBP', 'JPY']
  selectedDevise = 'MAD';
  days = 5;
  loading = false;
  error :string | null = null;

  currentRate:number | null = null;
  trend:string | null = null;
  trendUp:boolean = false ;  
  lastPrediction:number | null = null;
  predictions:{date:string,prediction:number;lower:number;upper:number}[] = [];

  private chart: Chart | null = null;

  constructor(private fxService: FxService) {}

  ngOnInit(): void {
    this.loadData();
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
  }
  selectDevise(devise: string) {
    this.selectedDevise = devise;
    this.loadData();
  }

  onDaysChange() {
    this.loadData();
  }
  
  loadData() {
    this.loading = true;
    this.error = null;

    this.fxService.predict(this.selectedDevise, this.days).subscribe({
      next:(data)=>{
       
      
        this.loading = false;
        this.processdata(data);
       setTimeout(() => {
    
    this.buildChart(data);
  }, 200);

      
      
      },
      error:(err)=>{

        this.error = 'ERREUR de chargement des données.';
        this.loading = false;
      
      }
    });
  }

  processdata(data:FxResponse) {
    this.currentRate = data.historic.at(-1) ?? null;
    this.lastPrediction = data.predictions.at(-1) ?? null;
    this.trendUp = (data.predictions[0] ?? 0) > (this.currentRate ?? 0);
    this.trend = this.trendUp ? '↑' : '↓';
    this.predictions = data.pred_dates.map((date, i) => ({
      date,
      prediction: parseFloat(data.predictions[i].toFixed(4)),
      lower: parseFloat(data.lower[i].toFixed(4)),
      upper: parseFloat(data.upper[i].toFixed(4))
    }));
  

  }



  

  buildChart(data: FxResponse) {
     this.fxChartRef.nativeElement.style.display = 'block';
      this.loading = false;
    const last60dates = data.dates.slice(-60);
    const last60values = data.historic.slice(-60);
    const labels = [...last60dates, ...data.pred_dates];
      const historicData = [
      ...last60values.map(v => parseFloat(v.toFixed(4))),
      ...new Array(data.pred_dates.length).fill(null)
    ];
     const predData = [
      ...new Array(last60dates.length).fill(null),
      ...data.predictions.map(v => parseFloat(v.toFixed(4)))
    ];

    const upperData = [
      ...new Array(last60dates.length).fill(null),
      ...data.upper.map(v => parseFloat(v.toFixed(4)))
    ];

    const lowerData = [
      ...new Array(last60dates.length).fill(null),
      ...data.lower.map(v => parseFloat(v.toFixed(4)))
    ];

    this.chart?.destroy();

    this.chart = new Chart(this.fxChartRef.nativeElement, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Historique',
            data: historicData,
            borderColor: '#6366f1',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
          },
          {
            label: 'Prédiction',
            data: predData,
            borderColor: '#f59e0b',
            borderDash: [5, 5],
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
          },
          {
            label: 'Max',
            data: upperData,
            borderColor: 'transparent',
            backgroundColor: 'rgba(245,158,11,0.15)',
            fill: '+1',
            pointRadius: 0,
          },
          {
            label: 'Min',
            data: lowerData,
            borderColor: 'transparent',
            backgroundColor: 'rgba(245,158,11,0.15)',
            fill: false,
            pointRadius: 0,
          },
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: '#94a3b8' } } },
        scales: {
          x: { ticks: { color: '#94a3b8', maxTicksLimit: 8 }, grid: { color: '#1e293b' } },
          y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } }
        }
      }
    });
  }
}
