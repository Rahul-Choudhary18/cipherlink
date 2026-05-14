function searchPublicKey() {

    let input = document
        .getElementById("searchInput")
        .value
        .toLowerCase();

    let cards = document.getElementsByClassName("key-card");

    for(let i = 0; i < cards.length; i++) {

        let friendName = cards[i]
            .getElementsByClassName("friend-name")[0]
            .innerText
            .toLowerCase();

        if(friendName.includes(input)) {

            cards[i].style.display = "flex";

        }
        else {

            cards[i].style.display = "none";

        }
    }
}

function copyKeyName(name) {

    navigator.clipboard.writeText(name);

    alert("Copied: " + name);
}