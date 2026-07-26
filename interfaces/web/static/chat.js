// Spinner frames for animation
const spinnerFrames = ['◐', '◓', '◑', '◒'];
let spinnerIndex = 0;
let spinnerInterval = null;
let timerInterval = null;
let startTime = null;

// Start the loading animation
function startLoading() {
    const thinkingDiv = document.getElementById("thinking");
    thinkingDiv.style.display = "flex";
    
    // Start timer
    startTime = Date.now();
    updateTimer();
    timerInterval = setInterval(updateTimer, 100);
    
    // Start spinner animation
    spinnerIndex = 0;
    updateSpinner();
    spinnerInterval = setInterval(updateSpinner, 150);
}

// Stop the loading animation
function stopLoading() {
    const thinkingDiv = document.getElementById("thinking");
    thinkingDiv.style.display = "none";
    
    // Clear intervals
    if (timerInterval) clearInterval(timerInterval);
    if (spinnerInterval) clearInterval(spinnerInterval);
    
    // Reset
    spinnerIndex = 0;
    startTime = null;
}

// Update spinner frame
function updateSpinner() {
    const spinner = document.getElementById("spinner");
    if (spinner) {
        spinner.textContent = spinnerFrames[spinnerIndex];
        spinnerIndex = (spinnerIndex + 1) % spinnerFrames.length;
    }
}

// Update timer display
function updateTimer() {
    if (startTime) {
        const elapsed = (Date.now() - startTime) / 1000;
        const timer = document.getElementById("timer");
        if (timer) {
            timer.textContent = elapsed.toFixed(1);
        }
    }
}

async function send(){

    let box = document.getElementById("message");

    let text = box.value;


    if(!text)
        return;


    addMessage(
        "You: " + text
    );


    box.value="";

    // Show loading panel
    startLoading();

    let response = await fetch(
        "/chat",
        {
            method:"POST",
            headers:{
                "Content-Type":"application/json"
            },
            body:JSON.stringify({
                message:text
            })
        }
    );

    // Hide loading panel
    stopLoading();

    let data = await response.json();


    addMessage(
        "Cyn: " + data.response
    );

}



function addMessage(msg){

    let chat =
    document.getElementById("chat");


    let div =
    document.createElement("div");


    div.innerText=msg;


    chat.appendChild(div);


    chat.scrollTop =
    chat.scrollHeight;

}