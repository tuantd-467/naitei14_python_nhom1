from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import User


class Command(BaseCommand):
    help = "Xóa các tài khoản chưa kích hoạt đã hết hạn kích hoạt."

    def handle(self, *args, **options):
        now = timezone.now()

        # Tài khoản chưa kích hoạt: is_active = False, có activation_expiry và đã quá hạn
        queryset = User.objects.filter(
            is_active=False,
            activation_expiry__isnull=False,
            activation_expiry__lt=now,
        )

        count = queryset.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("Không có tài khoản chưa kích hoạt nào cần xóa."))
            return

        usernames = list(queryset.values_list("username", flat=True))
        queryset.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Đã xóa {count} tài khoản chưa kích hoạt quá hạn: {', '.join(usernames)}"
            )
        )


