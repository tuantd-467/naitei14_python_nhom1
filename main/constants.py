DEFAULT_PITCH_IMAGE = 'https://manager.datsan247.com/assets/images/banner-client-placeholder.jpg'
DEFAULT_FACILITY_IMAGE = 'https://manager.datsan247.com/assets/images/banner-client-placeholder.jpg'

ITEMS_PER_PAGE = 6
MAX_PAGINATION_LINKS = 5

ADMIN_LIST_PER_PAGE = 20
ADMIN_INLINE_EXTRA = 1

PRICE_RANGES = {
    '0-100000': (0, 100000),
    '100000-200000': (100000, 200000),
    '200000-300000': (200000, 300000),
    '300000': (300000, float('inf')),
}

VOUCHER_CODE_MAX_LENGTH = 50
VOUCHER_CODE_PATTERN = r'^[A-Za-z0-9\-_]+$'

MIN_BOOKING_ADVANCE_DAYS = 0 
MAX_BOOKING_ADVANCE_DAYS = 14  

ROLE_ADMIN = "Admin"
ROLE_USER = "User"

DATE_HIERARCHY_BOOKING = 'booking_date'

READONLY_TIMESTAMP_FIELDS = ('created_at', 'updated_at')
READONLY_ACTIVATION_FIELDS = ('activation_token', 'activation_expiry')

BOOKING_READONLY_FIELDS = ('created_at', 'updated_at', 'duration_hours', 'final_price', 'time_slot')

VOUCHER_READONLY_FIELDS = ('created_at', 'used_count')
