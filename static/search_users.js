/* =========================
   SEARCH PAGE ANIMATIONS
========================= */

const searchInput =
    document.querySelector("input[name='search']");

const searchButton =
    document.querySelector(".search-box button");

/* =========================
   INPUT FOCUS EFFECT
========================= */

searchInput.addEventListener("focus", () => {

    searchInput.style.borderColor = "#2563eb";

    searchInput.style.boxShadow =
        "0 0 10px rgba(37,99,235,0.2)";
});

/* =========================
   REMOVE EFFECT
========================= */

searchInput.addEventListener("blur", () => {

    searchInput.style.borderColor = "#dbeafe";

    searchInput.style.boxShadow = "none";
});

/* =========================
   BUTTON CLICK EFFECT
========================= */

searchButton.addEventListener("click", () => {

    searchButton.innerHTML = "Searching...";

    searchButton.style.opacity = "0.8";
});

/* =========================
   RESULT CARD ANIMATION
========================= */

const resultCard =
    document.querySelector(".result-card");

if(resultCard){

    resultCard.style.opacity = "0";

    resultCard.style.transform =
        "translateY(20px)";

    setTimeout(() => {

        resultCard.style.transition =
            "0.4s ease";

        resultCard.style.opacity = "1";

        resultCard.style.transform =
            "translateY(0px)";

    }, 100);
}

/* =========================
   ERROR BOX ANIMATION
========================= */

const errorBox =
    document.querySelector(".error-box");

if(errorBox){

    errorBox.style.opacity = "0";

    errorBox.style.transform =
        "translateY(20px)";

    setTimeout(() => {

        errorBox.style.transition =
            "0.4s ease";

        errorBox.style.opacity = "1";

        errorBox.style.transform =
            "translateY(0px)";

    }, 100);
}