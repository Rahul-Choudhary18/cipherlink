const publicKeySelect =
document.getElementById("public_key_select");

if(publicKeySelect){

    publicKeySelect.addEventListener(
        "change",
        function(){

            let selected =
            publicKeySelect.options[
                publicKeySelect.selectedIndex
            ];

            let friend =
            selected.getAttribute("data-friend");

            document.getElementById(
                "friend_input"
            ).value = friend;
        }
    );
}