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

function escapeHTML(text){

    const div = document.createElement("div");

    div.textContent = text;

    return div.innerHTML;

}


function formatCynText(text){

    // If marked and DOMPurify are available, render Markdown -> sanitize -> return.
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {

        const renderer = new marked.Renderer();

        // Render links only for http/https and add the required attributes
        renderer.link = function(href, title, text) {
            try {
                if (!href) return escapeHTML(text);

                // allow only http(s)
                if (!/^https?:\/\//i.test(href)) {
                    return escapeHTML(text);
                }

                const safeHref = escapeHTML(href);
                const safeText = text || safeHref;
                const titleAttr = title ? ' title="' + escapeHTML(title) + '"' : '';

                return '<a class="cyn-link" href="' + safeHref + '"' + titleAttr + ' target="_blank" rel="noopener noreferrer">' + safeText + '</a>';

            } catch (e) {
                return escapeHTML(text);
            }
        };

        // Escape any raw HTML blocks from the model to avoid injecting HTML
        renderer.html = function(html) {
            return escapeHTML(html);
        };

        const rawHtml = marked.parse(text, { renderer: renderer });

        // Sanitize produced HTML and only allow http/https URIs
        const clean = DOMPurify.sanitize(rawHtml, { ALLOWED_URI_REGEXP: /^(?:https?):/i });

        return clean;

    }

    // Fallback: escape and linkify as before
    let safeText = escapeHTML(text);

    safeText = safeText.replace(
        /(https?:\/\/[^\s<]+)/gi,
        function(url){

            // Remove punctuation accidentally attached to URL.
            let cleanURL = url;
            let trailing = "";

            const match = url.match(/[.,!?;:)]+$/);

            if(match){

                trailing = match[0];

                cleanURL =
                    url.substring(
                        0,
                        url.length - trailing.length
                    );

            }

            return (
                '<a class="cyn-link" ' +
                'href="' + cleanURL + '" ' +
                'target="_blank" ' +
                'rel="noopener noreferrer">' +
                cleanURL +
                '</a>' +
                trailing
            );

        }
    );

    // Preserve line breaks in Cyn responses.
    safeText = safeText.replace(
        /\n/g,
        "<br>"
    );

    return safeText;

}


function addMessage(message) {

    const chat = document.getElementById("chat");

    if (!chat)
        return;

    const div = document.createElement("div");

    div.className = "message";

    if (message.startsWith("You:")) {

        const text = message.substring(4);

        div.innerHTML =
            '<span class="you-name">You:</span>' +
            '<span class="you-text">' +
            escapeHTML(text) +
            '</span>';

    }

    else if (message.startsWith("Cyn:")) {

        const text = message.substring(4);

        div.innerHTML =
            '<span class="cyn-name">Cyn:</span>' +
            '<span class="cyn-text">' +
            formatCynText(text) +
            '</span>';

    }

    else {

        div.textContent = message;

    }

    chat.appendChild(div);

    chat.scrollTop = chat.scrollHeight;
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