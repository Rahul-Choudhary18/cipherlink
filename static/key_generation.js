const popup =
    document.getElementById("popup");

const generateBtn =
    document.getElementById("generateBtn");

const closePopup =
    document.getElementById("closePopup");

const viewBtn =
    document.getElementById("viewBtn");

const keysSection =
    document.getElementById("keysSection");

/* =========================
   OPEN POPUP
========================= */

generateBtn.addEventListener("click", () => {

    popup.style.display = "flex";

});

/* =========================
   CLOSE POPUP
========================= */

closePopup.addEventListener("click", () => {

    popup.style.display = "none";

});

/* =========================
   CLOSE OUTSIDE
========================= */

window.addEventListener("click", (e) => {

    if(e.target === popup){

        popup.style.display = "none";
    }

});

/* =========================
   SHOW GENERATED KEYS
========================= */

viewBtn.addEventListener("click", () => {

    if(keysSection.style.display === "none"){

        keysSection.style.display = "block";

        viewBtn.innerHTML = "Hide Keys";
    }

    else{

        keysSection.style.display = "none";

        viewBtn.innerHTML = "View Keys";
    }

});