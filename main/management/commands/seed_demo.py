from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import (
    Facility,
    PitchType,
    Pitch,
    TimeSlot,
    PitchTimeSlot,
    User,
    Booking,
    BookingStatus,
    Role,
    Voucher,
)


class Command(BaseCommand):
    help = "Seed demo data: facilities, pitches, time slots, users, bookings."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding demo data..."))

        # Facilities
        facilities_data = [
            ("Sân Phú Thịnh", "123 Phan Chu Trinh, Đà Nẵng", "Cụm sân cỏ nhân tạo, bãi xe rộng."),
            ("Sân Hoà Khánh", "45 Lê Duẩn, Đà Nẵng", "Gần đại học, có phòng tắm và gửi đồ."),
            ("Sân Mỹ Đình", "Lê Đức Thọ, Hà Nội", "Sân chuẩn, có khán đài nhỏ."),
            ("Sân Thủ Đức", "Xa lộ Hà Nội, TP.HCM", "Bãi xe rộng, khu ăn nhẹ."),
        ]
        facilities = []
        for name, addr, desc in facilities_data:
            fac, _ = Facility.objects.get_or_create(
                name=name,
                defaults={
                    "address": addr,
                    "description": desc,
                },
            )
            facilities.append(fac)

        # Pitch types
        type_5, _ = PitchType.objects.get_or_create(
            name="Sân 5", defaults={"description": "Sân 5 người"}
        )
        type_7, _ = PitchType.objects.get_or_create(
            name="Sân 7", defaults={"description": "Sân 7 người"}
        )

        # Pitches (nhiều sân)
        pitches_data = [
            ("Sân A1", facilities[0], type_5, 250_000),
            ("Sân A2", facilities[0], type_7, 320_000),
            ("Sân B1", facilities[1], type_7, 300_000),
            ("Sân B2", facilities[1], type_5, 240_000),
            ("Sân C1", facilities[2], type_7, 350_000),
            ("Sân D1", facilities[3], type_5, 260_000),
        ]
        pitches = []
        for name, fac, ptype, price in pitches_data:
            pitch, _ = Pitch.objects.get_or_create(
                name=name,
                facility=fac,
                defaults={
                    "pitch_type": ptype,
                    "base_price_per_hour": price,
                    "is_available": True,
                    "images": [],
                },
            )
            pitches.append(pitch)

        # Time slots (fixed)
        slots_data = [
            ("07h-09h", time(7, 0), time(9, 0)),
            ("09h-11h", time(9, 0), time(11, 0)),
            ("17h-19h", time(17, 0), time(19, 0)),
            ("19h-21h", time(19, 0), time(21, 0)),
        ]
        time_slots = []
        for name, start, end in slots_data:
            ts, _ = TimeSlot.objects.get_or_create(name=name, start_time=start, end_time=end)
            time_slots.append(ts)

        # Link PitchTimeSlot
        for pitch in pitches:
            for ts in time_slots:
                PitchTimeSlot.objects.get_or_create(pitch=pitch, time_slot=ts, defaults={"is_available": True})

        # Users
        admin_user, created_admin = User.objects.get_or_create(
            username="admin_demo",
            defaults={
                "full_name": "Admin Demo",
                "email": "admin_demo@example.com",
                "role": Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if created_admin:
            admin_user.set_password("Admin@123")
            admin_user.save()

        normal_user, created_user = User.objects.get_or_create(
            username="user_demo",
            defaults={
                "full_name": "User Demo",
                "email": "user_demo@example.com",
                "role": Role.USER,
                "is_active": True,
            },
        )
        if created_user:
            normal_user.set_password("User@123")
            normal_user.save()

        # Sample bookings for the next days across pitches
        for idx, pitch in enumerate(pitches[:4]):
            booking_date = date.today() + timedelta(days=idx + 1)
            sample_slot = PitchTimeSlot.objects.filter(pitch=pitch).first()
            if sample_slot:
                Booking.objects.get_or_create(
                    user=normal_user,
                    pitch=pitch,
                    time_slot=sample_slot,
                    booking_date=booking_date,
                    defaults={
                        "status": BookingStatus.CONFIRMED if idx % 2 == 0 else BookingStatus.PENDING,
                        "note": "Demo booking tự động.",
                    },
                )

        # Vouchers (nhiều mã)
        vouchers_data = [
            ("WELCOME10", 10, None, 200),
            ("SUPER20", 20, 300_000, 50),
            ("WEEKEND15", 15, None, 100),
            ("BIG30", 30, 500_000, 30),
        ]
        for code, discount, min_value, usage in vouchers_data:
            Voucher.objects.get_or_create(
                code=code,
                defaults={
                    "description": f"Giảm {discount}%",
                    "discount_percent": discount,
                    "min_order_value": min_value,
                    "usage_limit": usage,
                    "is_active": True,
                },
            )

        self.stdout.write(self.style.SUCCESS("Seed demo data completed."))
        self.stdout.write(self.style.NOTICE("Tài khoản demo:"))
        self.stdout.write(" - Admin: admin_demo / Admin@123")
        self.stdout.write(" - User : user_demo / User@123")
        self.stdout.write(self.style.NOTICE("Voucher demo:"))
        for code, discount, min_value, usage in vouchers_data:
            desc = f"{code} (-{discount}%)"
            if min_value:
                desc += f", min {min_value:,.0f}"
            if usage:
                desc += f", limit {usage}"
            self.stdout.write(f" - {desc}")

