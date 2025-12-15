import { LOCALE, QUERY_KEYS, TEXT } from './const.js';

// ============= DATE CHANGE HANDLER =============
const bookingDateInput = document.getElementById('bookingDate');
if (bookingDateInput) {
    bookingDateInput.addEventListener('change', function () {
        const selectedDate = this.value;

        if (selectedDate) {
            const key = QUERY_KEYS.bookingDate;
            window.location.href = `?${key}=${encodeURIComponent(selectedDate)}`;
        }
    });
}

// ============= TIME SLOT SELECT =============
function selectTimeSlot(card) {
    if (!card || card.dataset.available !== 'true') return;

    document.querySelectorAll('.time-slot-card').forEach(c => {
        c.classList.remove('selected');
    });

    card.classList.add('selected');

    const { slotId, slotName, slotTime, slotPrice, slotDiscountedPrice } = card.dataset;

    document.getElementById('selectedTimeSlot').value = slotId;

    // Enable submit button
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) {
        submitBtn.disabled = false;
    }
}

document.querySelectorAll('.time-slot-card').forEach(card => {
    card.addEventListener('click', () => selectTimeSlot(card));
});


// ============= VOUCHER CHECK =============
let currentDiscountPercent = null;

function applyDiscountToSlots(discountPercent) {
    document.querySelectorAll('.time-slot-card').forEach(card => {
        const basePrice = Number(card.dataset.slotPrice);
        const priceTag = card.querySelector('.price-tag');
        if (!priceTag) return;

        if (discountPercent) {
            const discounted = Math.round(basePrice * (100 - discountPercent) / 100);
            card.dataset.slotDiscountedPrice = discounted;
            priceTag.innerHTML = `
                <span class="price-original text-decoration-line-through text-muted">${basePrice.toLocaleString(LOCALE)}đ</span>
                <span class="price-discount ms-1 text-danger fw-semibold">${discounted.toLocaleString(LOCALE)}đ</span>
            `;
        } else {
            delete card.dataset.slotDiscountedPrice;
            priceTag.innerHTML = `<span class="price-original">${basePrice.toLocaleString(LOCALE)}đ</span>`;
        }
    });
}

async function checkVoucher() {
    const code = document.getElementById('voucherCode').value.trim();
    const messageDiv = document.getElementById('voucherMessage');

    if (!code) {
        messageDiv.textContent = TEXT.MSG_ENTER_VOUCHER;
        return;
    }

    messageDiv.textContent = TEXT.MSG_VOUCHER_CHECKING;

    try {
        const url = `${window.checkVoucherUrl}?code=${encodeURIComponent(code)}`;
        const res = await fetch(url);

        if (!res.ok) {
            const error = new Error('Voucher HTTP error');
            error.name = 'VoucherCheckError';
            error.context = { status: res.status };
            throw error;
        }

        const data = await res.json();

        if (data.valid) {
            currentDiscountPercent = data.discount_percent;
            messageDiv.textContent = `${TEXT.MSG_VOUCHER_VALID} (Giảm ${data.discount_percent}%)`;
            applyDiscountToSlots(data.discount_percent);
        } else {
            currentDiscountPercent = null;
            messageDiv.textContent = data.message || TEXT.MSG_VOUCHER_INVALID;
            applyDiscountToSlots(null);
        }

    } catch (err) {
        messageDiv.textContent = TEXT.MSG_VOUCHER_ERROR;
        applyDiscountToSlots(null);

        // 3. Log error
        console.error({
            level: 'error',
            type: err.name,
            message: err.message,
            context: err.context || null,
            time: new Date().toISOString()
        });

        return;
    }
}

const voucherBtn = document.getElementById('checkVoucherBtn');
if (voucherBtn) {
    voucherBtn.addEventListener('click', checkVoucher);
}

// ============= FORM VALIDATION =============
const bookingForm = document.getElementById('bookingForm');
if (bookingForm) {
    bookingForm.addEventListener('submit', function (e) {
        const timeSlot = document.getElementById('selectedTimeSlot').value;

        if (!timeSlot) {
            e.preventDefault();
            const msg = document.getElementById('formMessage');
            if (msg) {
                msg.textContent = TEXT.TIME_SLOT_REQUIRED_MSG;
                msg.classList.remove('d-none');
            }
        }
    });
}
