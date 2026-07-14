import calendar
from datetime import date
from models import Subscription, Expense
from exteptions import ValidationError, LimitExceededError


class FinanceTracker:


    def __init__(self, balance: float = 0.0):
        self.balance = balance
        self.limits: dict[str, float] = {}
        self.subscriptions: list[Subscription] = []
        self.expenses: list[Expense] = []

    def set_balance(self, amount: float):
        if amount <= 0:
            raise ValidationError("Начальный баланс или же сумма депозита не должна быть отрицательной")
        self.balance = amount

    def set_limits(self, category: str, amount: float):
        if not category.strip():
            raise ValidationError("Название категории не может быть пустым")
        if amount <= 0:
            raise ValidationError("Лимит должен быть больше нуля")
        self.limits[category.strip()] = amount

    def add_subscription(self, title: str, cost: float, category: str, next_billing_date: date):
        if not title.strip() or not category.strip():
            raise ValidationError("Название подписки и категория не могут быть пустыми.")
        if cost <= 0:
            raise ValidationError("Цена подписки должна быть больше 0.")

        new_sub = Subscription(title.strip(), cost, category.strip(), next_billing_date)
        self.subscriptions.append(new_sub)

    def remove_subscription(self, title: str):
        self.subscriptions = [s for s in self.subscriptions if s.title.lower() != title.strip().lower()]

    def get_safe_balance(self) -> float:
        safe_balance = self.balance
        for sub in self.subscriptions:
            if sub.is_active and sub.get_days_left() <= 7:
                safe_balance -= sub.cost
        return safe_balance

    def add_expense(self, amount: float, category: str, description: str = "", date_fixed: date = None) -> str | None:
        if amount <= 0:
            raise ValidationError("Сумма расхода должна быть больше нуля.")
        if not category.strip():
            raise ValidationError("Категория расхода не может быть пустой.")
        if date_fixed is None:
            date_fixed = date.today()

        category = category.strip()

        total_spent_before = sum(
            a.amount for a in self.expenses
            if a.category.lower() == category.lower()
            and a.date_fixed.month == date_fixed.month
            and a.date_fixed.year == date_fixed.year
        )
        total_spent_after = total_spent_before + amount

        if self.balance < amount:
            raise ValidationError(f"Недостаточно средств на балансе! Доступно: {self.balance:.2f} руб.")

        matched_limit_key = next((k for k in self.limits if k.lower() == category.lower()), None)

        if matched_limit_key:
            limit = self.limits[matched_limit_key]
            if total_spent_after > limit:
                overspent = total_spent_after - limit
                raise LimitExceededError(category=matched_limit_key, overspent_amount=overspent)

            self.expenses.append(Expense(amount, matched_limit_key, date_fixed, description.strip()))
            self.balance -= amount

            if total_spent_after >= limit * 0.8:
                return f"Внимание. Вы потратили 80% бюджета по категории {matched_limit_key}."
            return ""

        self.expenses.append(Expense(amount, category, date_fixed, description.strip()))
        self.balance -= amount
        return ""

    def process_auto_billings(self) -> list[str]:
        today = date.today()
        logs = []

        for sub in self.subscriptions:
            if not sub.is_active:
                continue

            while sub.next_billing_date <= today and sub.is_active:
                if self.balance >= sub.cost:
                    self.balance -= sub.cost

                    auto_expense = Expense(
                        amount=sub.cost,
                        category="Подписки",
                        date_fixed=sub.next_billing_date,
                        description=f"Автосписание: [{sub.title}]"
                    )
                    self.expenses.append(auto_expense)
                    logs.append(
                        f"Успешный платеж: Подписка '{sub.title}' оплачена ({sub.next_billing_date.strftime('%d.%m.%Y')}) на сумму {sub.cost:.2f} руб.")
                    sub.next_billing_date = self._add_months(sub.next_billing_date, 1)
                else:
                    sub.is_active = False
                    logs.append(
                        f"Критическое предупреждение. Ошибка автосписания: подписка {sub.title} приостановлена. Недостаточно средств.")
        return logs

    @staticmethod
    def _add_months(source_date: date, months: int) -> date:
        month = source_date.month - 1 + months
        year = source_date.year + month // 12
        month = month % 12 + 1
        day = min(source_date.day, calendar.monthrange(year, month))
        return date(year, month, day)