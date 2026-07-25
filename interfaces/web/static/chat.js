async function send(){

let box = document.getElementById("message");

let text = box.value;


if(!text)
    return;


addMessage(
    "You: " + text
);


box.value="";


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