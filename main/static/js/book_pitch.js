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

function checkVoucher() {
    const voucherInput = document.querySelector('#bookingForm input[name="voucher_code"]');
    const voucherCode = voucherInput ? voucherInput.value.trim() : '';
    
    const hiddenDateInput = document.getElementById('hiddenBookingDate');
    const bookingDate = hiddenDateInput ? hiddenDateInput.value : '';
    
    if (!voucherCode) {
        alert('Vui lòng nhập mã giảm giá');
        if (voucherInput) voucherInput.focus();
        return;
    }
    
    if (!bookingDate) {
        alert('Vui lòng chọn ngày đặt sân trước');
        return;
    }
    
    let url = window.location.href.split('?')[0];
    url += `?booking_date=${encodeURIComponent(bookingDate)}&voucher_code=${encodeURIComponent(voucherCode)}`;
    window.location.href = url;
}
