async function predict() {
    const device = document.getElementById("device").value;
    const days = document.getElementById("days").value;

    const res = await fetch(`/predict?devise=${device}&days=${days}`)
    const data = await res.json();

    const trace1 = {
        x: data.dates,
        y: data.hisoric,
        mode: 'lines+markers',
        name: 'Historique',
        line:{color:'blue'}
    }
    const trace2 ={
        x: data.pred_dates,
        y: data.predictions,
        mode: 'lines+markers',
        name: 'Predictions',
        line:{color:'red',dash:'dash'}
    }
    plotly.newPlot('plot', [trace1, trace2], {
        title: `Predictions EUR > ${device}`,
        xaxis: { title: 'Date' },
        yaxis: { title: 'Price' }
    });
}