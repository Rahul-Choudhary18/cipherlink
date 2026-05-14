const passwordToggle =
    document.getElementById("passwordToggle");

const passwordInput =
    document.getElementById("password");

const toggleIcon =
    document.querySelector(".toggle-icon");

passwordToggle.addEventListener("click", () => {

    if(passwordInput.type === "password") {

        passwordInput.type = "text";

        toggleIcon.classList.add("show-password");

    }

    else {

        passwordInput.type = "password";

        toggleIcon.classList.remove("show-password");

    }

});