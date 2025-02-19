// Handle file uploads
function handleFileSubmit(event) {
    const fileInput = document.getElementById('file');
    if (fileInput && fileInput.files.length > 0) {
        event.preventDefault();
        handleFileUpload(fileInput.files[0], event.target);
        return false;
    }
    return true;
}

function handleFileUpload(file, form) {
    const progressBar = document.getElementById('upload-progress');
    const progressBarInner = progressBar.querySelector('.progress-bar');
    const errorDiv = document.getElementById('upload-error');
    const formData = new FormData(form);

    progressBar.classList.remove('d-none');
    errorDiv.classList.add('d-none');
    
    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            progressBarInner.style.width = percent + '%';
            progressBarInner.setAttribute('aria-valuenow', percent);
        }
    });

    xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
            form.submit();
        } else {
            errorDiv.textContent = 'Upload failed. Please try again.';
            errorDiv.classList.remove('d-none');
            progressBar.classList.add('d-none');
        }
    });

    xhr.addEventListener('error', () => {
        errorDiv.textContent = 'Network error occurred. Please try again.';
        errorDiv.classList.remove('d-none');
        progressBar.classList.add('d-none');
    });

    xhr.addEventListener('abort', () => {
        errorDiv.textContent = 'Upload cancelled.';
        errorDiv.classList.remove('d-none');
        progressBar.classList.add('d-none');
    });

    xhr.open('POST', form.action);
    xhr.send(formData);
}

// Initialize Feather Icons
document.addEventListener('DOMContentLoaded', function() {
    feather.replace();

    // Form validation
    const forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Add loading state to form submissions
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            const submitButton = form.querySelector('button[type="submit"]');
            if (form.checkValidity()) {
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
                submitButton.disabled = true;
                return true;
            }
            event.preventDefault();
            return false;
        });
    });
});

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}
