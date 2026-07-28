```javascript
// Spinner frames for animation
const spinnerFrames = ['◐', '◓', '◑', '◒'];

let spinnerIndex = 0;
let spinnerInterval = null;
let timerInterval = null;
let startTime = null;
let lastResponseTime = 0;



// ==========================
// LOADING SYSTEM
// ==========================


function startLoading() {

    const thinkingDiv =
        document.getElementById("thinking");


    if(thinkingDiv)
        thinkingDiv.style.display = "flex";



    startTime = Date.now();


    updateTimer();


    timerInterval = setInterval(
        updateTimer,
        100
    );



    spinnerIndex = 0;


    updateSpinner();


    spinnerInterval = setInterval(
        updateSpinner,
        150
    );

}





function stopLoading() {


    const thinkingDiv =
        document.getElementById("thinking");



    if(thinkingDiv)
        thinkingDiv.style.display = "none";



    if(startTime){

        lastResponseTime =
            (Date.now() - startTime)
            /
            1000;

    }




    if(timerInterval)
        clearInterval(timerInterval);



    if(spinnerInterval)
        clearInterval(spinnerInterval);




    spinnerIndex = 0;

    startTime = null;



    updateResponseTime();

}





function updateSpinner(){


    const spinner =
        document.getElementById("spinner");



    if(spinner){

        spinner.textContent =
            spinnerFrames[spinnerIndex];



        spinnerIndex =
            (
                spinnerIndex + 1
            )
            %
            spinnerFrames.length;

    }

}




function updateTimer(){


    if(startTime){


        const elapsed =
            (
                Date.now()
                -
                startTime
            )
            /
            1000;



        const timer =
            document.getElementById("timer");



        if(timer){

            timer.textContent =
                elapsed.toFixed(1);

        }

    }

}





function updateResponseTime(){


    const display =
        document.getElementById(
            "response-time"
        );


    if(display){

        display.textContent =
            "Last Response: "
            +
            lastResponseTime.toFixed(2)
            +
            " seconds";

    }

}




// ==========================
// CHAT SYSTEM
// ==========================


async function send(){


    let box =
        document.getElementById(
            "message"
        );



    let text =
        box.value;



    if(!text)
        return;




    addMessage(
        "You: "
        +
        text
    );



    box.value = "";



    startLoading();



    try {


        let response =
            await fetch(
                "/chat",
                {

                    method:"POST",

                    headers:{
                        "Content-Type":
                        "application/json"
                    },


                    body:
                    JSON.stringify({

                        message:text

                    })

                }
            );



        let data =
            await response.json();



        stopLoading();




        addMessage(
            "Cyn: "
            +
            data.response
        );



        addMessage(

            "[CYN-X RESPONSE TIME] "
            +
            lastResponseTime.toFixed(2)
            +
            " seconds"

        );



    }

    catch(error){


        stopLoading();



        addMessage(
            "[ERROR] "
            +
            error
        );


    }



}







function addMessage(msg){


    let chat =
        document.getElementById(
            "chat"
        );



    let div =
        document.createElement(
            "div"
        );



    div.innerText =
        msg;



    chat.appendChild(
        div
    );



    chat.scrollTop =
        chat.scrollHeight;

}





// ==========================
// BENCHMARK SYSTEM
// ==========================



async function loadBenchmark(){


    try{


        let response =
            await fetch(
                "/benchmark/results"
            );


        let data =
            await response.json();



        displayBenchmark(
            data
        );


    }


    catch(error){


        addMessage(
            "[BENCHMARK ERROR] "
            +
            error
        );


    }

}





async function loadBenchmarkStats(){


    try{


        let response =
            await fetch(
                "/benchmark/stats"
            );



        let stats =
            await response.json();



        let panel =
            document.getElementById(
                "stats"
            );



        if(panel){


            panel.innerText =

            `
CYN-X BENCHMARK STATUS

Tests:
${stats.tests}

Average Response:
${stats.average_time}s

Fastest:
${stats.fastest}s

Slowest:
${stats.slowest}s

Evolution Score:
${stats.average_score}/10
`;

        }


    }


    catch(error){


        console.log(
            error
        );

    }


}





function displayBenchmark(data){


    let panel =
        document.getElementById(
            "benchmark-history"
        );



    if(!panel)
        return;




    panel.innerHTML = "";




    data.forEach(
        result => {


            let div =
                document.createElement(
                    "div"
                );



            div.innerText =

            `
${result.test_id}

Category:
${result.category}

Time:
${result.response_time_seconds}s

Words:
${result.response_words}

Score:
${result.scores?.overall ?? "N/A"}

-------------------
`;



            panel.appendChild(
                div
            );


        }
    );


}






async function runBenchmark(){


    try{


        let response =
            await fetch(
                "/benchmark/run",
                {

                    method:"POST"

                }
            );



        let data =
            await response.json();



        addMessage(

            "[CYN-X BENCHMARK] "
            +
            data.status

        );



    }


    catch(error){


        addMessage(
            "[BENCHMARK FAILED] "
            +
            error
        );


    }

}






// Auto refresh stats when page loads

window.onload = function(){


    loadBenchmarkStats();


};
```
