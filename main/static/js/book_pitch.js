document.addEventListener('DOMContentLoaded', function() {
    const today = new Date().toISOString().split('T')[0];
    const dateInput = document.querySelector('#dateSelectionForm input[name="booking_date"]');
    if (dateInput) {
        dateInput.min = today;
        
        dateInput.addEventListener('change', function() {
            if (this.value) {
                document.getElementById('dateSelectionForm').submit();
            }
        });
    }
});
