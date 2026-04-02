async function predict() {
    const devise = document.getElementById("devise").value; 
    const days = parseInt(document.getElementById("days").value);

    const res = await fetch(`/predict?devise=${devise}&days=${days}`);
    const data = await res.json();

   
    const trace1 = {
        x: data.dates,
        y: data.historic,        
        mode: 'lines+markers',
        name: 'Historique',
        line: { color: 'blue' }
    };

    const trace2 = {
        x: data.pred_dates,
        y: data.predictions,
        mode: 'lines+markers',
        name: 'Prédictions',
        line: { color: 'red', dash: 'dash' }
    };


    Plotly.newPlot('chart', [trace1, trace2], {
        title: `Prédictions EUR → ${devise}`,
        xaxis: { title: 'Date' },
        yaxis: { title: 'Taux' }
    });
}