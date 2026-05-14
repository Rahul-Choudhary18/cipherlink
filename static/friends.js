// friends.js
// The friends page uses a single-page layout (no tabs).
// All sections (friend requests, group invitations, friends list) are always visible.
// This file is kept for any future JS enhancements on the friends page.

document.addEventListener("DOMContentLoaded", () => {

    // Animate cards on load
    const cards = document.querySelectorAll(".card");
    cards.forEach((card, i) => {
        card.style.opacity = "0";
        card.style.transform = "translateY(16px)";
        setTimeout(() => {
            card.style.transition = "opacity 0.35s ease, transform 0.35s ease";
            card.style.opacity = "1";
            card.style.transform = "translateY(0)";
        }, 60 * i);
    });

});