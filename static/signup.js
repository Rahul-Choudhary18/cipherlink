const togglePassword =
    document.getElementById("togglePassword");

const password =
    document.getElementById("password");

togglePassword.addEventListener("click", () => {

    if(password.type === "password"){

        password.type = "text";

        togglePassword.innerHTML = "🙈";
    }

    else{

        password.type = "password";

        togglePassword.innerHTML = "👁";
    }

});

const strengthFill =
    document.getElementById("strengthFill");

const strengthText =
    document.getElementById("strengthText");

password.addEventListener("input", () => {

    const value = password.value;

    let strength = 0;

    if(value.length >= 8) strength++;

    if(/[A-Z]/.test(value)) strength++;

    if(/[0-9]/.test(value)) strength++;

    if(/[!@#$%^&*]/.test(value)) strength++;

    if(strength === 1){

        strengthFill.style.width = "25%";
        strengthFill.style.background = "red";

        strengthText.innerHTML = "Weak Password";
    }

    else if(strength === 2){

        strengthFill.style.width = "50%";
        strengthFill.style.background = "orange";

        strengthText.innerHTML = "Medium Password";
    }

    else if(strength === 3){

        strengthFill.style.width = "75%";
        strengthFill.style.background = "#2563eb";

        strengthText.innerHTML = "Strong Password";
    }

    else if(strength === 4){

        strengthFill.style.width = "100%";
        strengthFill.style.background = "green";

        strengthText.innerHTML = "Very Strong Password";
    }

    else{

        strengthFill.style.width = "0%";

        strengthText.innerHTML = "Password Strength";
    }

});

const form =
    document.getElementById("signupForm");

const confirmPassword =
    document.getElementById("confirmPassword");

const errorMessage =
    document.getElementById("errorMessage");

form.addEventListener("submit", (e) => {

    if(password.value !== confirmPassword.value){

        e.preventDefault();

        errorMessage.innerHTML =
            "Passwords do not match";
    }

});