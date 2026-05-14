// SMOOTH CARD HOVER EFFECT

const cards =
document.querySelectorAll(".card");

cards.forEach(card => {

    card.addEventListener("mouseenter", () => {

        card.style.transform =
        "translateY(-8px)";
    });

    card.addEventListener("mouseleave", () => {

        card.style.transform =
        "translateY(0px)";
    });

});

// FORM VALIDATION

const decryptForm =
document.querySelector(".decrypt-form");

if(decryptForm){

    decryptForm.addEventListener(
        "submit",
        function(event){

            const selects =
            decryptForm.querySelectorAll("select");

            let valid = true;

            selects.forEach(select => {

                if(select.value === ""){

                    valid = false;
                }
            });

            if(!valid){

                event.preventDefault();

                alert(
                    "Please select all required options."
                );
            }
        }
    );
}

// FILE CARD CLICK EFFECT

const fileCards =
document.querySelectorAll(".file-card");

fileCards.forEach(card => {

    card.addEventListener("click", () => {

        card.style.scale = "0.98";

        setTimeout(() => {

            card.style.scale = "1";

        }, 150);
    });

});