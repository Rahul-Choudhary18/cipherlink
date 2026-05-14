const socket = io();

function sendMessage() {

    let messageInput = document.getElementById("message");

    let message = messageInput.value;

    if(message.trim() === "") {
        return;
    }

    socket.emit("send_message", {

        sender: CURRENT_USER,
        receiver: FRIEND,
        message: message

    });

    messageInput.value = "";
}

socket.on("receive_message", function(data) {

    // Only show messages of current chat

    if(
        (data.sender === CURRENT_USER && data.receiver === FRIEND)
        ||
        (data.sender === FRIEND && data.receiver === CURRENT_USER)
    ) {

        let messages = document.getElementById("messages");

        let div = document.createElement("div");

        if(data.sender === CURRENT_USER) {

            div.className = "my-message";

        } else {

            div.className = "friend-message";
        }

        div.innerHTML = data.message;

        messages.appendChild(div);

        messages.scrollTop = messages.scrollHeight;
    }
});