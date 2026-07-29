// CYN-X Dashboard Controller


const benchmarkButton =
document.getElementById("benchmarkButton");


const clearLogs =
document.getElementById("clearLogs");


const exportResults =
document.getElementById("exportResults");


const benchmarkType =
document.getElementById("benchmarkType");


const benchmarkStatus =
document.getElementById("benchmarkStatus");


const benchmarkLogs =
document.getElementById("benchmarkLogs");





// Add messages to log window

function addLog(message)
{

    const entry =
    document.createElement("div");


    entry.innerHTML =
    `[${new Date().toLocaleTimeString()}] ${message}`;


    benchmarkLogs.appendChild(entry);


    benchmarkLogs.scrollTop =
    benchmarkLogs.scrollHeight;

}





// Run benchmark button

benchmarkButton.onclick = async () =>
{


    const type =
    benchmarkType.value;



    benchmarkStatus.innerHTML =
    "Running benchmark...";


    addLog(
        `Starting benchmark: ${type}`
    );



    try
    {


        const response =
        await fetch("/run_benchmark",
        {

            method:"POST",

            headers:
            {
                "Content-Type":"application/json"
            },


            body:
            JSON.stringify(
            {
                benchmark:type
            })

        });



        const result =
        await response.json();



        benchmarkStatus.innerHTML =
        "Benchmark complete";



        addLog(
            "Benchmark finished"
        );


        addLog(
            JSON.stringify(result)
        );



        updateGraphs(result);


    }


    catch(error)
    {


        benchmarkStatus.innerHTML =
        "Benchmark failed";


        addLog(
            error
        );


    }


};









// Clear logs

clearLogs.onclick = () =>
{

    benchmarkLogs.innerHTML =
    "CYN-X Console Cleared...";

};









// Export benchmark results

exportResults.onclick = () =>
{

    window.location.href =
    "/export_results";


};









// Graph setup

let performanceChart =
null;


let personalityChart =
null;





function updateGraphs(data)
{


    if(!data.metrics)
    {
        return;
    }



    const labels =
    data.metrics.map(
        x => x.name
    );



    const scores =
    data.metrics.map(
        x => x.score
    );



    if(performanceChart)
    {
        performanceChart.destroy();
    }



    performanceChart =
    new Chart(
    document.getElementById(
        "performanceGraph"
    ),
    {

        type:"line",


        data:
        {

            labels:labels,

            datasets:
            [
                {

                    label:
                    "Benchmark Score",

                    data:scores

                }
            ]

        }

    });



}