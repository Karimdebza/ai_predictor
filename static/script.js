// async function predict() {
//     const loading = document.getElementById("loading");
//     const chartDiv = document.getElementById("chart");

//     try {
//         const devise = document.getElementById("devise").value;
//         const days = parseInt(document.getElementById("days").value);

//         if (loading) loading.style.display = "block";
//         if (chartDiv) chartDiv.innerHTML = "";

//         const res = await fetch(`/predict?devise=${devise}&days=${days}`);
//         const data = await res.json();

//         if (loading) loading.style.display = "none";

//         if (!data.dates || !data.historic) {
//             alert("Erreur données API");
//             return;
//         }

//         const traceHistoric = {
//             x: data.dates,
//             y: data.historic,
//             mode: "lines",
//             name: "Historique",
//             line: { color: "#4f8ef7", width: 2 }
//         };

//         const traceConfidence = {
//             x: [...data.pred_dates, ...data.pred_dates.slice().reverse()],
//             y: [...data.upper, ...data.lower.slice().reverse()],
//             fill: "toself",
//             fillcolor: "rgba(255, 150, 50, 0.15)",
//             line: { color: "transparent" },
//             name: "Intervalle de confiance",
//             showlegend: true,
//             type: "scatter"
//         };

//         const tracePred = {
//             x: data.pred_dates,
//             y: data.predictions,
//             mode: "lines+markers",
//             name: "Prédiction (Prophet)",
//             line: { color: "#ff9632", width: 2, dash: "dot" },
//             marker: { size: 7 }
//         };

//         const layout = {
//             title: `EUR → ${devise} : historique + prédiction Prophet`,
//             xaxis: { title: "Date" },
//             yaxis: { title: `Taux EUR/${devise}` },
//             legend: { orientation: "h", y: -0.2 },
//             hovermode: "x unified",
//             plot_bgcolor: "#fff",
//             paper_bgcolor: "#f8f9fa"
//         };

//         Plotly.newPlot("chart", [traceHistoric, traceConfidence, tracePred], layout);

//     } catch (err) {
//         if (loading) loading.style.display = "none";
//         console.error(err);
//         alert("Erreur JS → regarde la console");
//     }
// }