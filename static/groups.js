document.addEventListener('DOMContentLoaded', () => {

    // 1. File Upload UX Enhancement (Group Chat Workspace)
    // Shows the name of the file chosen right below the input box
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            let fileName = this.files[0] ? this.files[0].name : null;
            
            if (fileName) {
                let displaySpan = document.getElementById('file-chosen-text');
                
                // If the span doesn't exist yet, create it
                if (!displaySpan) {
                    displaySpan = document.createElement('span');
                    displaySpan.id = 'file-chosen-text';
                    displaySpan.style.display = 'block';
                    displaySpan.style.marginTop = '10px';
                    displaySpan.style.color = 'var(--accent)';
                    displaySpan.style.fontSize = '14px';
                    displaySpan.style.fontWeight = '600';
                    this.parentElement.appendChild(displaySpan);
                }
                
                displaySpan.textContent = `✔ Selected: ${fileName}`;
            }
        });
    }

    // 2. Access Control Input Validation
    // Forces the "Allowed Users" input to be formatted correctly (no spaces allowed)
    const allowedUsersInput = document.querySelector('input[name="allowed_users"]');
    if (allowedUsersInput) {
        allowedUsersInput.addEventListener('input', function() {
            // Remove any spaces the user tries to type
            this.value = this.value.replace(/\s+/g, '');
        });
    }

});