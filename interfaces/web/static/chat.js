// ==========================
// CYN-X CHAT CLIENT
// ==========================


// Spinner animation
const spinnerFrames = [
    "◐",
    "◓",
    "◑",
    "◒"
];


let spinnerIndex = 0;
let spinnerInterval = null;
let timerInterval = null;
let startTime = null;
let lastResponseTime = 0;



// ==========================
// LOADING DISPLAY
// ==========================


function startLoading(){


    const thinking =
        document.getElementById("thinking");


    if(thinking){
        thinking.style.display = "flex";
    }



    startTime = Date.now();



    timerInterval = setInterval(
        updateTimer,
        100
    );



    spinnerInterval = setInterval(
        updateSpinner,
        150
    );


}




function stopLoading(){


    const thinking =
        document.getElementById("thinking");


    if(thinking){
        thinking.style.display = "none";
    }



    if(startTime){

        lastResponseTime =
            (Date.now() - startTime) / 1000;

    }



    clearInterval(timerInterval);
    clearInterval(spinnerInterval);



    updateResponseTime();



}





function updateSpinner(){


    const spinner =
        document.getElementById(
            "spinner"
        );



    if(spinner){

        spinner.innerText =
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


    if(!startTime)
        return;



    const timer =
        document.getElementById(
            "timer"
        );



    if(timer){


        let seconds =
            (
                Date.now()
                -
                startTime
            )
            /
            1000;



        timer.innerText =
            seconds.toFixed(1);

    }


}





function updateResponseTime(){


    const display =
        document.getElementById(
            "response-time"
        );



    if(display){


        display.innerText =
            "Last Response: "
            +
            lastResponseTime.toFixed(2)
            +
            " seconds";


    }


}







// ==========================
// CHAT
// ==========================


async function send(){



    const input =
        document.getElementById(
            "message"
        );



    const text =
        input.value.trim();



    if(!text)
        return;



    addMessage(
        "You: " + text
    );



    input.value = "";



    startLoading();



    try{


        const response =
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



        const data =
            await response.json();



        stopLoading();




        addMessage(
            "Cyn: "
            +
            data.response
        );



    }



    catch(error){


        stopLoading();


        addMessage(
            "[ERROR] "
            +
            error.message
        );


    }


}







// ==========================
// CHAT DISPLAY
// ==========================
// ==========================
// CHAT DISPLAY
// ==========================

function addMessage(message){


    const chat =
        document.getElementById(
            "chat"
        );


    if(!chat)
        return;



    const div =
        document.createElement(
            "div"
        );


    div.className =
        "message";



    if(message.startsWith("You:")){


        div.innerHTML =
            `<span class="you-name">You:</span>` +
            `<span class="you-text">${message.substring(4)}</span>`;

    }


    else if(message.startsWith("Cyn:")){


        div.innerHTML =
            `<span class="cyn-name">Cyn:</span>` +
            `<span class="cyn-text">${message.substring(4)}</span>`;

    }


    else{


        div.innerText =
            message;


    }



    chat.appendChild(
        div
    );


    chat.scrollTop =
        chat.scrollHeight;


}







// ==========================
// KEYBOARD SUPPORT
// ==========================


window.onload = function(){


    const input =
        document.getElementById(
            "message"
        );



    if(input){


        input.addEventListener(
            "keydown",
            function(event){


                if(
                    event.key === "Enter"
                ){

                    send();

                }


            }
        );


    }


};







// ==========================
// OPTIONAL DEBUG
// ==========================


console.log(
    "CYN-X chat interface loaded"
);

document.addEventListener("DOMContentLoaded", () => {

    console.log("CYN-X DOM READY");


    const button =
        document.getElementById("sendButton");


    if(button){

        button.addEventListener(
            "click",
            send
        );


        console.log(
            "SEND BUTTON CONNECTED"
        );

    }
    else{

        console.error(
            "SEND BUTTON NOT FOUND"
        );

    }


});